import numpy as np
import pytest

from geoviz_seismic.cache import SeismicCache


def test_cache_miss_returns_none():
    cache = SeismicCache(max_slices=5)
    assert cache.get(("inline", 100)) is None


def test_cache_put_and_get():
    cache = SeismicCache(max_slices=5)
    data = np.ones((10, 20), dtype=np.float32)
    cache.put(("inline", 100), data)
    result = cache.get(("inline", 100))
    assert result is not None
    np.testing.assert_array_equal(result, data)


def test_cache_lru_eviction():
    cache = SeismicCache(max_slices=3)
    for i in range(5):
        cache.put(("inline", i), np.zeros((5, 5), dtype=np.float32))
    assert cache.get(("inline", 0)) is None
    assert cache.get(("inline", 1)) is None
    assert cache.get(("inline", 2)) is not None
    assert cache.get(("inline", 3)) is not None
    assert cache.get(("inline", 4)) is not None


def test_cache_clear():
    cache = SeismicCache(max_slices=5)
    cache.put(("inline", 0), np.zeros((5, 5)))
    cache.clear()
    assert cache.get(("inline", 0)) is None


def test_cache_hit_refreshes_lru():
    cache = SeismicCache(max_slices=3)
    cache.put(("inline", 0), np.zeros((5, 5)))
    cache.put(("inline", 1), np.zeros((5, 5)))
    cache.put(("inline", 2), np.zeros((5, 5)))
    cache.get(("inline", 0))
    cache.put(("inline", 3), np.zeros((5, 5)))
    assert cache.get(("inline", 0)) is not None
    assert cache.get(("inline", 1)) is None
