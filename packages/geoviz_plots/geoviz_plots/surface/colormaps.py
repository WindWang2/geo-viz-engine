"""Shared colormap tables and sampling for filled-contour rendering.

Extracted from ``surface_widget.py`` (Phase-2, T3 / #247) so both
``marching_squares.extract_filled_contours`` (which resolves a ``palette``
name to a per-band ``QColor`` for ``BandedFill``) and ``SurfaceWidget``
(which paints those bands) share a single source of truth without a circular
import (``surface_widget`` already imports from ``marching_squares``).

``geoviz_plots`` already depends on PySide6 (``SurfaceWidget`` uses
``QPainter``/``QColor``/``QPainterPath``), so holding ``QColor`` values here
adds no new dependency. The package-independence edges that
``test_geoviz_dependency_graph_is_acyclic`` enforces are between *internal*
geoviz subpackages; this module is intra-``geoviz_plots`` and introduces no
new subpackage edge.
"""
from __future__ import annotations

from PySide6.QtGui import QColor


# Beautiful Elegant Academic Colormaps. Each entry is a sorted list of
# (fraction in [0,1], QColor) control points; fractions must be monotonic.
COLORMAPS: dict[str, list[tuple[float, QColor]]] = {
    "viridis": [
        (0.0, QColor(68, 1, 84)),
        (0.25, QColor(59, 82, 139)),
        (0.5, QColor(33, 145, 140)),
        (0.75, QColor(94, 201, 98)),
        (1.0, QColor(253, 231, 37)),
    ],
    "cnpc_strat": [  # CNPC Geologic Standard: Shale (Gray) to Sand (Yellow) to Carbonate (Blue)
        (0.0, QColor(100, 110, 120)),   # Shale
        (0.35, QColor(160, 175, 155)),  # Silty mudstone
        (0.7, QColor(255, 220, 95)),    # Sandstone
        (1.0, QColor(90, 175, 255)),    # Carbonate / Limestone
    ],
    "cnpc_fluid": [  # CNPC Fluid standard
        (0.0, QColor(40, 115, 255)),    # Water (Blue)
        (0.5, QColor(50, 220, 100)),    # Oil (Green)
        (1.0, QColor(255, 55, 55)),     # Gas (Red)
    ],
    "thermal": [
        (0.0, QColor(0, 0, 150)),
        (0.33, QColor(0, 200, 200)),
        (0.66, QColor(220, 220, 0)),
        (1.0, QColor(255, 0, 0)),
    ],
}


def sample_colormap(name: str, val: float, vmin: float, vmax: float) -> QColor:
    """Linearly interpolate a color from the named colormap at ``val``.

    ``val`` is clamped to the ``[vmin, vmax]`` range, mapped to ``[0, 1]``,
    then linearly interpolated between the adjacent control points of the
    colormap. If ``vmin == vmax`` the first control point's color is returned.
    An unknown ``name`` falls back to ``"viridis"`` (matching the
    ``SurfaceWidget`` default). When ``levels`` is empty the caller should
    short-circuit; this function treats ``vmin == vmax`` as that signal.
    """
    cmap = COLORMAPS.get(name, COLORMAPS["viridis"])
    if vmax == vmin:
        return QColor(cmap[0][1])
    fraction = (val - vmin) / (vmax - vmin)
    fraction = max(0.0, min(1.0, fraction))

    for i in range(len(cmap) - 1):
        t1, c1 = cmap[i]
        t2, c2 = cmap[i + 1]
        if t1 <= fraction <= t2:
            t_range = t2 - t1
            if t_range == 0.0:
                return QColor(c1)
            w = (fraction - t1) / t_range
            return QColor(
                int(c1.red() + w * (c2.red() - c1.red())),
                int(c1.green() + w * (c2.green() - c1.green())),
                int(c1.blue() + w * (c2.blue() - c1.blue())),
            )
    return QColor(cmap[-1][1])
