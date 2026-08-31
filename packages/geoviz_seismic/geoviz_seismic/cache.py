"""LRU cache for seismic 2-D slice data (RAM L1 + VRAM L2)."""
from __future__ import annotations

import itertools
import threading
import weakref
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

import numpy as np

# Module-level global byte budget shared by ALL cache instances.  The
# per-instance ``max_bytes`` (default 512 MB) is per-view, so N open views
# could otherwise hold N × 512 MB of slices.  When the shared budget is
# exceeded, entries are evicted in global LRU order across instances.
_GLOBAL_MAX_BYTES = 1024 * 1024 * 1024  # 1 GiB across all instances
_GLOBAL_BYTES = 0
_GLOBAL_LRU: OrderedDict[tuple[int, object], np.ndarray] = OrderedDict()
_GLOBAL_LOCK = threading.RLock()
_NEXT_CACHE_ID = itertools.count()
_CACHE_REGISTRY: weakref.WeakValueDictionary[int, object] = weakref.WeakValueDictionary()


def _global_bytes() -> int:
    """Return the total bytes currently held by all cache instances."""
    return _GLOBAL_BYTES


def set_global_budget(max_bytes: int) -> int:
    """Set the shared byte budget across ALL cache instances (P2-A wiring).

    The workbench's ``ResourceBudget.l1_slice_cache_bytes`` is pushed here at
    startup/relief time instead of the hardcoded 1 GiB default. Shrinking the
    budget evicts global-LRU entries immediately; growing it never allocates
    anything. Returns the previous budget.
    """
    global _GLOBAL_MAX_BYTES
    max_bytes = max(0, int(max_bytes))
    with _GLOBAL_LOCK:
        previous = _GLOBAL_MAX_BYTES
        _GLOBAL_MAX_BYTES = max_bytes
        # Evict in global LRU order until the shared ledger fits the new cap.
        # Runs on every live instance's overage helper for bookkeeping parity.
        while _GLOBAL_BYTES > _GLOBAL_MAX_BYTES and _GLOBAL_LRU:
            gkey, evicted = _GLOBAL_LRU.popitem(last=False)
            _GLOBAL_BYTES -= evicted.nbytes
            inst_id, key = gkey
            owner = _CACHE_REGISTRY.get(inst_id)
            if owner is not None and key in owner._cache:
                owner._current_bytes -= evicted.nbytes
                del owner._cache[key]
        return previous


def global_stats() -> dict:
    """Shared-ledger diagnostics (bytes held, budget, instances, entries)."""
    with _GLOBAL_LOCK:
        return {
            "budget_bytes": _GLOBAL_MAX_BYTES,
            "bytes_now": _GLOBAL_BYTES,
            "entries": len(_GLOBAL_LRU),
            "instances": len(_CACHE_REGISTRY),
        }


@dataclass(frozen=True)
class SliceCacheKey:
    volume_id: str
    slice_type: str
    position: int
    downsample_factor: tuple[int, ...] = (1, 1, 1)
    attribute_id: str = "raw"


class RamSliceCache:
    """RAM (L1) LRU cache with strict Byte Budget and slice count limits.

    All instances share one module-level byte budget
    (:data:`_GLOBAL_MAX_BYTES`); when it is exceeded the least-recently
    used entry across *all* instances is evicted, so a single view cannot
    starve the others.
    """

    def __init__(self, max_bytes: int = 512 * 1024 * 1024, max_slices: int = 200):
        self._max_bytes = max_bytes
        self._max_slices = max_slices
        self._current_bytes = 0
        self._cache: OrderedDict[Any, np.ndarray] = OrderedDict()
        self._instance_id = next(_NEXT_CACHE_ID)
        # All instances share the module lock: instance budgets and the
        # global budget are updated atomically together.
        self._lock = _GLOBAL_LOCK
        _CACHE_REGISTRY[self._instance_id] = self

    def get(self, key: Any) -> np.ndarray | None:
        with _GLOBAL_LOCK:
            if key in self._cache:
                self._cache.move_to_end(key)
                gkey = (self._instance_id, key)
                if gkey in _GLOBAL_LRU:
                    _GLOBAL_LRU.move_to_end(gkey)
                return self._cache[key]
            return None

    def put(self, key: Any, data: np.ndarray) -> None:
        global _GLOBAL_BYTES
        size_bytes = data.nbytes
        with _GLOBAL_LOCK:
            gkey = (self._instance_id, key)
            if key in self._cache:
                old = self._cache[key]
                self._current_bytes -= old.nbytes
                if gkey in _GLOBAL_LRU:
                    del _GLOBAL_LRU[gkey]
                    _GLOBAL_BYTES -= old.nbytes
                self._cache.move_to_end(key)

            while (self._current_bytes + size_bytes > self._max_bytes or len(self._cache) >= self._max_slices) and self._cache:
                k, evicted = self._cache.popitem(last=False)
                self._current_bytes -= evicted.nbytes
                gk = (self._instance_id, k)
                if gk in _GLOBAL_LRU:
                    del _GLOBAL_LRU[gk]
                    _GLOBAL_BYTES -= evicted.nbytes

            self._cache[key] = data
            self._current_bytes += size_bytes
            _GLOBAL_LRU[gkey] = data
            _GLOBAL_LRU.move_to_end(gkey)
            _GLOBAL_BYTES += size_bytes
            self._evict_global_overage()

    def _evict_global_overage(self) -> None:
        """Evict the globally least-recently-used entry while over budget."""
        global _GLOBAL_BYTES
        while _GLOBAL_BYTES > _GLOBAL_MAX_BYTES and _GLOBAL_LRU:
            gkey, evicted = _GLOBAL_LRU.popitem(last=False)
            _GLOBAL_BYTES -= evicted.nbytes
            inst_id, key = gkey
            owner = _CACHE_REGISTRY.get(inst_id)
            if owner is not None and key in owner._cache:
                owner._current_bytes -= evicted.nbytes
                del owner._cache[key]

    def clear(self) -> None:
        global _GLOBAL_BYTES
        with _GLOBAL_LOCK:
            for key, data in self._cache.items():
                gkey = (self._instance_id, key)
                if gkey in _GLOBAL_LRU:
                    del _GLOBAL_LRU[gkey]
                    _GLOBAL_BYTES -= data.nbytes
            self._cache.clear()
            self._current_bytes = 0

    def __len__(self) -> int:
        with _GLOBAL_LOCK:
            return len(self._cache)

    def __contains__(self, key: Any) -> bool:
        with _GLOBAL_LOCK:
            return key in self._cache


# Backward-compatible alias
class SeismicCache(RamSliceCache):
    def __init__(self, max_slices: int = 50):
        super().__init__(max_bytes=512 * 1024 * 1024, max_slices=max_slices)


# L2 (VRAM) half of the dual-level cache. Defined in vram_cache.py to keep
# this module free of the GL-adjacent machinery; re-exported so the whole
# two-level cache is importable from geoviz_seismic.cache.
from .vram_cache import (  # noqa: E402
    VRAM,
    VramStats,
    VramTextureCache,
    reset_for_tests,
)
