"""Contour segment extraction and feature export (pure numpy).

The extraction pipeline consumes the ``geoviz`` facade's ``extract_contour_lines``
(contourpy-backed marching squares) and emits a list of ``ContourSegment``
dataclasses. The Workbench adapter maps these into its pydantic
``ContourDraft`` / ``PaleoMapDocument.line_features``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np

from geoviz_plots.contour_draft.levels import GENERATOR_VERSION


@dataclass
class ContourSegment:
    """One isoline polyline.

    Field shape mirrors ``paleo_workbench.project.models.ContourSegment`` so the
    Workbench adapter can construct the pydantic model field-for-field, but
    this dataclass is independent (T10: ``project.models`` is not promoted).
    """

    level: float
    coordinates: list[list[float]]
    closed: bool = False
    properties: dict[str, Any] = field(default_factory=dict)
    id: str = ""


def coerce_grid(
    params: dict[str, Any] | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pull and normalize ``grid_x`` / ``grid_y`` / ``grid_z`` from a params dict.

    Accepts the loose shape stored in ``FactorMapTask.parameters`` (lists with
    possible ``None`` cells). Raises ``ValueError`` when the grid is missing or
    malformed. Kept model-free (takes a plain dict) so the engine doesn't
    depend on ``FactorMapTask``; the Workbench adapter calls it with
    ``task.parameters``.
    """
    params = params or {}
    gx = params.get("grid_x")
    gy = params.get("grid_y")
    gz = params.get("grid_z")
    if not gx or not gy or not gz:
        raise ValueError("params 缺少 grid_x/grid_y/grid_z，请先完成插值")
    grid_x = np.asarray(gx, dtype=np.float64)
    grid_y = np.asarray(gy, dtype=np.float64)
    grid_z = np.asarray(gz, dtype=np.float64)
    # JSON may store None for invalid cells
    if grid_z.dtype == object:
        grid_z = np.array(
            [[np.nan if v is None else float(v) for v in row] for row in gz],
            dtype=np.float64,
        )
    if grid_z.ndim != 2:
        raise ValueError(f"grid_z 维数错误: {grid_z.shape}")
    return grid_x, grid_y, grid_z


def extract_contour_segments(
    grid_x: np.ndarray,
    grid_y: np.ndarray,
    grid_z: np.ndarray,
    levels: Sequence[float],
    *,
    cancellation_token=None,
) -> list[ContourSegment]:
    """Extract isolines via the ``geoviz`` facade and return ``ContourSegment``s.

    Thin wrapper over ``geoviz.extract_contour_lines`` (contourpy) that converts
    the raw ``dict[level, list[ndarray]]`` into structured segments. Raises
    ``ImportError`` if the facade is unavailable.
    """
    try:
        from geoviz import extract_contour_lines
    except Exception as exc:  # noqa: BLE001
        raise ImportError(
            "geoviz.extract_contour_lines unavailable; ensure geoviz facade is installed"
        ) from exc

    lines_dict = extract_contour_lines(
        grid_x,
        grid_y,
        grid_z,
        list(levels),
        cancellation_token=cancellation_token,
    )
    return _segments_from_lines_dict(lines_dict)


def _segments_from_lines_dict(
    lines_dict: dict[float, list[Any]],
) -> list[ContourSegment]:
    segments: list[ContourSegment] = []
    for level, lines in sorted(lines_dict.items(), key=lambda kv: kv[0]):
        for line in lines or []:
            arr = np.asarray(line, dtype=np.float64)
            if arr.ndim != 2 or arr.shape[0] < 2 or arr.shape[1] < 2:
                continue
            coords = [[float(p[0]), float(p[1])] for p in arr]
            closed = (
                len(coords) >= 3
                and math.isclose(coords[0][0], coords[-1][0], abs_tol=1e-9)
                and math.isclose(coords[0][1], coords[-1][1], abs_tol=1e-9)
            )
            segments.append(
                ContourSegment(
                    level=float(level),
                    coordinates=coords,
                    closed=closed,
                    properties={"level": float(level)},
                )
            )
    return segments


def segments_to_line_features(
    segments: Sequence[ContourSegment],
    *,
    draft_id: str,
    factor_type: str = "",
    target_horizon: str = "",
) -> list[dict[str, Any]]:
    """Export isolines as map-edit ``line_features`` (``role=contour``).

    Mirrors the feature shape produced by the Workbench adapter's
    ``line_features_from_contour_draft`` so the Workbench adapter can delegate
    here, passing the draft's identity fields. The adapter remains responsible
    for assigning per-segment ``id`` if it needs stable cross-session ids.
    """
    features: list[dict[str, Any]] = []
    for seg in segments:
        if len(seg.coordinates) < 2:
            continue
        features.append(
            {
                "id": seg.id,
                "kind": "line",
                "name": f"L={seg.level:g}",
                "role": "contour",
                "coordinates": [list(p) for p in seg.coordinates],
                "properties": {
                    "role": "contour",
                    "constraint_role": "contour",
                    "level": seg.level,
                    "closed": seg.closed,
                    "contour_draft_id": draft_id,
                    "factor_type": factor_type,
                    "target_horizon": target_horizon,
                    **(seg.properties or {}),
                },
            }
        )
    return features


__all__ = [
    "GENERATOR_VERSION",
    "ContourSegment",
    "coerce_grid",
    "extract_contour_segments",
    "segments_to_line_features",
]
