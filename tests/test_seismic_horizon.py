import ast
import inspect
import time
from pathlib import Path

import numpy as np
import pytest

from geoviz_seismic.horizon import HorizonParser

_SEISMIC_VIEW = (
    Path(__file__).resolve().parents[1]
    / "packages"
    / "geoviz_seismic"
    / "geoviz_seismic"
    / "seismic_view.py"
)


def _make_axes():
    return {
        "ilines": np.arange(100, 110, dtype=np.int32),
        "xlines": np.arange(200, 220, dtype=np.int32),
        "nI": 10,
        "nX": 20,
    }


def _reference_quad_faces(nI: int, nX: int) -> np.ndarray:
    faces = []
    for i in range(nI - 1):
        for j in range(nX - 1):
            p0 = i * nX + j
            p1 = p0 + 1
            p2 = p0 + nX
            p3 = p2 + 1
            faces.append([p0, p1, p2])
            faces.append([p1, p3, p2])
    return np.asarray(faces, dtype=np.int64)


def test_horizon_quad_faces_is_vectorized_and_matches_nested_append():
    """#695: face construction must not be a Python list.append double loop."""
    from geoviz_seismic.horizon import horizon_quad_faces

    src = inspect.getsource(horizon_quad_faces)
    assert ".append(" not in src
    faces = horizon_quad_faces(4, 5)
    expected = _reference_quad_faces(4, 5)
    assert faces.shape == (2 * 3 * 4, 3)
    assert np.array_equal(faces, expected)

    horizon_quad_faces(200, 200)  # warmup
    t0 = time.perf_counter()
    big = horizon_quad_faces(1000, 1000)
    elapsed = time.perf_counter() - t0
    assert big.shape == (2 * 999 * 999, 3)
    # Nested Python append of ~2M faces is ~1s; vectorized stays well under this.
    assert elapsed < 0.2


def test_load_horizon_offloads_parse_and_edt():
    """#695: parse + fill_nearest must not run inside the GUI _load_horizon slot."""
    tree = ast.parse(_SEISMIC_VIEW.read_text(encoding="utf-8"), filename=str(_SEISMIC_VIEW))
    body = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "SeismicView":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "_load_horizon":
                    body = item
                    break
    assert body is not None
    dumped = ast.dump(body)
    assert "HorizonLoadWorker" in dumped
    assert "fill_nearest" not in dumped
    assert "parse" not in dumped


def test_horizon_load_worker_parses_and_fills(tmp_path):
    from geoviz_seismic.workers import HorizonLoadWorker

    path = tmp_path / "h.txt"
    path.write_text("100 200 1100\n101 200 1100\n", encoding="utf-8")
    axes = {
        "ilines": np.array([100, 101]),
        "xlines": np.array([200]),
        "nI": 2,
        "nX": 1,
    }
    worker = HorizonLoadWorker(str(path), axes, "h", (1.0, 0.9, 0.2, 0.6))
    results = []
    errors = []
    worker.done.connect(results.append)
    worker.error.connect(errors.append)
    worker.run()
    assert errors == []
    name, filled, color = results[0]
    assert name == "h"
    assert color == (1.0, 0.9, 0.2, 0.6)
    assert filled.shape == (2, 1)
    assert not np.any(np.isnan(filled))


def test_parse_dense_horizon(dense_horizon_path):
    parser = HorizonParser(dense_horizon_path, unit="ms")
    axes = _make_axes()
    grid = parser.parse(axes)
    assert grid.shape == (10, 20)
    assert not np.any(np.isnan(grid))


def test_parse_sparse_has_gaps(sparse_horizon_path):
    parser = HorizonParser(sparse_horizon_path, unit="ms")
    axes = _make_axes()
    grid = parser.parse(axes)
    assert grid.shape == (10, 20)
    assert np.any(np.isnan(grid))


def test_nearest_fill(sparse_horizon_path):
    parser = HorizonParser(sparse_horizon_path, unit="ms")
    axes = _make_axes()
    grid = parser.parse(axes)
    filled = parser.fill_nearest(grid, max_dist=0)
    assert not np.any(np.isnan(filled))


def test_sample_unit_conversion(dense_horizon_path):
    parser_ms = HorizonParser(dense_horizon_path, unit="ms")
    parser_samp = HorizonParser(dense_horizon_path, unit="sample", scale=0.5)
    axes = _make_axes()
    axes["dt_ms"] = 4.0
    grid_ms = parser_ms.parse(axes)
    grid_samp = parser_samp.parse(axes)
    assert not np.allclose(grid_ms, grid_samp)


def test_fill_rbf_respects_max_dist():
    """Gap pixels farther than max_dist from the nearest valid pick must
    stay NaN.

    Regression: the EDT was computed on the *valid* mask, so the distance
    at gap pixels was always 0 and ``(~mask) & (dist > max_dist)`` could
    never trigger — max_dist clipping was a no-op.
    """
    from scipy.ndimage import distance_transform_edt

    grid = np.full((30, 30), np.nan)
    grid[2:6, 2:6] = 100.0  # valid cluster in one corner, big gap elsewhere
    parser = HorizonParser("/dev/null")
    filled = parser.fill_rbf(grid, max_dist=2.0, neighbors=8)

    mask = np.isfinite(grid)
    dist = distance_transform_edt(~mask)
    # Valid picks are never turned into NaN.
    assert np.all(np.isfinite(filled[mask]))
    # Gap pixels beyond max_dist remain unfilled.
    far = (~mask) & (dist > 2.0)
    assert far.any()
    assert np.all(np.isnan(filled[far]))
    # Gap pixels within max_dist are filled.
    near = (~mask) & (dist <= 2.0)
    assert near.any()
    assert np.all(np.isfinite(filled[near]))


def test_fill_rbf_max_dist_zero_unlimited():
    """max_dist=0 keeps the unlimited-fill behaviour."""
    grid = np.full((10, 10), np.nan)
    grid[0, 0] = 1.0
    grid[0, 9] = 2.0
    grid[9, 0] = 3.0
    grid[9, 9] = 4.0
    parser = HorizonParser("/dev/null")
    filled = parser.fill_rbf(grid, max_dist=0, neighbors=4)
    assert not np.any(np.isnan(filled))
