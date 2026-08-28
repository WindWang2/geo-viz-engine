"""Global VRAM (L2) texture cache: one byte budget, LRU eviction, explicit release.

Second level of the dual-level slice cache (``docs/research/segy-async-cache.md``
§2.3): L1 (:class:`geoviz_seismic.cache.RamSliceCache`) keeps decoded float32
slices in RAM; this module keeps *display-ready texture residency* — GPU
texture handles and their upload-source content arrays (uint8 LUT-index slices,
RGBA composites) — inside ONE process-wide byte budget.

Every texture type shares the same ledger: 2-D profile slice textures,
3-D orthogonal slice planes, overlay volumes, horizon (sculpt) textures,
the 3-D volume brick, wiggle R32F slices and the small colormap LUTs.
When the budget is exceeded the globally least-recently-used entry is
evicted and its GPU memory is released *explicitly* through an
owner-supplied ``release`` callback (direct ``glDeleteTextures`` when a
context is current, deferred delete otherwise — see
``renderer_3d.queue_gl_texture_delete``).  Owners must make evicted
resources re-uploadable, so an eviction is invisible except for a one-frame
re-upload cost.

Colormap independence: entry keys never include the colormap name.  A
colormap switch re-uploads only the 256-entry LUT textures (O(1)) and keeps
both L1 raw slices and L2 index textures valid — “colormap 切换只重建 L2
着色，不重读 L1”.

All views share the module-level singleton :data:`VRAM`, so the budget does
not scale with the number of open views.

Budget configuration: ``GEOVIZ_VRAM_BUDGET_MB`` environment variable or
:data:`VRAM.set_budget` programmatically (default 1 GiB, clamped to
512 MiB–2 GiB per the L2 budget contract).
"""
from __future__ import annotations

import logging
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

logger = logging.getLogger(__name__)

# Budget bounds from the L2 contract: default 1 GiB, user-configurable in
# [512 MiB, 2 GiB].  Below 512 MiB a single 10000x10000 time slice plus the
# volume brick no longer fit; above 2 GiB integrated GPUs start swapping.
MIN_BUDGET_BYTES = 512 * 1024 * 1024
MAX_BUDGET_BYTES = 2 * 1024 * 1024 * 1024
DEFAULT_BUDGET_BYTES = 1024 * 1024 * 1024

_ENV_BUDGET_MB = "GEOVIZ_VRAM_BUDGET_MB"


def _clamp_budget(value_bytes: int) -> int:
    return max(MIN_BUDGET_BYTES, min(MAX_BUDGET_BYTES, int(value_bytes)))


def _budget_from_env() -> int:
    raw = os.environ.get(_ENV_BUDGET_MB)
    if not raw:
        return DEFAULT_BUDGET_BYTES
    try:
        mib = float(raw)
    except ValueError:
        logger.warning("%s=%r is not a number; using default L2 budget", _ENV_BUDGET_MB, raw)
        return DEFAULT_BUDGET_BYTES
    if mib <= 0:
        return DEFAULT_BUDGET_BYTES
    return _clamp_budget(int(mib * 1024 * 1024))


@dataclass
class _VramEntry:
    """One tracked texture residency (GPU handle and/or upload content)."""

    key: tuple
    kind: str
    size_bytes: int
    handle: int | None = None
    # Upload-source content (uint8 index array / RGBA composite).  Serves the
    # L2-hit fast path: re-display skips L1→normalize and re-uploads/renders
    # straight from this array.
    content: np.ndarray | None = None
    # Owner-supplied explicit GPU free.  Must leave the owner re-uploadable
    # (e.g. set texture handle to None and raise the needs-upload flag).
    release: Callable[[], None] | None = None
    touch_count: int = 0


@dataclass
class VramStats:
    """Diagnostic counters (the budget's verifiable evidence)."""

    budget_bytes: int = 0
    bytes_now: int = 0
    peak_bytes: int = 0
    entries: int = 0
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    releases: int = 0
    release_errors: int = 0
    by_kind: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "budget_bytes": self.budget_bytes,
            "bytes_now": self.bytes_now,
            "peak_bytes": self.peak_bytes,
            "entries": self.entries,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "releases": self.releases,
            "release_errors": self.release_errors,
            "by_kind": dict(self.by_kind),
        }


