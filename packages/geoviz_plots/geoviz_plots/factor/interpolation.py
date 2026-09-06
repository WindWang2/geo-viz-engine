"""Factor-map interpolation core: IDW / SciPy / directional-trend / kriging dispatch.

Promoted from ``paleo_workbench/workflow/factor_interpolation.py`` (Phase-2
promote-down). Pure numpy + the ``geoviz`` facade; the
``FactorMapTask`` / ``ProjectDocument`` -mutating adapters
(``apply_interpolation_to_task``, ``batch_prepare_factor_maps``) stay in
Workbench.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from typing import Any

import numpy as np

from geoviz_plots.factor.directional import (
    DEFAULT_SEMI_MAJOR,
    DEFAULT_SEMI_MINOR,
    extract_xy_z_weights,
)

GENERATOR_VERSION = "factor-interp-v1"
DEFAULT_FACTOR_TYPES = ("地层厚度", "砂岩含量", "砂地比", "泥岩含量")
DEFAULT_GRID_N = 50
MAX_LOO_SAMPLES = 64

# UI labels (tokens.INTERPOLATION_METHODS) -> engine backends.
# ISS-KRIG-01 resolved (#1049): both 克里金 labels — including the legacy
# "克里金(MVP·线性)" alias — dispatch to the REAL variogram-based
# ordinary-kriging backend "kriging" (geoviz_plots.factor.kriging). The
# SciPy linear-triangulation backend stays reachable under its own engine
# name "linear" for callers that explicitly want it.
_METHOD_BACKEND: dict[str, str] = {
    "IDW": "idw",
    "idw": "idw",
    "克里金": "kriging",
    "克里金(MVP·线性)": "kriging",
    "kriging": "kriging",
    "linear": "linear",
    "样条": "cubic",
    "方向趋势": "directional",
    "directional": "directional",
    "方向加权": "directional",
    "mock": "idw",
}

_BACKEND_MVP_NOTES: dict[str, str] = {
    "linear": "MVP：SciPy linear 三角剖分插值，非变差函数克里金（ISS-KRIG-01）",
}


def method_to_backend(method: str) -> str:
    """Resolve a UI method label to an engine backend name (default ``idw``)."""
    return _METHOD_BACKEND.get(method, "idw")


def mvp_note_for(backend: str) -> str | None:
    """Return the MVP caveat note for a backend, or ``None`` if none applies."""
    return _BACKEND_MVP_NOTES.get(backend)


def _snapshot_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def extract_xy_values(
    sample_points: list[dict[str, Any]] | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pull (x, y, value) arrays from factor sample_points records.

    Accepts ``x``/``y`` or ``lng``/``lat`` keys; ``value`` / ``z`` / ``v`` for
    the scalar. Skips non-finite entries.
    """
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    for pt in sample_points or []:
        if not isinstance(pt, dict):
            continue
        try:
            if "x" in pt and "y" in pt:
                x = float(pt["x"])
                y = float(pt["y"])
            elif "lng" in pt and "lat" in pt:
                x = float(pt["lng"])
                y = float(pt["lat"])
            else:
                continue
            z = float(pt.get("value", pt.get("z", pt.get("v"))))
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
            continue
        xs.append(x)
        ys.append(y)
        zs.append(z)
    return (
        np.asarray(xs, dtype=np.float64),
        np.asarray(ys, dtype=np.float64),
        np.asarray(zs, dtype=np.float64),
    )


def _grid_axes(
    x: np.ndarray, y: np.ndarray, grid_n: int
) -> tuple[np.ndarray, np.ndarray]:
    n = max(2, int(grid_n))
    if len(x) == 0:
        return np.linspace(0.0, 1.0, n), np.linspace(0.0, 1.0, n)
    pad_x = max((float(x.max()) - float(x.min())) * 0.05, 1e-6)
    pad_y = max((float(y.max()) - float(y.min())) * 0.05, 1e-6)
    grid_x = np.linspace(float(x.min()) - pad_x, float(x.max()) + pad_x, n)
    grid_y = np.linspace(float(y.min()) - pad_y, float(y.max()) + pad_y, n)
    return grid_x, grid_y


