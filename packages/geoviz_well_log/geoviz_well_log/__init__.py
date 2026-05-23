"""geoviz-well-log — QPainter-based well log visualization package.

A standalone PySide6 package for rendering well log charts with SVG pattern
fills, curve tracks, stratigraphy columns, and vector export (SVG/PDF/PNG).

Quick start::

    from geoviz_well_log import build_qpainter_tracks, WellLogCanvas
    from geoviz_well_log import WellLogData, CurveData, IntervalItem

    # Build tracks from data
    tracks = build_qpainter_tracks(well_log_data)

    # Use in a Qt layout
    canvas = WellLogCanvas()
    canvas.set_tracks(tracks)
"""

# Data models
from .models import (
    WellLogData,
    CurveData,
    LithologyInterval,
    FaciesInterval,
    IntervalItem,
    WellIntervals,
    FaciesData,
    LineStyle,
)

# Pattern mapping
from .pattern_map import PATTERN_MAP, FACIES_COLORS

# QPainter renderer
from .renderer import (
    BaseTrack,
    DepthTrack,
    CurveTrack,
    WellLogCanvas,
    LayoutCoordinator,
    IntervalTrack,
    LithologyTrack,
    FaciesTrack,
    SystemsTractTrack,
    PatternEngine,
    ZoomPanHandler,
    CrosshairOverlay,
)

# Track builder
from .qpainter_builder import build_qpainter_tracks

# Vector export
from .export_qpainter import export_svg, export_pdf, export_png

__version__ = "1.0.0"

__all__ = [
    # Models
    "WellLogData",
    "CurveData",
    "LithologyInterval",
    "FaciesInterval",
    "IntervalItem",
    "WellIntervals",
    "FaciesData",
    "LineStyle",
    # Patterns
    "PATTERN_MAP",
    "FACIES_COLORS",
    # Renderer
    "BaseTrack",
    "DepthTrack",
    "CurveTrack",
    "WellLogCanvas",
    "LayoutCoordinator",
    "IntervalTrack",
    "LithologyTrack",
    "FaciesTrack",
    "SystemsTractTrack",
    "PatternEngine",
    "ZoomPanHandler",
    "CrosshairOverlay",
    # Builder
    "build_qpainter_tracks",
    # Export
    "export_svg",
    "export_pdf",
    "export_png",
]
