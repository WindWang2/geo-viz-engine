from .chart_engine import ChartEngine
from .models import (
    WellLogData, CurveData, LithologyInterval, FaciesInterval,
    IntervalItem, WellIntervals, FaciesData, LineStyle
)
from .config import (
    ChartConfig, TrackConfig, TrackType, PatternMapping,
    CurveTrackConfig, IntervalTrackConfig, SystemsTractTrackConfig, TextTrackConfig
)
from .sync_manager import SyncManager
from .connection_overlay import ConnectionOverlay
from .location_map import LocationMapWidget
from .utils import build_default_payload
from .payload_builder import (
    build_tracks_from_data,
    build_curve_track,
    build_interval_track,
    build_depth_track,
    build_lithology_track,
    build_merged_curve_track,
    build_systems_tract_track,
    build_ai_prediction_tracks,
    build_legacy_display_items,
    LEGACY_DEFAULT_ACTIVE,
)
from .track_manager import TrackManager
from .pattern_map import PATTERN_MAP

# New QPainter renderer
from .renderer import (
    BaseTrack, DepthTrack, CurveTrack, WellLogCanvas, LayoutCoordinator,
    IntervalTrack, LithologyTrack, FaciesTrack, SystemsTractTrack,
    PatternEngine, ZoomPanHandler, CrosshairOverlay,
)
from .export_qpainter import export_svg as qpainter_export_svg
from .export_qpainter import export_pdf as qpainter_export_pdf
from .export_qpainter import export_png as qpainter_export_png

__version__ = "0.1.0"

__all__ = [
    "ChartEngine",
    "WellLogData",
    "CurveData",
    "LithologyInterval",
    "FaciesInterval",
    "IntervalItem",
    "WellIntervals",
    "FaciesData",
    "LineStyle",
    "ChartConfig",
    "TrackConfig",
    "TrackType",
    "PatternMapping",
    "CurveTrackConfig",
    "IntervalTrackConfig",
    "SystemsTractTrackConfig",
    "TextTrackConfig",
    "SyncManager",
    "ConnectionOverlay",
    "LocationMapWidget",
    "build_default_payload",
    "build_tracks_from_data",
    "build_curve_track",
    "build_interval_track",
    "build_depth_track",
    "build_lithology_track",
    "build_merged_curve_track",
    "build_systems_tract_track",
    "build_ai_prediction_tracks",
    "build_legacy_display_items",
    "LEGACY_DEFAULT_ACTIVE",
    "TrackManager",
    "PATTERN_MAP",
    # QPainter renderer
    "BaseTrack", "DepthTrack", "CurveTrack", "WellLogCanvas", "LayoutCoordinator",
    "IntervalTrack", "LithologyTrack", "FaciesTrack", "SystemsTractTrack",
    "PatternEngine", "ZoomPanHandler", "CrosshairOverlay",
    "qpainter_export_svg", "qpainter_export_pdf", "qpainter_export_png",
]
