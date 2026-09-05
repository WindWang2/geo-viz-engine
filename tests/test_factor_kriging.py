"""Ordinary-kriging baseline tests (geoviz_plots.factor.kriging).

Analytical fixtures only — no RNG, no Qt:

- exact interpolation at sample points (nugget = 0);
- a linear field predicted against an independently computed closed-form
  reference (hand-derived ``z = 2x - 3y + 5``);
- a covariance-combination field that ordinary kriging reproduces exactly
  (centered weights, gaussian covariance, zero nugget);
- duplicate-point handling, determinism, finite outputs on arbitrary
  points, variogram sanity, and the factor-grid wiring.
"""

import math

import numpy as np
import pytest

from geoviz_plots.factor import interpolate_factor_grid, method_to_backend, mvp_note_for
from geoviz_plots.factor.kriging import (
    SUPPORTED_MODELS,
    empirical_variogram,
    fit_variogram,
    kriging_grid,
    ordinary_kriging,
    variogram_model_value,
)


# ---------------------------------------------------------------------------
# Variogram model sanity
# ---------------------------------------------------------------------------


def test_variogram_zero_lag_equals_nugget():
    """At zero lag the semivariogram equals the nugget (0 with a zero nugget)."""
    for model in SUPPORTED_MODELS:
        assert variogram_model_value(0.0, model, range_=3.0, sill=2.0, nugget=0.5) == pytest.approx(0.5)
        assert variogram_model_value(0.0, model, range_=3.0, sill=2.0, nugget=0.0) == pytest.approx(0.0)


def test_variogram_reaches_sill_beyond_range():
    """Spherical saturates at nugget + sill for h >= range; exp/gauss are monotone
    and approach the sill asymptotically."""
    for h in (3.0, 10.0, 1e3):
        assert variogram_model_value(h, "spherical", range_=3.0, sill=2.0, nugget=0.5) == pytest.approx(2.5)
    for model in ("exponential", "gaussian"):
        vals = [
            float(variogram_model_value(h, model, range_=3.0, sill=2.0, nugget=0.0))
            for h in (0.1, 1.0, 3.0, 10.0, 1e3)
        ]
        assert vals == sorted(vals)  # monotone non-decreasing
        assert vals[0] <= 2.0  # well below the sill at short lags
        assert vals[-1] == pytest.approx(2.0, abs=1e-6)  # asymptotic sill


def test_empirical_variogram_linear_field_sane():
    """Bins are complete (sum of counts = n(n-1)/2) and grow with distance."""
    g = np.linspace(0.0, 9.0, 4)
    xx, yy = np.meshgrid(g, g)
    x, y = xx.ravel(), yy.ravel()
    z = 2.0 * x - 3.0 * y + 5.0
    emp = empirical_variogram(x, y, z, n_lags=4)
    n = len(z)
    assert int(emp["counts"].sum()) == n * (n - 1) // 2
    valid = np.isfinite(emp["gamma"])
    assert int(valid.sum()) >= 2  # enough populated bins to be meaningful
    gammas = emp["gamma"][valid]
    assert (np.diff(gammas) >= 0).all()  # growing with distance


def test_empirical_variogram_collapses_exact_duplicates():
    """Exact duplicate locations are collapsed before binning."""
    pts = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 0.0], [2.0, 1.0], [3.0, 2.0]])
    z = np.array([0.0, 5.0, 7.0, 3.0, 8.0])
    emp_dup = empirical_variogram(pts[:, 0], pts[:, 1], z, n_lags=4)
    # Manually deduped input -> identical bins
    emp_clean = empirical_variogram(
        np.array([0.0, 1.0, 2.0, 3.0]),
        np.array([0.0, 0.0, 1.0, 2.0]),
        np.array([0.0, 6.0, 3.0, 8.0]),  # (1,0) averaged: (5+7)/2
        n_lags=4,
    )
    assert np.allclose(emp_dup["gamma"], emp_clean["gamma"], equal_nan=True)
    assert np.array_equal(emp_dup["counts"], emp_clean["counts"])


