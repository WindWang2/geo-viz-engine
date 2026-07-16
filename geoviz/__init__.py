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

_COMPATIBILITY_EXPORTS = {
    "WellLogCanvas": "geoviz_well_log",
    "WellLogData": "geoviz_well_log",
    "CurveData": "geoviz_well_log",
    "build_qpainter_tracks": "geoviz_well_log",
    "SeismicView": "geoviz_seismic",
    "ProfileWidget": "geoviz_seismic",
    "PaleoMapCanvas": "geoviz_paleo_map",
    "CrossWellCanvas": "geoviz_cross_well",
    "PlotWidget": "geoviz_plots",
    "SurfaceWidget": "geoviz_plots",
}


def __getattr__(name: str):
    module_name = _COMPATIBILITY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(module_name), name)
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
    *_COMPATIBILITY_EXPORTS,
]
