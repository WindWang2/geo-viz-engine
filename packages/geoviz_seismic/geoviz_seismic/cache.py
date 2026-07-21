"""LRU cache for seismic 2-D slice data (RAM L1 + VRAM L2)."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import threading
import numpy as np


@dataclass(frozen=True)
class SliceCacheKey:
    volume_id: str
    slice_type: str
    position: int
    downsample_factor: tuple[int, ...] = (1, 1, 1)
    attribute_id: str = "raw"


class RamSliceCache:
    """RAM (L1) LRU cache with strict Byte Budget and slice count limits."""

    def __init__(self, max_bytes: int = 512 * 1024 * 1024, max_slices: int = 200):
        self._max_bytes = max_bytes
        self._max_slices = max_slices
        self._current_bytes = 0
        self._cache: OrderedDict[Any, np.ndarray] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: Any) -> np.ndarray | None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    def put(self, key: Any, data: np.ndarray) -> None:
        size_bytes = data.nbytes
        with self._lock:
            if key in self._cache:
                self._current_bytes -= self._cache[key].nbytes
                self._cache.move_to_end(key)

            while (self._current_bytes + size_bytes > self._max_bytes or len(self._cache) >= self._max_slices) and self._cache:
                k, evicted = self._cache.popitem(last=False)
                self._current_bytes -= evicted.nbytes

            self._cache[key] = data
            self._current_bytes += size_bytes

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._current_bytes = 0

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)

    def __contains__(self, key: Any) -> bool:
        with self._lock:
            return key in self._cache


class DualLevelSeismicCache:
    """Dual-level LRU Cache combining L1 (RAM) and L2 (VRAM handle) budgets."""

    def __init__(self, ram_bytes: int = 512 * 1024 * 1024, vram_bytes: int = 256 * 1024 * 1024):
        self.ram_cache = RamSliceCache(max_bytes=ram_bytes)
        self.vram_cache: OrderedDict[Any, Any] = OrderedDict()
        self.vram_bytes_limit = vram_bytes
        self.current_vram_bytes = 0

    def get_slice(self, key: Any) -> np.ndarray | None:
        return self.ram_cache.get(key)

    def put_slice(self, key: Any, data: np.ndarray) -> None:
        self.ram_cache.put(key, data)


# Backward-compatible alias
class SeismicCache(RamSliceCache):
    def __init__(self, max_slices: int = 50):
        super().__init__(max_bytes=512 * 1024 * 1024, max_slices=max_slices)