def test_empirical_variogram_drops_pairs_beyond_max_dist():
    """#118: pairs farther than max_dist must be dropped, not clipped into
    the last lag bin. Four near points (pairwise h <= sqrt(2) < 1.8) plus
    one far point (h ~ 100) with max_dist=2.0: the far pairs used to land in
    the last bin (edges step 0.2, bin 9 = (1.8, 2.0]) and pollute its
    semivariance; the last bin must now stay empty (NaN gamma)."""
    x = np.array([0.0, 1.0, 0.0, 1.0, 100.0])
    y = np.array([0.0, 0.0, 1.0, 1.0, 0.0])
    z = np.array([1.0, 2.0, 3.0, 4.0, 50.0])
    emp = empirical_variogram(x, y, z, n_lags=10, max_dist=2.0)
    # Only the 6 near-cluster pairs are binned; the 4 far pairs (h ~ 100)
    # are out of range and must not inflate any bin.
    assert int(emp["counts"].sum()) == 6
    assert int(emp["counts"][-1]) == 0
    assert np.isnan(emp["gamma"][-1])
    # The populated bins reflect only near-pair semivariances (max ~ 0.5*9).
    valid = emp["gamma"][np.isfinite(emp["gamma"])]
    assert valid.max() < 5.0


def test_fit_variogram_returns_finite_positive_params():
    """Fitted range/sill/nugget are finite and non-negative."""
    rng = np.random.default_rng(11)
    x = rng.uniform(0.0, 10.0, 20)
    y = rng.uniform(0.0, 10.0, 20)
    z = 2.0 * x - 3.0 * y + 5.0
    for model in SUPPORTED_MODELS:
        params = fit_variogram(x, y, z, model=model)
        assert set(params) == {"range", "sill", "nugget"}
        assert all(np.isfinite(list(params.values())))
        assert params["range"] > 0.0 and params["sill"] >= 0.0 and params["nugget"] >= 0.0


