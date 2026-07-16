import importlib

from .contracts import (
    PreparedPreview,
    PreviewCapabilities,
    PreviewKind,
    PreviewOptions,
    PreviewRequest,
)
from .engine import GeoVizEngine
from .errors import ErrorCode, GeoVizError
from .prepared_codec import (
    PAYLOAD_SCHEMA_VERSION,
    decode_prepared_preview,
    encode_prepared_preview,
)
from .registry import PreviewRegistry

# name → (module, attribute) for lazy workbench-facing exports.
_COMPATIBILITY_EXPORTS: dict[str, tuple[str, str]] = {
    "WellLogCanvas": ("geoviz_well_log", "WellLogCanvas"),
    "WellLogData": ("geoviz_well_log", "WellLogData"),
    "CurveData": ("geoviz_well_log", "CurveData"),
    "build_qpainter_tracks": ("geoviz_well_log", "build_qpainter_tracks"),
    "load_las_preview": ("geoviz_well_log.las_preview", "load_las_preview"),
    "export_svg": ("geoviz_well_log", "export_svg"),
    "export_pdf": ("geoviz_well_log", "export_pdf"),
    "export_png": ("geoviz_well_log", "export_png"),
    "SeismicView": ("geoviz_seismic", "SeismicView"),
    "ProfileWidget": ("geoviz_seismic", "ProfileWidget"),
    "SeismicLoader": ("geoviz_seismic.loader", "SeismicLoader"),
    "PaleoMapCanvas": ("geoviz_paleo_map", "PaleoMapCanvas"),
    "export_professional_figure": ("geoviz_paleo_map", "export_professional_figure"),
    "CrossWellCanvas": ("geoviz_cross_well", "CrossWellCanvas"),
    "PlotWidget": ("geoviz_plots", "PlotWidget"),
    "SurfaceWidget": ("geoviz_plots", "SurfaceWidget"),
    "interpolate_idw": ("geoviz_plots", "interpolate_idw"),
    "interpolate_scipy": ("geoviz_plots", "interpolate_scipy"),
    # Well-log interval models used when attaching facies/lithology tracks.
    "FaciesData": ("geoviz_well_log.models", "FaciesData"),
    "FaciesInterval": ("geoviz_well_log.models", "FaciesInterval"),
    "IntervalItem": ("geoviz_well_log.models", "IntervalItem"),
    "LithologyInterval": ("geoviz_well_log.models", "LithologyInterval"),
    "WellIntervals": ("geoviz_well_log.models", "WellIntervals"),
}


def __getattr__(name: str):
    spec = _COMPATIBILITY_EXPORTS.get(name)
    if spec is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = spec
    value = getattr(importlib.import_module(module_name), attr)
    globals()[name] = value
    return value


__all__ = [
    "ErrorCode",
    "GeoVizEngine",
    "GeoVizError",
    "PreparedPreview",
    "PreviewCapabilities",
    "PreviewKind",
    "PreviewOptions",
    "PreviewRegistry",
    "PreviewRequest",
    "PAYLOAD_SCHEMA_VERSION",
    "decode_prepared_preview",
    "encode_prepared_preview",
    *sorted(_COMPATIBILITY_EXPORTS),
]