def _run_grid(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    grid_x: np.ndarray,
    grid_y: np.ndarray,
    *,
    backend: str,
    power: float,
    fault_polylines: list[list[tuple[float, float]]] | None = None,
    azimuth_deg: float = 0.0,
    semi_major: float = DEFAULT_SEMI_MAJOR,
    semi_minor: float = DEFAULT_SEMI_MINOR,
    q: np.ndarray | None = None,
    b_i: np.ndarray | None = None,
    cancellation_token=None,
    want_variance: bool = False,
    interp_status: dict[str, Any] | None = None,
    variogram_model: str = "spherical",
    variogram_range: float | None = None,
    variogram_nugget: float | None = None,
) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
    if cancellation_token is not None:
        cancellation_token.raise_if_cancelled()
    if backend == "kriging":
        from geoviz_plots.factor.kriging import kriging_grid

        # V6 §11: explicit variogram controls + geometric anisotropy (the
        # direction-line azimuth/ratio the directional backend already uses).
        kriging_kwargs: dict[str, Any] = {"variogram_model": variogram_model}
        if variogram_range is not None:
            kriging_kwargs["range_"] = float(variogram_range)
        if variogram_nugget is not None:
            kriging_kwargs["nugget"] = float(variogram_nugget)
        anisotropy_applied = False
        if anisotropy_requested(azimuth_deg, semi_major, semi_minor):
            ratio = float(semi_major) / float(semi_minor)
            if ratio > 1.0 + 1e-9:
                kriging_kwargs["azimuth_deg"] = float(azimuth_deg or 0.0)
                kriging_kwargs["anisotropy_ratio"] = ratio
                anisotropy_applied = True
        kriging_diag: dict[str, Any] = {}
        kriging_kwargs["diagnostics"] = kriging_diag
        grid_z, grid_var = kriging_grid(x, y, z, grid_x, grid_y, **kriging_kwargs)
        if interp_status is not None:
            interp_status["kriging_diagnostics"] = kriging_diag
        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()
        if want_variance:
            return grid_z, grid_var
        return grid_z
    if backend == "directional":
        from geoviz import directional_trend_grid

        return directional_trend_grid(
            x, y, z, grid_x, grid_y,
            azimuth_deg=azimuth_deg, a=semi_major, b=semi_minor,
            q=q, b_i=b_i, cancellation_token=cancellation_token,
        )
    if backend == "idw":
        from geoviz import interpolate_idw

        kwargs: dict[str, Any] = {"power": power, "cancellation_token": cancellation_token}
        if fault_polylines:
            kwargs["fault_polylines"] = fault_polylines
        return interpolate_idw(x, y, z, grid_x, grid_y, **kwargs)
    from geoviz import interpolate_scipy

    method = backend if backend in {"linear", "cubic", "nearest", "rbf"} else "linear"
    result = interpolate_scipy(x, y, z, grid_x, grid_y, method=method, status=interp_status)
    if cancellation_token is not None:
        cancellation_token.raise_if_cancelled()
    return result


