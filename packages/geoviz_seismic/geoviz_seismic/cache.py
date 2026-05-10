"""LRU cache for seismic 2-D slice data."""

from collections import OrderedDict

import numpy as np


class SeismicCache:
    """Simple LRU cache keyed by ``(slice_type, position)`` tuples.

    Args:
        max_slices: Maximum number of slices to retain. Eviction is
            count-based; a single slice can be multiple MB.

    Note:
        There is no memory-based eviction. For large volumes, consider
        lowering *max_slices* to avoid excessive RAM usage.
    """

    def __init__(self, max_slices: int = 50):
        self._max = max_slices
        self._cache: OrderedDict[tuple, np.ndarray] = OrderedDict()

    def get(self, key: tuple) -> np.ndarray | None:
        """Return cached slice or ``None``."""
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, key: tuple, data: np.ndarray) -> None:
        """Insert a slice, evicting the oldest entry if capacity is exceeded."""
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = data
        while len(self._cache) > self._max:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        """Remove all cached slices."""
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, key: tuple) -> bool:
        return key in self._cache
