"""Ordinary kriging (OK) baseline for factor-map interpolation.

Deterministic, pure-numpy geostatistical core (no Qt, no RNG):

- :func:`empirical_variogram` — pairwise half squared differences binned by
  distance. Exact duplicate sample locations are collapsed to their mean
  first so zero-distance pairs cannot contaminate the first lag bin.
- :func:`variogram_model_value` — spherical / exponential / gaussian
  semivariogram models with range / partial sill / nugget.
- :func:`fit_variogram` — bounded weighted least-squares fit of the model
  parameters to the empirical variogram (with sane fallback defaults when
  the data cannot support a fit).
- :func:`ordinary_kriging` — builds the augmented covariance system and
  solves it with ``numpy.linalg``, returning the prediction AND the kriging
  variance per target point.
- :func:`leave_one_out_predictions` — closed-form leave-one-out predictions
  at each sample location from a single inversion of the augmented system
  (fit the variogram once, invert once, no per-point re-solve).
- :func:`kriging_grid` — 2D wrapper for regular grids (matches the
  ``(len(grid_y), len(grid_x))`` convention of the other backends).

Numerical safety: duplicate points are deduplicated, a small ridge is added
to the covariance block when the system is singular (e.g. near-duplicate
points or a constant field), and all outputs are guaranteed finite.

Semivariogram conventions (standard geostatistics):

- ``range_`` — practical range (the distance at which the model reaches the
  sill: ``r`` for spherical, ``r/3`` for exponential, ``r/sqrt(3)`` for the
  Gaussian ``3h/r`` parametrizations below).
- ``sill`` — partial sill (the variance contribution of the model).
- ``nugget`` — y-intercept at zero lag (measurement noise / microscale
  variance). Total sill = ``nugget + sill``.

Models (``gamma(h)``, with ``r = range_``, ``s = sill``, ``ng = nugget``):

- spherical: ``ng + s * (1.5*(h/r) - 0.5*(h/r)**3)`` for ``h < r``, else ``ng + s``
- exponential: ``ng + s * (1 - exp(-3*h/r))``
- gaussian: ``ng + s * (1 - exp(-3*(h/r)**2))``
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.optimize import least_squares

SUPPORTED_MODELS = ("spherical", "exponential", "gaussian")

_MIN_SAMPLES = 2
_DEFAULT_RIDGE = 1e-9
_MAX_FIT_EVALUATIONS = 200


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dedupe_points(
    x: np.ndarray, y: np.ndarray, z: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Collapse exact duplicate (x, y) locations to their mean ``z``."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    z = np.asarray(z, dtype=np.float64)
    if x.ndim != 1 or y.ndim != 1 or z.ndim != 1:
        raise ValueError("sample coordinates must be 1-D arrays")
    if not (x.shape == y.shape == z.shape):
        raise ValueError("x, y, z must have the same length")
    pts = np.stack([x, y], axis=1)
    unique_pts, inverse = np.unique(pts, axis=0, return_inverse=True)
    if len(unique_pts) == len(pts):
        return x, y, z
    z_sum = np.zeros(len(unique_pts), dtype=np.float64)
    np.add.at(z_sum, inverse, z)
    z_mean = z_sum / np.bincount(inverse)
    return unique_pts[:, 0], unique_pts[:, 1], z_mean


def _gamma(h: np.ndarray, model: str, range_: float, sill: float, nugget: float) -> np.ndarray:
    """Semivariogram value(s) for the given model (h may be an array)."""
    r = float(range_)
    s = float(sill)
    ng = float(nugget)
    h = np.asarray(h, dtype=np.float64)
    if model == "spherical":
        hr = h / r
        g = np.where(hr < 1.0, s * (1.5 * hr - 0.5 * hr**3), s)
    elif model == "exponential":
        g = s * (1.0 - np.exp(-3.0 * h / r))
    elif model == "gaussian":
        g = s * (1.0 - np.exp(-3.0 * (h / r) ** 2))
    else:
        raise ValueError(f"unknown variogram model {model!r}; choose from {SUPPORTED_MODELS}")
    return ng + g


def _covariance(h: np.ndarray, model: str, range_: float, sill: float, nugget: float) -> np.ndarray:
    """Stationary covariance ``C(h) = total_sill - gamma(h)`` with ``C(0) = total_sill``."""
    total = float(sill) + float(nugget)
    h = np.asarray(h, dtype=np.float64)
    c = total - _gamma(h, model, range_, sill, nugget)
    c[h == 0.0] = total
    return c


def _pairwise_h(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Full (n, n) matrix of pairwise sample distances."""
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    return np.sqrt(dx * dx + dy * dy)