def _kriging_leave_one_out_r2(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    cancellation_token=None,
) -> float | None:
    """LOO R² for the kriging backend via the closed-form single-inverse path.

    The variogram is fitted once and the augmented system inverted once
    (``kriging.leave_one_out_predictions``) instead of re-fitting the
    variogram and re-solving a full system for every left-out point. Falls
    back to ``None`` whenever the closed form cannot be formed (same contract
    as the per-point loop).
    """
    from geoviz_plots.factor.kriging import leave_one_out_predictions

    if cancellation_token is not None:
        cancellation_token.raise_if_cancelled()
    try:
        preds, observed = leave_one_out_predictions(x, y, z)
    except Exception as exc:
        from geoviz import JobCancelled

        if isinstance(exc, JobCancelled):
            raise
        return None
    if cancellation_token is not None:
        cancellation_token.raise_if_cancelled()
    m = len(observed)
    if m < 3 or not np.all(np.isfinite(preds)):
        return None
    if m > MAX_LOO_SAMPLES:
        evaluation_indices = np.linspace(0, m - 1, MAX_LOO_SAMPLES, dtype=np.int64)
    else:
        evaluation_indices = np.arange(m, dtype=np.int64)
    return _r_squared(observed[evaluation_indices], preds[evaluation_indices])


def _r_squared(observed: np.ndarray, preds: np.ndarray) -> float:
    """Coefficient of determination (signed; not clamped to [0, 1])."""
    ss_res = float(np.sum((observed - preds) ** 2))
    ss_tot = float(np.sum((observed - np.mean(observed)) ** 2))
    if ss_tot <= 1e-12:
        return 1.0 if ss_res <= 1e-12 else 0.0
    return 1.0 - ss_res / ss_tot


def _leave_one_out_r2(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    *,
    backend: str,
    power: float,
    fault_polylines: list[list[tuple[float, float]]] | None = None,
    azimuth_deg: float = 0.0,
    semi_major: float = DEFAULT_SEMI_MAJOR,
    semi_minor: float = DEFAULT_SEMI_MINOR,
    q: np.ndarray | None = None,
    b_i: np.ndarray | None = None,
    cancellation_token=None,
) -> float | None:
    """Estimate LOO R² using at most ``MAX_LOO_SAMPLES`` observations.

    The kriging backend uses the closed-form single-inverse LOO
    (:func:`_kriging_leave_one_out_r2`); all other backends run one
    interpolation per left-out point.
    """
    n = len(z)
    if n < 3:
        return None
    if backend == "kriging":
        return _kriging_leave_one_out_r2(x, y, z, cancellation_token)
    evaluation_indices = (
        np.arange(n, dtype=np.int64)
        if n <= MAX_LOO_SAMPLES
        else np.linspace(0, n - 1, MAX_LOO_SAMPLES, dtype=np.int64)
    )
    preds = np.empty(len(evaluation_indices), dtype=np.float64)
    for prediction_index, i in enumerate(evaluation_indices):
        mask = np.ones(n, dtype=bool)
        mask[i] = False
        try:
            q_m = None if q is None else q[mask]
            b_m = None if b_i is None else b_i[mask]
            grid = _run_grid(
                x[mask], y[mask], z[mask],
                np.asarray([x[i]]), np.asarray([y[i]]),
                backend=backend, power=power, fault_polylines=fault_polylines,
                azimuth_deg=azimuth_deg, semi_major=semi_major, semi_minor=semi_minor,
                q=q_m, b_i=b_m, cancellation_token=cancellation_token,
            )
            val = float(grid[0, 0])
        except Exception as exc:
            from geoviz import JobCancelled

            if isinstance(exc, JobCancelled):
                raise
            return None
        if not math.isfinite(val):
            return None
        preds[prediction_index] = val
    observed = z[evaluation_indices]
    return _r_squared(observed, preds)


def anisotropy_requested(
    azimuth_deg: float | None, semi_major: float | None, semi_minor: float | None
) -> bool:
    """Whether the caller actually CONFIGURED anisotropy (review R3-P1).

    Default axes (1.0/0.4) with azimuth 0 mean "unset"; a non-zero azimuth
    OR axes different from the defaults is intent (azimuth 0° = due north is
    expressible via explicit non-default axes).
    """
    if azimuth_deg not in (None, 0.0):
        return True
    try:
        return (float(semi_major), float(semi_minor)) != (
            float(DEFAULT_SEMI_MAJOR),
            float(DEFAULT_SEMI_MINOR),
        )
    except (TypeError, ValueError):
        return False


