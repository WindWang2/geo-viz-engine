from __future__ import annotations

import math

import numpy as np
import pytest


def test_modified_z_scores_flags_deviation_when_mad_is_zero():
    from geoviz import modified_z_scores

    scores = modified_z_scores([0.0, 0.0, 0.0, 100.0])

    assert np.array_equal(scores[:3], np.zeros(3))
    assert math.isinf(float(scores[3]))
    assert float(scores[3]) > 0


def test_sand_ratio_core_enforces_closed_unit_interval():
    from geoviz import compute_sand_ratio

    assert compute_sand_ratio(0.0, 5.0) == (0.0, "ok")
    assert compute_sand_ratio(5.0, 5.0) == (1.0, "ok")
    assert compute_sand_ratio(5.1, 5.0) == (None, "invalid_ratio")
    assert compute_sand_ratio(1.0, 0.0) == (None, "invalid_ratio")


def test_directional_distance_rejects_non_positive_axes():
    from geoviz import directional_distance

    with pytest.raises(ValueError, match="positive"):
        directional_distance(np.array([1.0]), np.array([1.0]), a=0.0, b=1.0)


def test_chunked_directional_grid_matches_single_chunk():
    from geoviz import directional_trend_grid

    xs = np.array([0.0, 1.0, 0.0, 1.0])
    ys = np.array([0.0, 0.0, 1.0, 1.0])
    zs = np.array([1.0, 2.0, 3.0, 4.0])
    gx = np.linspace(0.0, 1.0, 11)
    gy = np.linspace(0.0, 1.0, 9)

    chunked = directional_trend_grid(
        xs, ys, zs, gx, gy, a=2.0, b=0.5, max_cells_per_chunk=7
    )
    single = directional_trend_grid(
        xs, ys, zs, gx, gy, a=2.0, b=0.5, max_cells_per_chunk=10_000
    )

    assert np.allclose(chunked, single)


def test_directional_grid_checks_cancellation_between_chunks():
    from geoviz import JobCancelled, directional_trend_grid

    class CancelOnSecondCheckpoint:
        calls = 0

        def raise_if_cancelled(self):
            self.calls += 1
            if self.calls == 2:
                raise JobCancelled("cancelled between chunks")

    token = CancelOnSecondCheckpoint()
    with pytest.raises(JobCancelled):
        directional_trend_grid(
            np.array([0.0, 1.0]),
            np.array([0.0, 1.0]),
            np.array([1.0, 2.0]),
            np.linspace(0.0, 1.0, 6),
            np.linspace(0.0, 1.0, 4),
            max_cells_per_chunk=2,
            cancellation_token=token,
        )
