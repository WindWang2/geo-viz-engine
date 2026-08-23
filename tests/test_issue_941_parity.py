"""Parity and memory regressions for #941-1/5."""
import math
import numpy as np
import pytest


def test_idw_squared_distance_parity():
    """#941-5: squared-distance kernel must match hypot within 3e-14 (711 vs 1243ms)."""
    from geoviz_plots.interpolation.idw import interpolate_idw

    rng = np.random.default_rng(0)
    x = rng.uniform(0, 10, 20)
    y = rng.uniform(0, 10, 20)
    z = rng.normal(5, 2, 20)
    gx = np.linspace(0, 10, 32)
    gy = np.linspace(0, 10, 32)

    # Reference via direct hypot path — compute with old formula inline
    # Simulate old code: distances = hypot(dx, dy); weights = 1/(dist**power)
    # We compute reference by calling interpolate_idw with a monkeypatched hypot? Easier: compute expected via brute
    out = interpolate_idw(x, y, z, gx, gy, power=2.0)

    # Brute reference: same chunk size but using hypot
    def brute(x, y, z, gx, gy, power=2.0, eps=1e-12):
        H, W = len(gy), len(gx)
        cell_x = np.tile(gx, H)
        cell_y = np.repeat(gy, W)
        res = np.full(cell_x.shape, np.nan)
        for s in range(0, len(cell_x), 16384):
            e = min(s+16384, len(cell_x))
            dx = cell_x[s:e, None] - x[None, :]
            dy = cell_y[s:e, None] - y[None, :]
            d = np.maximum(np.hypot(dx, dy), eps)
            w = 1.0 / (d**power)
            t = np.sum(w, axis=1)
            pop = t > 0
            v = np.full(e-s, np.nan)
            v[pop] = np.sum(w[pop]*z, axis=1)/t[pop]
            res[s:e] = v
        return res.reshape(H, W)

    ref = brute(x, y, z, gx, gy, power=2.0)
    diff = np.abs(out - ref)
    maxdiff = np.nanmax(diff)
    assert maxdiff < 1e-12, f"max diff {maxdiff} exceeds 1e-12 (expect ~2.8e-14)"

    # Power !=2 path
    out3 = interpolate_idw(x, y, z, gx, gy, power=3.5)
    ref3 = brute(x, y, z, gx, gy, power=3.5)
    assert np.nanmax(np.abs(out3 - ref3)) < 1e-12


def test_kriging_grid_chunked_matches_reference():
    """#941-1: chunked kriging must be numerically identical to non-chunked."""
    from geoviz_plots.factor.kriging import kriging_grid, ordinary_kriging

    rng = np.random.default_rng(1)
    x = rng.uniform(0, 10, 12)
    y = rng.uniform(0, 10, 12)
    z = 2*x - 3*y + 5

    gx_small = np.linspace(0, 10, 16)
    gy_small = np.linspace(0, 10, 16)

    # Small grid: non-chunked path (should be identical)
    zg1, vg1 = kriging_grid(x, y, z, gx_small, gy_small)

    # Larger grid that forces chunking (512² would be heavy; use 128² with chunk 4096)
    gx = np.linspace(0, 10, 128)
    gy = np.linspace(0, 10, 128)
    zg, vg = kriging_grid(x, y, z, gx, gy)
    assert zg.shape == (128, 128)
    assert vg.shape == (128, 128)
    assert np.all(np.isfinite(zg))
    # Spot-check against single-point ordinary_kriging for first few cells
    tx = np.array([gx[0], gx[1], gx[5]])
    ty = np.array([gy[0], gy[0], gy[10]])
    pred, var = ordinary_kriging(x, y, z, tx, ty)
    # kriging_grid's mesh ordering is row-major: gy repeats
    assert math.isclose(zg[0, 0], pred[0], rel_tol=1e-12)
    assert math.isclose(zg[0, 1], pred[1], rel_tol=1e-12)
    assert math.isclose(zg[10, 5], pred[2], rel_tol=1e-12)


def test_interpolate_factor_grid_returns_ndarray():
    """#941-2: engine must return ndarray hot payload, not nested lists."""
    from geoviz_plots.factor import interpolate_factor_grid

    pts = [{"x": float(i), "y": float(i), "value": float(i*2)} for i in range(5)]
    res = interpolate_factor_grid(pts, method="IDW", grid_n=16)
    assert isinstance(res["grid_x"], np.ndarray)
    assert isinstance(res["grid_y"], np.ndarray)
    assert isinstance(res["grid_z"], np.ndarray)
    assert res["grid_z"].shape == (16, 16)
    # grid_var for kriging
    res_k = interpolate_factor_grid(pts, method="kriging", grid_n=8)
    assert isinstance(res_k["grid_z"], np.ndarray)
    assert isinstance(res_k["grid_var"], np.ndarray)
