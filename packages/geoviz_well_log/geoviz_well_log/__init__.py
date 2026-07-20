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
    CorrelationLink,
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
    DepthRuler,
)

# Track builder
from .qpainter_builder import build_qpainter_tracks
from .well_log_view import WellLogView

# Bounded LAS and XML preview loaders
from .las_preview import (
    LASCurveHeader,
    LASPreviewHeader,
    curve_data_from_arrays,
    inspect_las_file,
    load_las_preview,
    read_sampled_ascii,
)
from .xml_preview import load_xml_preview

# Vector export
from .export_qpainter import export_svg, export_pdf, export_png

# Cross-well widgets
from .section import (
    DatumTransformer,
    FaciesQuad,
    HorizonLink,
    WellSectionCanvas,
)
from .cross_well_widget import CrossWellWidget
from .painter_sync_manager import QPainterSyncManager

# Cross-well scene (QGraphicsScene-based)
from .scene import CrossWellScene, CrossWellView, WellItem, CorrelationBand, DepthRulerItem

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
    "CorrelationLink",
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
    "DepthRuler",
    # Builder
    "build_qpainter_tracks",
    "WellLogView",
    # LAS preview
    "LASCurveHeader",
    "LASPreviewHeader",
    "curve_data_from_arrays",
    "inspect_las_file",
    "load_las_preview",
    "read_sampled_ascii",
    # Export
    "export_svg",
    "export_pdf",
    "export_png",
    # Cross-well
    "CrossWellWidget",
    "QPainterSyncManager",
    "CrossWellScene",
    "CrossWellView",
    "WellItem",
    "CorrelationBand",
    "DepthRulerItem",
]