def test_fit_variogram_degenerate_returns_defaults():
    """Too few points fall back to sane defaults instead of crashing."""
    params = fit_variogram(np.array([0.0, 1.0]), np.array([0.0, 0.0]), np.array([1.0, 2.0]))
    assert params["range"] == pytest.approx(1.0)  # max pairwise distance
    assert params["sill"] == pytest.approx(0.25)  # np.var([1, 2])
    assert params["nugget"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Ordinary kriging: analytical fixtures
# ---------------------------------------------------------------------------


def test_exact_interpolation_at_sample_points():
    """With a zero nugget, OK reproduces the observed values at the samples."""
    rng = np.random.default_rng(7)
    x = rng.uniform(0.0, 10.0, 12)
    y = rng.uniform(0.0, 10.0, 12)
    z = 2.0 * x - 3.0 * y + 5.0
    pred, var = ordinary_kriging(
        x, y, z, x, y,
        variogram_model="spherical", range_=10.0, sill=float(np.var(z)), nugget=0.0,
    )
    assert np.allclose(pred, z, atol=1e-8)
    assert np.allclose(var, 0.0, atol=1e-8)


def test_linear_field_against_independent_reference():
    """A smooth linear field is predicted within a tight tolerance of the
    hand-derived closed form ``z = 2x - 3y + 5`` on interior targets."""
    g = np.linspace(0.0, 9.0, 4)
    xx, yy = np.meshgrid(g, g)
    x, y = xx.ravel(), yy.ravel()
    z = 2.0 * x - 3.0 * y + 5.0
    tg = np.linspace(1.0, 8.0, 5)
    tx, ty = np.meshgrid(tg, tg)
    tx, ty = tx.ravel(), ty.ravel()
    pred, _ = ordinary_kriging(x, y, z, tx, ty, variogram_model="gaussian")
    reference = 2.0 * tx - 3.0 * ty + 5.0
    rel_err = np.abs(pred - reference) / np.ptp(z)
    assert float(rel_err.max()) < 0.01  # < 1% of the field range
    assert float(rel_err.mean()) < 0.005


def test_covariance_reproduction_closed_form():
    """OK reproduces a covariance-combination field exactly (known closed form).

    With a zero nugget, ordinary kriging is exact on the linear span of the
    covariance functions centered at the samples (weights sum to zero), so the
    prediction at any interior target equals the independently computed
    combination ``sum_i w_i * C(|t - s_i|)``.
    """
    rng = np.random.default_rng(3)
    sx = rng.uniform(0.0, 6.0, 8)
    sy = rng.uniform(0.0, 6.0, 8)
    weights = rng.uniform(-1.0, 1.0, 8)
    weights = weights - weights.mean()  # centered: reproduces under OK
    range_, sill = 3.0, 2.0

    def cov_gauss(h):
        return sill * np.exp(-3.0 * (np.asarray(h, dtype=np.float64) / range_) ** 2)

    def field(px, py):
        px = np.asarray(px, dtype=np.float64)
        py = np.asarray(py, dtype=np.float64)
        out = np.zeros_like(px)
        for i in range(8):
            h = np.sqrt((px - sx[i]) ** 2 + (py - sy[i]) ** 2)
            out += weights[i] * cov_gauss(h)
        return out

    sz = field(sx, sy)
    tx = rng.uniform(0.5, 5.5, 20)
    ty = rng.uniform(0.5, 5.5, 20)
    pred, _ = ordinary_kriging(
        sx, sy, sz, tx, ty,
        variogram_model="gaussian", range_=range_, sill=sill, nugget=0.0,
    )
    assert np.allclose(pred, field(tx, ty), atol=1e-9)


def test_finite_output_on_arbitrary_points():
    """Predictions and variances are finite everywhere, including far outside."""
    rng = np.random.default_rng(5)
    x = rng.uniform(0.0, 10.0, 15)
    y = rng.uniform(0.0, 10.0, 15)
    z = 3.0 * x + y - 4.0
    tx = np.concatenate([rng.uniform(-100.0, 100.0, 30), [5.0]])
    ty = np.concatenate([rng.uniform(-100.0, 100.0, 30), [5.0]])
    pred, var = ordinary_kriging(x, y, z, tx, ty, variogram_model="exponential")
    assert np.all(np.isfinite(pred))
    assert np.all(np.isfinite(var))
    assert np.all(var >= 0.0)


def test_duplicate_point_handling():
    """Exact duplicates are averaged; the result equals kriging on deduped input."""
    x = np.array([0.0, 1.0, 1.0, 2.0])
    y = np.array([0.0, 0.0, 0.0, 0.0])
    z = np.array([0.0, 5.0, 7.0, 10.0])
    tx = np.array([1.0, 1.5])
    ty = np.array([0.0, 0.0])
    pred, var = ordinary_kriging(x, y, z, tx, ty, variogram_model="spherical")
    # Deduped reference: (1,0) -> 6.0, and the target sits on a sample
    pred_ref, var_ref = ordinary_kriging(
        np.array([0.0, 1.0, 2.0]),
        np.array([0.0, 0.0, 0.0]),
        np.array([0.0, 6.0, 10.0]),
        tx, ty, variogram_model="spherical",
    )
    assert np.allclose(pred, pred_ref)
    assert np.allclose(var, var_ref)
    assert np.allclose(pred[0], 6.0, atol=1e-8)  # exact at the averaged sample
    assert np.allclose(var[0], 0.0, atol=1e-8)


def test_determinism_same_input_same_output():
    """Identical inputs give bit-identical outputs (no RNG anywhere)."""
    rng = np.random.default_rng(9)
    x = rng.uniform(0.0, 10.0, 12)
    y = rng.uniform(0.0, 10.0, 12)
    z = 2.0 * x - y + 1.0
    tx = rng.uniform(0.0, 10.0, 20)
    ty = rng.uniform(0.0, 10.0, 20)
    p1, v1 = ordinary_kriging(x, y, z, tx, ty, variogram_model="exponential")
    p2, v2 = ordinary_kriging(x, y, z, tx, ty, variogram_model="exponential")
    assert np.array_equal(p1, p2)
    assert np.array_equal(v1, v2)


def test_constant_field_is_finite_and_constant():
    """A constant field (singular covariance) stays finite via ridge + sum-to-1."""
    g = np.linspace(0.0, 2.0, 3)
    xx, yy = np.meshgrid(g, g)
    x, y = xx.ravel(), yy.ravel()
    z = np.full(len(x), 7.0)
    pred, var = ordinary_kriging(x, y, z, np.array([0.5, 1.5]), np.array([0.5, 1.5]))
    assert np.allclose(pred, 7.0, atol=1e-6)
    assert np.all(np.isfinite(var))
    assert np.all(var >= 0.0)


def test_kriging_grid_shapes_and_finiteness():
    """kriging_grid returns (len(grid_y), len(grid_x)) finite arrays."""
    rng = np.random.default_rng(2)
    x = rng.uniform(0.0, 10.0, 10)
    y = rng.uniform(0.0, 10.0, 10)
    z = 2.0 * x - 3.0 * y + 5.0
    grid_z, grid_var = kriging_grid(x, y, z, np.linspace(0.0, 10.0, 9), np.linspace(0.0, 10.0, 7))
    assert grid_z.shape == (7, 9)
    assert grid_var.shape == (7, 9)
    assert np.all(np.isfinite(grid_z))
    assert np.all(np.isfinite(grid_var))


# ---------------------------------------------------------------------------
# factor/interpolation.py wiring
# ---------------------------------------------------------------------------


def test_method_to_backend_resolves_kriging():
    """Both 克里金 labels route to the real kriging backend (#1049)."""
    assert method_to_backend("kriging") == "kriging"
    assert method_to_backend("IDW") == "idw"
    assert method_to_backend("克里金(MVP·线性)") == "kriging"  # legacy alias, real kriging
    assert mvp_note_for("kriging") is None  # real kriging is not an MVP placeholder


def test_interpolate_factor_grid_kriging_backend():
    """interpolate_factor_grid(method='kriging') returns a grid dict with finite grid_z plus per-cell kriging variance."""
    pts = [
        {"x": 0.0, "y": 0.0, "value": 0.0},
        {"x": 10.0, "y": 0.0, "value": 10.0},
        {"x": 0.0, "y": 10.0, "value": 5.0},
        {"x": 10.0, "y": 10.0, "value": 15.0},
    ]
    result = interpolate_factor_grid(pts, method="kriging", grid_n=10)
    assert result["backend"] == "kriging"
    assert result["method"] == "kriging"
    assert result["grid_n"] == 10
    # #941-1/2: engine now returns ndarray for the hot payload.
    for key, arr in (("grid_z", result["grid_z"]), ("grid_var", result["grid_var"])):
        if isinstance(arr, np.ndarray):
            assert arr.shape == (10, 10)
            assert np.isfinite(arr).all()
        else:
            assert len(arr) == 10 and len(arr[0]) == 10
            assert all(isinstance(v, float) or v is None for row in arr for v in row)
            assert all(math.isfinite(v) for row in arr for v in row if v is not None)
    assert result["variance_min"] is not None and result["variance_max"] is not None
    assert result["variance_min"] <= result["variance_max"]
    assert "mvp_note" not in result  # real kriging carries no MVP caveat
    assert result["r_squared"] is None or math.isfinite(result["r_squared"])


# --- finiteness contract (#145) -----------------------------------------------


def test_kriging_filters_nonfinite_samples():
    """NaN coordinates/values must not poison the system into a NaN surface
    with variance washed to 0 (#145): non-finite samples are dropped, the
    remaining ones interpolate finitely."""
    rng = np.random.default_rng(11)
    x = rng.uniform(0, 100, 40)
    y = rng.uniform(0, 100, 40)
    z = np.sin(x / 10) + np.cos(y / 8)
    x[5] = np.nan
    z[9] = np.inf
    tx = np.linspace(10, 90, 25)
    pred, var = ordinary_kriging(x, y, z, tx, tx)
    assert np.all(np.isfinite(pred))
    assert np.all(np.isfinite(var))
    assert np.all(var >= 0.0)


def test_kriging_all_nan_input_raises():
    """With no usable samples the engine must fail loudly (the documented
    contract is finite outputs — never a NaN surface wearing variance 0)."""
    x = np.array([1.0, 2.0, 3.0, 4.0])
    y = np.array([1.0, 2.0, 3.0, 4.0])
    z = np.array([np.nan, np.nan, np.nan, np.nan])
    with pytest.raises(ValueError):
        ordinary_kriging(x, y, z, np.array([2.0]), np.array([2.0]))