class VramTextureCache:
    """Process-wide L2 texture ledger with strict byte budget and global LRU.

    All instances of the application share ONE cache object (the module-level
    :data:`VRAM` singleton), so N open views still consume at most one budget.
    The class can also be instantiated directly in tests to exercise the
    eviction policy against a private budget.
    """

    def __init__(self, max_bytes: int | None = None, *, _use_env: bool = True):
        self._max_bytes = (
            _budget_from_env() if max_bytes is None and _use_env else DEFAULT_BUDGET_BYTES
        )
        if max_bytes is not None:
            # Explicit constructor budget is respected verbatim (tests use
            # tiny budgets); the 512 MiB-2 GiB clamp is a *user-facing*
            # configuration bound, applied in set_budget().
            self._max_bytes = int(max_bytes)
        self._lock = threading.RLock()
        self._lru: OrderedDict[tuple, _VramEntry] = OrderedDict()
        self._stats = VramStats(budget_bytes=self._max_bytes)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def budget_bytes(self) -> int:
        with self._lock:
            return self._max_bytes

    def set_budget(self, value_bytes: int) -> int:
        """Set the global byte budget (clamped to 512 MiB–2 GiB).

        Shrinking below current usage evicts the globally least-recently-used
        textures immediately.  Returns the effective budget.
        """
        value_bytes = _clamp_budget(int(value_bytes))
        with self._lock:
            self._max_bytes = value_bytes
            self._stats.budget_bytes = value_bytes
            self._apply_budget()
            return self._max_bytes

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def get(self, key: tuple) -> np.ndarray | None:
        """Return the cached upload content for *key*, or ``None`` on miss.

        Counts a diagnostic hit whenever the key is resident (even for
        handle-only entries) and bumps the key to the MRU end.
        """
        with self._lock:
            entry = self._lru.get(key)
            if entry is None:
                self._stats.misses += 1
                return None
            self._stats.hits += 1
            self._lru.move_to_end(key)
            return entry.content

    def touch(self, key: tuple) -> None:
        """Bump *key* to MRU without hit/miss accounting (paint-time keepalive)."""
        with self._lock:
            if key in self._lru:
                self._lru.move_to_end(key)
                self._lru[key].touch_count += 1

    def put(
        self,
        key: tuple,
        content: np.ndarray | None,
        size_bytes: int,
        kind: str,
        *,
        handle: int | None = None,
        release: Callable[[], None] | None = None,
    ) -> None:
        """Register (or refresh) one texture residency and enforce the budget.

        Re-registering an existing key updates it in place — the owner is
        expected to reuse its GL texture name, so no release fires for the
        old entry; only the byte accounting is adjusted.
        """
        if size_bytes < 0:
            raise ValueError(f"size_bytes must be >= 0, got {size_bytes}")
        with self._lock:
            old = self._lru.get(key)
            if old is not None:
                self._remove_bytes(old.kind, old.size_bytes)
            self._lru[key] = _VramEntry(
                key=key,
                kind=kind,
                size_bytes=int(size_bytes),
                handle=handle,
                content=content,
                release=release,
            )
            self._lru.move_to_end(key)
            self._add_bytes(kind, int(size_bytes))
            self._apply_budget(protect=key)

    # Convenience alias matching RamSliceCache's vocabulary.
    register = put

    def unregister(self, key: tuple) -> None:
        """Remove an entry the owner has already freed (no release callback).

        Used from ``clean()`` paths where the GL objects are deleted by the
        owner itself; only the ledger is updated.
        """
        with self._lock:
            entry = self._lru.pop(key, None)
            if entry is not None:
                self._remove_bytes(entry.kind, entry.size_bytes)

    def clear(self) -> None:
        """Drop every entry, invoking each release callback exactly once."""
        with self._lock:
            entries = list(self._lru.values())
            self._lru.clear()
            self._stats.bytes_now = 0
            self._stats.entries = 0
            self._stats.by_kind.clear()
            for entry in entries:
                self._invoke_release(entry)

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return self._stats.as_dict()

    def resident_kinds(self) -> dict[str, int]:
        """Per-kind byte usage snapshot."""
        with self._lock:
            return dict(self._stats.by_kind)

    def __len__(self) -> int:
        with self._lock:
            return len(self._lru)

    def __contains__(self, key: tuple) -> bool:
        with self._lock:
            return key in self._lru

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _add_bytes(self, kind: str, size_bytes: int) -> None:
        self._stats.bytes_now += size_bytes
        self._stats.by_kind[kind] = self._stats.by_kind.get(kind, 0) + size_bytes
        self._stats.peak_bytes = max(self._stats.peak_bytes, self._stats.bytes_now)
        self._stats.entries = len(self._lru)

    def _remove_bytes(self, kind: str, size_bytes: int) -> None:
        self._stats.bytes_now -= size_bytes
        remaining = self._stats.by_kind.get(kind, 0) - size_bytes
        if remaining > 0:
            self._stats.by_kind[kind] = remaining
        else:
            self._stats.by_kind.pop(kind, None)
        self._stats.entries = len(self._lru)

    def _invoke_release(self, entry: _VramEntry) -> None:
        if entry.release is None:
            return
        try:
            entry.release()
            self._stats.releases += 1
        except Exception:
            # A broken release must never break rendering or eviction.
            self._stats.release_errors += 1
            logger.debug("VRAM release callback failed for %r", entry.key, exc_info=True)

    def _apply_budget(self, protect: tuple | None = None) -> None:
        """Evict globally-LRU entries while over budget.

        *protect* (the just-inserted key) is never chosen as a victim so a
        single huge slice cannot evict itself; if it alone exceeds the whole
        budget it stays resident — refusing to display the requested slice
        would be worse than a documented transient oversubscription.
        """
        while self._stats.bytes_now > self._max_bytes:
            victim_key = None
            for cand_key in self._lru:  # OrderedDict iterates LRU-first
                if cand_key != protect:
                    victim_key = cand_key
                    break
            if victim_key is None:
                break
            entry = self._lru.pop(victim_key)
            self._remove_bytes(entry.kind, entry.size_bytes)
            self._stats.evictions += 1
            self._invoke_release(entry)
        if self._stats.bytes_now > self._max_bytes:
            logger.warning(
                "L2 VRAM budget %d exceeded: a single entry holds %d bytes "
                "(%d entries resident)",
                self._max_bytes,
                self._stats.bytes_now,
                len(self._lru),
            )


# Module-level singleton: the ONE global VRAM budget shared by every view
# (2-D profiles, 3-D renderer, wiggle renderer, overlays, horizons).
VRAM: VramTextureCache = VramTextureCache()


def reset_for_tests(cache: VramTextureCache | None = None) -> None:
    """Reset a cache's ledger and counters (test isolation helper)."""
    target = cache if cache is not None else VRAM
    with target._lock:
        target._lru.clear()
        budget = target._max_bytes
        target._stats = VramStats(budget_bytes=budget)
