from collections import OrderedDict

import numpy as np


class SeismicCache:
    def __init__(self, max_slices: int = 50):
        self._max = max_slices
        self._cache: OrderedDict[tuple, np.ndarray] = OrderedDict()

    def get(self, key: tuple) -> np.ndarray | None:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, key: tuple, data: np.ndarray):
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = data
        while len(self._cache) > self._max:
            self._cache.popitem(last=False)

    def clear(self):
        self._cache.clear()