def _default_params(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> dict[str, float]:
    """Sane fallback variogram parameters when a fit is not possible."""
    n = len(z)
    h = _pairwise_h(x, y)
    iu = np.triu_indices(n, k=1)
    dmax = float(h[iu].max()) if n > 1 else 1.0
    if not np.isfinite(dmax) or dmax <= 0.0:
        dmax = 1.0
    zvar = float(np.var(z)) if n > 1 else 1.0
    if not np.isfinite(zvar) or zvar <= 0.0:
        zvar = 1.0
    return {"range": dmax, "sill": zvar, "nugget": 0.0}


# ---------------------------------------------------------------------------
# Variogram models
# ---------------------------------------------------------------------------


def variogram_model_value(
    h: float | np.ndarray,
    model: str = "spherical",
    range_: float = 1.0,
    sill: float = 1.0,
    nugget: float = 0.0,
) -> float | np.ndarray:
    """Semivariogram value at distance(s) ``h`` for the given model.

    Returns a float for scalar input, an ndarray for array input.
    At zero lag the value equals the nugget (0.0 with a zero nugget).
    """
    scalar = np.isscalar(h)
    out = _gamma(np.atleast_1d(h), model, range_, sill, nugget)
    return float(out[0]) if scalar else out


# ---------------------------------------------------------------------------
# Empirical variogram
# ---------------------------------------------------------------------------


def empirical_variogram(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    *,
    n_lags: int = 10,
    max_dist: float | None = None,
    min_pairs: int = 1,
) -> dict[str, Any]:
    """Bin pairwise semivariance (half squared difference) by distance.

    Returns a dict with ``lags`` (bin centers), ``gamma`` (mean semivariance
    per bin, ``NaN`` for empty bins), ``counts`` (pairs per bin), ``edges``
    and ``max_dist``. Exact duplicate locations are collapsed to their mean
    before binning.
    """
    x, y, z = _dedupe_points(x, y, z)
    n = len(z)
    if n < _MIN_SAMPLES:
        raise ValueError("empirical variogram needs at least 2 distinct sample points")
    h = _pairwise_h(x, y)
    half = 0.5 * (z[:, None] - z[None, :]) ** 2
    iu = np.triu_indices(n, k=1)
    h_vals = h[iu]
    g_vals = half[iu]
    max_d = float(h_vals.max())
    if max_d <= 0.0:
        raise ValueError("all sample points coincide; cannot bin a variogram")
    if max_dist is None:
        max_dist = max_d
    max_dist = float(max_dist)
    if max_dist <= 0.0:
        raise ValueError("max_dist must be positive")
    n_lags = max(2, int(n_lags))
    edges = np.linspace(0.0, max_dist, n_lags + 1)
    bins = np.clip(np.searchsorted(edges, h_vals, side="right") - 1, 0, n_lags - 1)
    counts = np.zeros(n_lags, dtype=np.int64)
    gamma = np.full(n_lags, np.nan)
    min_pairs = max(1, int(min_pairs))
    for k in range(n_lags):
        mask = bins == k
        nk = int(mask.sum())
        counts[k] = nk
        if nk >= min_pairs:
            gamma[k] = float(np.mean(g_vals[mask]))
    return {
        "lags": 0.5 * (edges[:-1] + edges[1:]),
        "gamma": gamma,
        "counts": counts,
        "edges": edges,
        "max_dist": max_dist,
    }


# ---------------------------------------------------------------------------
# Variogram fitting
# ---------------------------------------------------------------------------


def fit_variogram(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    *,
    model: str = "spherical",
    n_lags: int = 10,
    max_dist: float | None = None,
) -> dict[str, float]:
    """Weighted least-squares fit of ``(range, sill, nugget)``.

    Bins are weighted by their pair count. Falls back to sane defaults
    (range = max pairwise distance, sill = sample variance, nugget = 0) when
    fewer than two valid bins are available or the fit is degenerate.
    """
    if model not in SUPPORTED_MODELS:
        raise ValueError(f"unknown variogram model {model!r}; choose from {SUPPORTED_MODELS}")
    x, y, z = _dedupe_points(x, y, z)
    n = len(z)
    if n < _MIN_SAMPLES:
        raise ValueError("fit_variogram needs at least 2 distinct sample points")
    emp = empirical_variogram(x, y, z, n_lags=n_lags, max_dist=max_dist)
    valid = np.isfinite(emp["gamma"])
    if int(valid.sum()) < 2:
        return _default_params(x, y, z)
    lags = emp["lags"][valid]
    obs = emp["gamma"][valid]
    weights = np.sqrt(emp["counts"][valid].astype(np.float64))
    z_var = float(np.var(z))
    z_max_gamma = float(obs.max())
    h_max = float(lags.max())

    # Initial guess + bounds: range ~ half the max lag, sill ~ max observed
    # semivariance (capped by the data variance), nugget ~ first-bin value.
    x0 = np.array(
        [
            max(h_max * 0.5, h_max * 1e-3),
            max(z_max_gamma - float(obs[0]), z_var * 1e-3),
            min(float(obs[0]), z_max_gamma),
        ]
    )
    lo = np.array([h_max * 1e-4, 0.0, 0.0])
    hi = np.array([max(h_max * 3.0, h_max * 1e-3), max(z_var * 10.0, z_max_gamma), z_max_gamma])
    # scipy requires lo < hi strictly; degenerate fields (e.g. constant z)
    # collapse bounds to a point, so widen hi by a small epsilon.
    hi = np.maximum(hi, lo + 1e-12)

    def residual(params: np.ndarray) -> np.ndarray:
        r, s, ng = params
        return weights * (_gamma(lags, model, r, s, ng) - obs)

    result = least_squares(residual, x0, bounds=(lo, hi), max_nfev=_MAX_FIT_EVALUATIONS)
    r, s, ng = (float(v) for v in result.x)
    if not (np.isfinite(r) and np.isfinite(s) and np.isfinite(ng)):
        return _default_params(x, y, z)
    return {"range": r, "sill": max(s, 0.0), "nugget": max(ng, 0.0)}


# ---------------------------------------------------------------------------
# Ordinary kriging
# ---------------------------------------------------------------------------


def _solve_augmented(aug: np.ndarray, rhs: np.ndarray, total_sill: float, ridge: float) -> np.ndarray:
    """Solve the augmented kriging system; retry with a ridge on singularity."""
    try:
        sol = np.linalg.solve(aug, rhs)
        if np.all(np.isfinite(sol)):
            return sol
    except np.linalg.LinAlgError:
        pass
    n = len(aug) - 1
    aug_r = aug.copy()
    aug_r[:n, :n] = aug_r[:n, :n] + ridge * max(float(total_sill), 1.0) * np.eye(n)
    try:
        return np.linalg.solve(aug_r, rhs)
    except np.linalg.LinAlgError as exc:  # pragma: no cover - pathological input only
        raise ValueError("kriging system is singular even after ridge regularization") from exc


def ordinary_kriging(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    target_x: np.ndarray,
    target_y: np.ndarray,
    *,
    variogram_model: str = "spherical",
    range_: float | None = None,
    sill: float | None = None,
    nugget: float | None = None,
    ridge: float = _DEFAULT_RIDGE,
) -> tuple[np.ndarray, np.ndarray]:
    """Ordinary kriging prediction and kriging variance per target point.

    Args:
        x, y, z: 1-D sample coordinates and observed values. Exact duplicate
            locations are collapsed to their mean before solving.
        target_x, target_y: 1-D target coordinates (same length).
        variogram_model: ``"spherical"``, ``"exponential"`` or ``"gaussian"``.
        range_, sill, nugget: explicit variogram parameters. Any ``None``
            parameter is resolved by :func:`fit_variogram` from the samples.
        ridge: relative ridge added to the covariance diagonal if the system
            is singular (near-duplicate points / constant field).

    Returns:
        ``(prediction, variance)`` — 1-D arrays of the same length as the
        targets. Both are finite; variance is clipped at 0.
    """
    if variogram_model not in SUPPORTED_MODELS:
        raise ValueError(f"unknown variogram model {variogram_model!r}; choose from {SUPPORTED_MODELS}")
    x, y, z = _dedupe_points(x, y, z)
    n = len(z)
    if n < _MIN_SAMPLES:
        raise ValueError("ordinary kriging needs at least 2 distinct sample points")
    tx = np.asarray(target_x, dtype=np.float64).ravel()
    ty = np.asarray(target_y, dtype=np.float64).ravel()
    if tx.shape != ty.shape:
        raise ValueError("target_x and target_y must have the same length")
    m = len(tx)

    if any(p is None for p in (range_, sill, nugget)):
        fitted = fit_variogram(x, y, z, model=variogram_model)
        if range_ is None:
            range_ = fitted["range"]
        if sill is None:
            sill = fitted["sill"]
        if nugget is None:
            nugget = fitted["nugget"]
    if range_ is None:
        range_ = _default_params(x, y, z)["range"]
    if sill is None:
        sill = _default_params(x, y, z)["sill"]
    if nugget is None:
        nugget = 0.0
    range_ = float(range_)
    sill = float(sill)
    nugget = float(nugget)
    if range_ <= 0.0 or sill < 0.0 or nugget < 0.0:
        raise ValueError("variogram parameters must satisfy range > 0, sill >= 0, nugget >= 0")
    total_sill = sill + nugget

    # Pairwise sample covariance matrix (n x n) and sample-to-target
    # covariance (n x m) — the RHS of the kriging system.
    h = _pairwise_h(x, y)
    a_mat = _covariance(h, variogram_model, range_, sill, nugget)
    t_h = np.sqrt((x[:, None] - tx[None, :]) ** 2 + (y[:, None] - ty[None, :]) ** 2)
    c_mat = _covariance(t_h, variogram_model, range_, sill, nugget)

    aug = np.empty((n + 1, n + 1), dtype=np.float64)
    aug[:n, :n] = a_mat
    aug[:n, n] = 1.0
    aug[n, :n] = 1.0
    aug[n, n] = 0.0
    rhs = np.empty((n + 1, m), dtype=np.float64)
    rhs[:n, :] = c_mat
    rhs[n, :] = 1.0

    sol = _solve_augmented(aug, rhs, total_sill, ridge)
    weights = sol[:n, :]
    mu = sol[n, :]
    pred = weights.T @ z
    variance = total_sill - (np.sum(weights * c_mat, axis=0) + mu)
    pred = np.asarray(pred, dtype=np.float64)
    variance = np.asarray(variance, dtype=np.float64)
    variance = np.where(np.isfinite(variance) & (variance >= 0.0), variance, 0.0)
    return pred, variance


def leave_one_out_predictions(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    *,
    variogram_model: str = "spherical",
    range_: float | None = None,
    sill: float | None = None,
    nugget: float | None = None,
    ridge: float = _DEFAULT_RIDGE,
) -> tuple[np.ndarray, np.ndarray]:
    """Closed-form leave-one-out predictions at each sample location.

    The variogram is fitted at most ONCE (any ``None`` parameter is resolved
    from the full sample set), the augmented kriging system is built and
    inverted once, and every leave-one-out prediction is derived from that
    single inverse in O(n) each:

    .. math:: yhat_i = - sum_{j != i} V[j, i] * z_j / V[i, i]

    where ``V = M^{-1}`` and ``M = [[A, 1], [1^T, 0]]`` is the augmented
    system of :func:`ordinary_kriging` (standard cross-validation in a unique
    neighborhood, cf. Dubrule 1983). This avoids re-fitting the variogram and
    re-solving an (n-1)-sized system for every left-out point.

    Returns ``(predictions, z_dedup)`` aligned with the deduplicated samples
    (exact duplicate locations are collapsed to their mean, exactly as in
    :func:`ordinary_kriging`). Raises ``ValueError`` when the system stays
    singular even after ridge regularization or no finite prediction can be
    formed for a sample.
    """
    if variogram_model not in SUPPORTED_MODELS:
        raise ValueError(f"unknown variogram model {variogram_model!r}; choose from {SUPPORTED_MODELS}")
    x, y, z = _dedupe_points(x, y, z)
    n = len(z)
    if n < _MIN_SAMPLES:
        raise ValueError("leave-one-out needs at least 2 distinct sample points")

    if any(p is None for p in (range_, sill, nugget)):
        fitted = fit_variogram(x, y, z, model=variogram_model)
        if range_ is None:
            range_ = fitted["range"]
        if sill is None:
            sill = fitted["sill"]
        if nugget is None:
            nugget = fitted["nugget"]
    if range_ is None:
        range_ = _default_params(x, y, z)["range"]
    if sill is None:
        sill = _default_params(x, y, z)["sill"]
    if nugget is None:
        nugget = 0.0
    range_ = float(range_)
    sill = float(sill)
    nugget = float(nugget)
    if range_ <= 0.0 or sill < 0.0 or nugget < 0.0:
        raise ValueError("variogram parameters must satisfy range > 0, sill >= 0, nugget >= 0")
    total_sill = sill + nugget

    h = _pairwise_h(x, y)
    a_mat = _covariance(h, variogram_model, range_, sill, nugget)
    aug = np.empty((n + 1, n + 1), dtype=np.float64)
    aug[:n, :n] = a_mat
    aug[:n, n] = 1.0
    aug[n, :n] = 1.0
    aug[n, n] = 0.0

    # Solving against the identity returns M^{-1} through the same
    # ridge-fallback path as ordinary_kriging.
    v = _solve_augmented(aug, np.eye(n + 1), total_sill, ridge)
    b = v[:n, :n]
    diag = np.diag(b)
    if not np.all(np.abs(diag) > 1e-14):
        raise ValueError("leave-one-out system degenerate: zero diagonal in the inverse")
    # sum_{j != i} V[j, i] * z_j = (B^T z)_i - B[i, i] * z_i
    numer = b.T @ z - diag * z
    preds = -numer / diag
    if not np.all(np.isfinite(preds)):
        raise ValueError("leave-one-out predictions are not finite")
    return preds, z


def kriging_grid(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    grid_x: np.ndarray,
    grid_y: np.ndarray,
    **kwargs: Any,
) -> tuple[np.ndarray, np.ndarray]:
    """Ordinary kriging onto a regular grid.

    Returns ``(grid_z, grid_var)`` with shape ``(len(grid_y), len(grid_x))``,
    matching the convention of the other interpolation backends.
    """
    gx = np.asarray(grid_x, dtype=np.float64)
    gy = np.asarray(grid_y, dtype=np.float64)
    xx, yy = np.meshgrid(gx, gy)
    pred, variance = ordinary_kriging(x, y, z, xx.ravel(), yy.ravel(), **kwargs)
    return pred.reshape(xx.shape), variance.reshape(xx.shape)


__all__ = [
    "SUPPORTED_MODELS",
    "empirical_variogram",
    "fit_variogram",
    "kriging_grid",
    "leave_one_out_predictions",
    "ordinary_kriging",
    "variogram_model_value",
]
