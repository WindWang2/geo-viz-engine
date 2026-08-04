"""Factor-map interpolation core: IDW / SciPy / directional-trend dispatch.

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
# ISS-KRIG-01: 克里金 / 克里金(MVP·线性) map to SciPy linear triangulation,
# NOT full variogram kriging. T3 (paleo-workbench#247) confirmed this stays.
_METHOD_BACKEND: dict[str, str] = {
    "IDW": "idw",
    "idw": "idw",
    "克里金": "linear",
    "克里金(MVP·线性)": "linear",
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
) -> np.ndarray:
    if cancellation_token is not None:
        cancellation_token.raise_if_cancelled()
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
    result = interpolate_scipy(x, y, z, grid_x, grid_y, method=method)
    if cancellation_token is not None:
        cancellation_token.raise_if_cancelled()
    return result


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
    """Estimate LOO R² using at most ``MAX_LOO_SAMPLES`` observations."""
    n = len(z)
    if n < 3:
        return None
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
    ss_res = float(np.sum((observed - preds) ** 2))
    ss_tot = float(np.sum((observed - np.mean(observed)) ** 2))
    if ss_tot <= 1e-12:
        return 1.0 if ss_res <= 1e-12 else 0.0
    return max(0.0, min(1.0, 1.0 - ss_res / ss_tot))


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
) -> dict[str, Any]:
    """Interpolate scattered sample_points onto a regular grid.

    Returns a JSON-serializable dict with axes, values, and quality stats.
    Optional *fault_polylines* are passed to IDW as break barriers (ISS-ALG-03).
    Method ``方向趋势`` uses directional weights (ISS-ALG-02).
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
    grid_z = _run_grid(
        x, y, z, grid_x, grid_y,
        backend=backend, power=power,
        fault_polylines=fault_polylines if backend == "idw" else None,
        azimuth_deg=azimuth_deg, semi_major=semi_major, semi_minor=semi_minor,
        q=q, b_i=b_i, cancellation_token=cancellation_token,
    )
    finite = grid_z[np.isfinite(grid_z)]
    if finite.size == 0:
        raise ValueError("插值结果全为无效值")
    r2 = _leave_one_out_r2(
        x, y, z,
        backend=backend, power=power,
        fault_polylines=fault_polylines if backend == "idw" else None,
        azimuth_deg=azimuth_deg, semi_major=semi_major, semi_minor=semi_minor,
        q=q, b_i=b_i, cancellation_token=cancellation_token,
    )
    out: dict[str, Any] = {
        "grid_x": [float(v) for v in grid_x],
        "grid_y": [float(v) for v in grid_y],
        "grid_z": [[None if not math.isfinite(float(v)) else float(v) for v in row] for row in grid_z],
        "backend": backend,
        "method": method,
        "grid_n": int(grid_n),
        "n_points": int(len(z)),
        "n_break_lines": int(len(fault_polylines or [])) if backend == "idw" else 0,
        "azimuth_deg": float(azimuth_deg) if backend == "directional" else None,
        "semi_major": float(semi_major) if backend == "directional" else None,
        "semi_minor": float(semi_minor) if backend == "directional" else None,
        "min": float(np.min(finite)),
        "max": float(np.max(finite)),
        "mean": float(np.mean(finite)),
        "r_squared": None if r2 is None else round(float(r2), 4),
    }
    note = mvp_note_for(backend)
    if note:
        out["mvp_note"] = note
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
