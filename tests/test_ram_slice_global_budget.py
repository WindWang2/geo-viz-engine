"""RamSliceCache shared-ledger budget API (P2-A wiring)."""
from __future__ import annotations

import numpy as np

from geoviz_seismic.cache import RamSliceCache, global_stats, set_global_budget


def test_set_global_budget_shrinks_and_evicts():
    previous = set_global_budget(1_048_576)
    cache = RamSliceCache(max_bytes=10_000, max_slices=10)
    key = "p2-l1-budget-probe"
    try:
        cache.put(key, np.ones(500, dtype=np.uint8))
        assert key in cache
        assert global_stats()["budget_bytes"] == 1_048_576

        restored = set_global_budget(100)
        assert restored == 1_048_576
        after = global_stats()
        assert after["budget_bytes"] == 100
        assert after["bytes_now"] <= 100
        assert key not in cache
    finally:
        cache.clear()
        set_global_budget(previous)