def interpolate_factor_grid(
    sample_points: list[dict[str, Any]] | None,
    *,
    method: str = "IDW",
    grid_n: int = DEFAULT_GRID_N,
    power: float = 2.0,
    fault_polylines: list[list[tuple[float, float]]] | None = None,
    azimuth_deg: float = 0.0,
    semi_major: float = DEFAULT_SEMI_MAJOR,
    semi_minor: float = DEFAULT_SEMI_MINOR,
    cancellation_token=None,
    variogram_model: str = "spherical",
    variogram_range: float | None = None,
    variogram_nugget: float | None = None,
) -> dict[str, Any]:
    """Interpolate scattered sample_points onto a regular grid.

    Returns a JSON-serializable dict with axes, values, and quality stats.
    Optional *fault_polylines* are passed to IDW as break barriers (ISS-ALG-03).
    Method ``方向趋势`` uses directional weights (ISS-ALG-02). Backend
    ``kriging`` runs real ordinary kriging (variogram fit + OK solve) and
    additionally returns ``grid_var`` (kriging variance per cell) plus
    ``variance_min`` / ``variance_max``.
    """
    backend = method_to_backend(method)
    q = b_i = None
    if backend == "directional":
        x, y, z, q, b_i = extract_xy_z_weights(sample_points)
    else:
        x, y, z = extract_xy_values(sample_points)
    if len(z) < 2:
        raise ValueError("插值至少需要 2 个有效采样点")
    grid_x, grid_y = _grid_axes(x, y, grid_n)
    want_variance = backend == "kriging"
    interp_status: dict[str, Any] = {}
    grid_out = _run_grid(
        x, y, z, grid_x, grid_y,
        backend=backend, power=power,
        fault_polylines=fault_polylines if backend == "idw" else None,
        azimuth_deg=azimuth_deg, semi_major=semi_major, semi_minor=semi_minor,
        q=q, b_i=b_i, cancellation_token=cancellation_token,
        want_variance=want_variance,
        interp_status=interp_status,
        variogram_model=variogram_model,
        variogram_range=variogram_range,
        variogram_nugget=variogram_nugget,
    )
    grid_z, grid_var = grid_out if want_variance else (grid_out, None)
    # #941-1/2: keep ndarray for the hot numerical payload — converting to a
    # nested list of Python floats duplicates the grid (≈8× memory for 2000²)
    # and costs ~124 ms @1024². Callers that need JSON lists can materialise
    # them via ``encode_legacy_*`` helpers; the live cache (FactorGridResult)
    # consumes the ndarray directly (mirrors the plan path).
    grid_x_arr = np.ascontiguousarray(grid_x, dtype=np.float64)
    grid_y_arr = np.ascontiguousarray(grid_y, dtype=np.float64)
    grid_z_arr = np.ascontiguousarray(grid_z, dtype=np.float64)
    # Normalise non-finite to NaN (engine convention) — keep ndarray.
    grid_z_arr = np.where(np.isfinite(grid_z_arr), grid_z_arr, np.nan)
    if grid_var is not None:
        grid_var_arr = np.ascontiguousarray(grid_var, dtype=np.float64)
        grid_var_arr = np.where(np.isfinite(grid_var_arr), grid_var_arr, np.nan)
    else:
        grid_var_arr = None
    finite = grid_z_arr[np.isfinite(grid_z_arr)]
    if finite.size == 0:
        raise ValueError("插值结果全为无效值")
    r2 = _leave_one_out_r2(
        x, y, z,
        backend=backend, power=power,
        fault_polylines=fault_polylines if backend == "idw" else None,
        azimuth_deg=azimuth_deg, semi_major=semi_major, semi_minor=semi_minor,
        q=q, b_i=b_i, cancellation_token=cancellation_token,
    )
    # Scientific V6 §10: constraints passed to a backend that ignores them
    # are REPORTED, never silently dropped. The old code zeroed
    # n_break_lines for non-IDW backends while the caller still showed the
    # user's faults on the map — the surface looked constrained.
    # Review R1-P1/R3-P1: only report anisotropy as ignored when it was
    # actually REQUESTED (default axes are "unset", not intent) and the
    # backend did not consume it (kriging applies it above).
    ignored_constraints: list[str] = []
    if fault_polylines and backend != "idw":
        ignored_constraints.append(
            f"barrier:{len(fault_polylines)} break line(s) not consumed by {backend}"
        )
    if (
        anisotropy_requested(azimuth_deg, semi_major, semi_minor)
        and backend == "idw"
    ):
        ignored_constraints.append("anisotropy:ignored by idw")
    out: dict[str, Any] = {
        "grid_x": grid_x_arr,
        "grid_y": grid_y_arr,
        "grid_z": grid_z_arr,
        "backend": backend,
        "method": method,
        "grid_n": int(grid_n),
        "n_points": int(len(z)),
        "n_break_lines": int(len(fault_polylines or [])) if backend == "idw" else 0,
        "ignored_constraints": ignored_constraints,
        "constraint_warnings": [
            f"constraint {entry} — the interpolated surface does NOT reflect it"
            for entry in ignored_constraints
        ],
        "azimuth_deg": float(azimuth_deg) if backend == "directional" else None,
        "semi_major": float(semi_major) if backend == "directional" else None,
        "semi_minor": float(semi_minor) if backend == "directional" else None,
        "min": float(np.min(finite)),
        "max": float(np.max(finite)),
        "mean": float(np.mean(finite)),
        "r_squared": round(float(r2), 4) if (r2 is not None and math.isfinite(r2)) else None,
    }
    if grid_var_arr is not None:
        var_flat = grid_var_arr[np.isfinite(grid_var_arr)]
        out["grid_var"] = grid_var_arr
        out["variance_min"] = float(np.min(var_flat)) if var_flat.size else None
        out["variance_max"] = float(np.max(var_flat)) if var_flat.size else None
    note = mvp_note_for(backend)
    if note:
        out["mvp_note"] = note
    if interp_status.get("kriging_diagnostics"):
        out["kriging_diagnostics"] = interp_status["kriging_diagnostics"]
    if interp_status.get("fallback"):
        out["degraded"] = True
        out["fallback"] = interp_status["fallback"]
    return out


