"""Vector contour line and filled polygon extraction using contourpy."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import contourpy
from PySide6.QtGui import QColor

from geoviz_plots.surface.colormaps import sample_colormap


@dataclass
class BandedFill:
    """One filled-contour band between two adjacent levels.

    ``polygons`` / ``offsets`` retain the contourpy ``OuterOffset`` (or
    ``Separate``) packed shape so existing painters can iterate rings by
    slicing ``polygons[i][offsets[i][j]:offsets[i][j+1]]``. ``color`` is the
    band's representative color resolved against ``palette`` at the band
    midpoint ``((level_min + level_max) / 2)``; ``label`` is a display hint
    (``"min-max"``) that callers may override.
    """

    level_min: float
    level_max: float
    polygons: list
    offsets: list
    color: QColor
    label: str


def extract_contour_lines(
    grid_x, grid_y, grid_z, levels, *, cancellation_token=None
) -> dict[float, list[np.ndarray]]:
    """Extract vector contour lines for each level using contourpy.

    Handles NaNs automatically by converting to a masked array.

    Args:
        grid_x, grid_y: 1D grid coordinate arrays.
        grid_z: 2D grid value array of shape (len(grid_y), len(grid_x)).
        levels: List of contour levels to extract.

    Returns:
        A dict mapping level (float) to a list of lines (each line is a 2D numpy array of points).
    """
    if cancellation_token is not None:
        cancellation_token.raise_if_cancelled()
    grid_x = np.asarray(grid_x, dtype=np.float64)
    grid_y = np.asarray(grid_y, dtype=np.float64)
    grid_z = np.asarray(grid_z, dtype=np.float64)

    # Mask NaNs & Infinities
    masked_z = np.ma.masked_invalid(grid_z)

    # Create contour generator using serial algorithm and separate line lists
    cg = contourpy.contour_generator(
        x=grid_x, y=grid_y, z=masked_z,
        name="serial", line_type="Separate"
    )

    lines_dict = {}
    for lv in levels:
        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()
        lines_dict[float(lv)] = cg.lines(float(lv))
    if cancellation_token is not None:
        cancellation_token.raise_if_cancelled()

    return lines_dict


def _clip_polygons_to_study_area(
    polys, offsets, study_area_clip: list[tuple[float, float]]
):
    """Clip packed OuterOffset contour rings to a study-area polygon.

    Returns ``(clipped_polys, clipped_offsets)`` in the same packed shape.
    Falls back to the input (no clip) when shapely is unavailable, matching
    the ``HAS_SHAPELY`` capability pattern in ``geoviz_plots.map_edit``.
    """
    try:
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
    except ImportError:
        return polys, offsets

    clip_poly = Polygon(study_area_clip)
    if not clip_poly.is_valid:
        return polys, offsets

    out_polys: list = []
    out_offsets: list = []
    for poly_coords, offset_arr in zip(polys, offsets):
        rings = []
        for j in range(len(offset_arr) - 1):
            start_idx = offset_arr[j]
            end_idx = offset_arr[j + 1]
            ring_pts = poly_coords[start_idx:end_idx]
            if len(ring_pts) >= 3:
                rings.append(ring_pts)
        if not rings:
            continue
        # Union each ring as a polygon, then intersect with the clip polygon.
        merged = unary_union([Polygon(r) for r in rings])
        clipped = merged.intersection(clip_poly)
        if clipped.is_empty:
            continue
        geoms = list(clipped.geoms) if clipped.geom_type == "MultiPolygon" else [clipped]
        for g in geoms:
            if g.geom_type != "Polygon" or g.is_empty:
                continue
            ext = np.array(g.exterior.coords)
            out_polys.append(ext)
            offsets_for_poly = [0, len(ext)]
            for interior in g.interiors:
                int_pts = np.array(interior.coords)
                out_polys.append(int_pts)
                offsets_for_poly.append(offsets_for_poly[-1] + len(int_pts))
            out_offsets.append(np.array(offsets_for_poly))
    return out_polys, out_offsets


def extract_filled_contours(
    grid_x, grid_y, grid_z, levels,
    *,
    study_area_clip: list[tuple[float, float]] | None = None,
    fill_type: Literal["OuterOffset", "Separate"] = "OuterOffset",
    palette: str = "viridis",
    cancellation_token=None,
) -> list[BandedFill]:
    """Extract vector filled contour polygons between adjacent levels.

    Args:
        grid_x, grid_y: 1D grid coordinate arrays.
        grid_z: 2D grid value array of shape (len(grid_y), len(grid_x)).
        levels: Sorted list of contour interval boundary values.
        study_area_clip: Optional polygon (list of (x, y)) to clip band rings
            to. When provided, bands are intersected with this polygon via
            shapely (falls back to no clip if shapely is unavailable).
        fill_type: contourpy fill type (``"OuterOffset"`` or ``"Separate"``).
        palette: Colormap name resolved against
            ``geoviz_plots.surface.colormaps.COLORMAPS`` to produce each
            band's representative ``color``.
        cancellation_token: Optional cooperative-cancellation token; checked
            before work and between bands (same shape as
            ``extract_contour_lines``).

    Returns:
        List of :class:`BandedFill` - one per adjacent level pair, in
        ascending level order. ``color`` is sampled at the band midpoint
        against the ``levels`` range; ``label`` is ``"min-max"`` (caller may
        override).
    """
    if cancellation_token is not None:
        cancellation_token.raise_if_cancelled()
    grid_x = np.asarray(grid_x, dtype=np.float64)
    grid_y = np.asarray(grid_y, dtype=np.float64)
    grid_z = np.asarray(grid_z, dtype=np.float64)

    # Mask NaNs & Infinities
    masked_z = np.ma.masked_invalid(grid_z)

    cg = contourpy.contour_generator(
        x=grid_x, y=grid_y, z=masked_z,
        name="serial", fill_type=fill_type,
    )

    sorted_levels = sorted(levels)
    if not sorted_levels:
        return []

    vmin = float(sorted_levels[0])
    vmax = float(sorted_levels[-1])

    bands: list[BandedFill] = []
    for i in range(len(sorted_levels) - 1):
        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()
        lv_min = float(sorted_levels[i])
        lv_max = float(sorted_levels[i + 1])
        polys, offsets = cg.filled(lv_min, lv_max)

        if study_area_clip:
            polys, offsets = _clip_polygons_to_study_area(polys, offsets, study_area_clip)

        midpoint = (lv_min + lv_max) / 2.0
        color = sample_colormap(palette, midpoint, vmin, vmax)
        bands.append(BandedFill(
            level_min=lv_min,
            level_max=lv_max,
            polygons=polys,
            offsets=offsets,
            color=color,
            label=f"{lv_min:g}-{lv_max:g}",
        ))

    return bands
