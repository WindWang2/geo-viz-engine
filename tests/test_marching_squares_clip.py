"""Tests for Issue #68: study-area clipping must preserve band holes.

contourpy ``OuterOffset`` packs one exterior ring followed by its hole rings
into a single points array per polygon. ``_clip_polygons_to_study_area``
rebuilds that exterior/interiors relationship so holes survive the clip
instead of being filled in by a naive union of all rings.
"""

import numpy as np
import pytest
from geoviz_plots.surface.marching_squares import (
    _clip_polygons_to_study_area,
    extract_filled_contours,
)


def _ring_signed_area(ring_pts):
    """Absolute polygon area via the shoelace formula."""
    x, y = ring_pts[:, 0], ring_pts[:, 1]
    return 0.5 * abs(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def test_clip_preserves_hole_of_packed_polygon():
    """A packed exterior+hole polygon keeps its interior after clipping."""
    # Exterior: 4x4 square; hole: 2x2 square centred at origin.
    ext = np.array([[-2.0, -2.0], [2.0, -2.0], [2.0, 2.0], [-2.0, 2.0], [-2.0, -2.0]])
    hole = np.array([[-1.0, -1.0], [1.0, -1.0], [1.0, 1.0], [-1.0, 1.0], [-1.0, -1.0]])
    poly_coords = np.concatenate([ext, hole])
    offsets = np.array([0, len(ext), len(ext) + len(hole)])

    # Clip to a 3x3 square that lies inside the exterior and fully contains
    # the hole: the hole must survive as a separate ring.
    clip = [(-1.5, -1.5), (1.5, -1.5), (1.5, 1.5), (-1.5, 1.5), (-1.5, -1.5)]
    out_polys, out_offsets = _clip_polygons_to_study_area(
        [poly_coords],
        [offsets],
        clip,
    )
    assert len(out_polys) == 1
    # One exterior + one interior ring survive the clip.
    assert len(out_offsets[0]) == 3
    exterior_area = _ring_signed_area(
        out_polys[0][out_offsets[0][0] : out_offsets[0][1]]
    )
    hole_area = _ring_signed_area(out_polys[0][out_offsets[0][1] : out_offsets[0][2]])
    # Rings are the clipped 3x3 square and the intact 2x2 hole. A union-based
    # clip would collapse both into a single filled ring.
    assert exterior_area == pytest.approx(9.0, abs=1e-6)
    assert hole_area == pytest.approx(4.0, abs=1e-6)


def test_clip_keeps_rings_when_clip_covers_hole():
    """Clipping a donut band to a region containing the hole keeps both rings."""
    n = 60
    x = np.linspace(-3.0, 3.0, n)
    y = np.linspace(-3.0, 3.0, n)
    gx, gy = np.meshgrid(x, y)
    radius = np.hypot(gx, gy)
    # Smooth radial hill peaking at r=1.5; band [1, 3] is a genuine annulus.
    grid_z = 4.0 * np.exp(-((radius - 1.5) ** 2) / 0.35)

    clip = [(-3.0, -3.0), (3.0, -3.0), (3.0, 3.0), (-3.0, 3.0), (-3.0, -3.0)]
    bands = extract_filled_contours(
        x,
        y,
        grid_z,
        levels=[1.0, 3.0],
        study_area_clip=clip,
    )
    assert len(bands) == 1
    assert bands[0].polygons, "band must contain at least one polygon"
    for poly_coords, offset_arr in zip(bands[0].polygons, bands[0].offsets):
        # Each annulus keeps its exterior + hole rings after the clip.
        assert len(offset_arr) >= 3
        exterior_area = _ring_signed_area(poly_coords[offset_arr[0] : offset_arr[1]])
        hole_area = _ring_signed_area(poly_coords[offset_arr[1] : offset_arr[2]])
        assert exterior_area > hole_area > 0.0


def test_clip_falls_back_to_input_without_shapely(monkeypatch):
    """Without shapely the clip is a no-op, returning the input unchanged."""
    import sys

    monkeypatch.setitem(sys.modules, "shapely", None)
    monkeypatch.setitem(sys.modules, "shapely.geometry", None)

    poly_coords = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]])
    offsets = np.array([0, 5])
    clip = [(0.0, 0.0), (0.5, 0.0), (0.5, 0.5), (0.0, 0.5), (0.0, 0.0)]
    out_polys, out_offsets = _clip_polygons_to_study_area(
        [poly_coords],
        [offsets],
        clip,
    )
    assert len(out_polys) == 1
    assert np.array_equal(out_polys[0], poly_coords)
    assert len(out_offsets) == 1
    assert np.array_equal(out_offsets[0], offsets)