def synthetic_sample_points(
    *,
    seed: int,
    factor_type: str,
    count: int = 8,
) -> list[dict[str, Any]]:
    """Deterministic control points when no well-derived samples exist yet."""
    rng = random.Random(f"{seed}:{factor_type}")
    digest = hashlib.sha256(factor_type.encode("utf-8")).digest()
    base = 10.0 + (int.from_bytes(digest[:4], "big") % 20)
    return [
        {
            "well": f"A{i + 1}",
            "x": round(114.0 + rng.random() * 0.3, 6),
            "y": round(22.5 + rng.random() * 0.3, 6),
            "value": round(base + rng.random() * 40.0, 3),
        }
        for i in range(count)
    ]


# Expose the snapshot-hash helper for the Workbench adapter, which needs it
# to populate ``FactorMapTask.input_snapshot_hash``.
def snapshot_hash(payload: dict[str, Any]) -> str:
    """Stable SHA-256 of a JSON-serializable payload (sorted keys)."""
    return _snapshot_hash(payload)


__all__ = [
    "GENERATOR_VERSION",
    "DEFAULT_FACTOR_TYPES",
    "DEFAULT_GRID_N",
    "MAX_LOO_SAMPLES",
    "extract_xy_values",
    "interpolate_factor_grid",
    "method_to_backend",
    "mvp_note_for",
    "snapshot_hash",
    "synthetic_sample_points",
]
