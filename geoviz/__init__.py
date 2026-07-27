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
from .jobs import CancellationToken, JobCancelled
from .prepared_codec import (
    PAYLOAD_SCHEMA_VERSION,
    decode_prepared_preview,
    encode_prepared_preview,
)
from .registry import PreviewRegistry

# name → (module, attribute) for lazy workbench-facing exports.
_COMPATIBILITY_EXPORTS: dict[str, tuple[str, str]] = {
    "WellLogCanvas": ("geoviz_well_log", "WellLogCanvas"),
    "WellSectionCanvas": ("geoviz_well_log", "WellSectionCanvas"),
    "DatumTransformer": ("geoviz_well_log", "DatumTransformer"),
    "WellLogData": ("geoviz_well_log", "WellLogData"),
    "CurveData": ("geoviz_well_log", "CurveData"),
    "LineStyle": ("geoviz_well_log", "LineStyle"),
    "build_qpainter_tracks": ("geoviz_well_log", "build_qpainter_tracks"),
    "load_las_preview": ("geoviz_well_log.las_preview", "load_las_preview"),
    "load_xml_preview": ("geoviz_well_log.xml_preview", "load_xml_preview"),
    "inspect_las_file": ("geoviz_well_log.las_preview", "inspect_las_file"),
    "curve_data_from_arrays": ("geoviz_well_log.las_preview", "curve_data_from_arrays"),
    "compute_robust_display_range": ("geoviz_well_log", "compute_robust_display_range"),
    "export_svg": ("geoviz_well_log", "export_svg"),
    "export_pdf": ("geoviz_well_log", "export_pdf"),
    "export_png": ("geoviz_well_log", "export_png"),
    "SeismicView": ("geoviz_seismic", "SeismicView"),
    "ProfileWidget": ("geoviz_seismic", "ProfileWidget"),
    "SeismicLoader": ("geoviz_seismic.loader", "SeismicLoader"),
    "PaleoMapCanvas": ("geoviz_paleo_map", "PaleoMapCanvas"),
    "validate_polygon_geometry": ("geoviz_paleo_map.topology", "validate_polygon_geometry"),
    "export_professional_figure": ("geoviz_paleo_map", "export_professional_figure"),
    "CrossWellCanvas": ("geoviz_cross_well", "CrossWellCanvas"),
    "FormationTop": ("geoviz_cross_well.tops_model", "FormationTop"),
    "WellTieCanvas": ("geoviz_well_tie.canvas", "WellTieCanvas"),
    "PlotWidget": ("geoviz_plots", "PlotWidget"),
    "SurfaceWidget": ("geoviz_plots", "SurfaceWidget"),
    "PreviewRowIssue": ("geoviz.previews.dat", "PreviewRowIssue"),
    "XYPreviewDiagnostics": (
        "geoviz.previews.dat",
        "XYPreviewDiagnostics",
    ),
    "XYPreviewPayload": ("geoviz.previews.dat", "XYPreviewPayload"),
    "interpolate_idw": ("geoviz_plots", "interpolate_idw"),
    "interpolate_scipy": ("geoviz_plots", "interpolate_scipy"),
    "azimuth_to_rad": ("geoviz_plots", "azimuth_to_rad"),
    "directional_distance": ("geoviz_plots", "directional_distance"),
    "directional_trend_grid": ("geoviz_plots", "directional_trend_grid"),
    "directional_weights": ("geoviz_plots", "directional_weights"),
    "rotate_to_uv": ("geoviz_plots", "rotate_to_uv"),
    "trend_value_at": ("geoviz_plots", "trend_value_at"),
    "compute_sand_ratio": ("geoviz_plots", "compute_sand_ratio"),
    "median_absolute_deviation": ("geoviz_plots", "median_absolute_deviation"),
    "modified_z_scores": ("geoviz_plots", "modified_z_scores"),
    "extract_contour_lines": ("geoviz_plots", "extract_contour_lines"),
    "extract_filled_contours": ("geoviz_plots", "extract_filled_contours"),
    # Well-log interval models used when attaching facies/lithology tracks.
    "FaciesData": ("geoviz_well_log.models", "FaciesData"),
    "FaciesInterval": ("geoviz_well_log.models", "FaciesInterval"),
    "IntervalItem": ("geoviz_well_log.models", "IntervalItem"),
    "LithologyInterval": ("geoviz_well_log.models", "LithologyInterval"),
    "WellIntervals": ("geoviz_well_log.models", "WellIntervals"),
    # Downsample provider hook installed by the workbench at startup.
    "set_downsample_provider": ("geoviz_well_log.renderer.downsample", "set_downsample_provider"),
    "get_downsample_provider": ("geoviz_well_log.renderer.downsample", "get_downsample_provider"),
    "numpy_minmax_downsample": ("geoviz_well_log.renderer.downsample", "numpy_minmax_downsample"),
    # LAS parser provider hook installed by the workbench at startup.
    "set_las_parser_provider": ("geoviz_well_log.las_preview", "set_las_parser_provider"),
    "get_las_parser_provider": ("geoviz_well_log.las_preview", "get_las_parser_provider"),
    # Isosurface extractor hook installed by the workbench at startup.
    "set_isosurface_extractor": ("geoviz_seismic.isosurface", "set_isosurface_extractor"),
    "get_isosurface_extractor": ("geoviz_seismic.isosurface", "get_isosurface_extractor"),
    # Well–seismic joint 3D analysis (geoviz_well_seismic_3d).
    "WellSeismicScene": ("geoviz_well_seismic_3d", "WellSeismicScene"),
    "JointDisplaySettings": ("geoviz_well_seismic_3d", "JointDisplaySettings"),
    "JointWellId": ("geoviz_well_seismic_3d", "JointWellId"),
    "OrthogonalSliceState": (
        "geoviz_well_seismic_3d",
        "OrthogonalSliceState",
    ),
    "WellSeismicJointWidget": ("geoviz_well_seismic_3d", "WellSeismicJointWidget"),
    "WellHead": ("geoviz_well_seismic_3d", "WellHead"),
    "TimeDepthTable": ("geoviz_well_seismic_3d", "TimeDepthTable"),
    "TimeSliceState": ("geoviz_well_seismic_3d", "TimeSliceState"),
    "InMemoryVolumeAccess": ("geoviz_well_seismic_3d", "InMemoryVolumeAccess"),
    "VerticalDomain": ("geoviz_well_seismic_3d", "VerticalDomain"),
    "FenceSection": ("geoviz_well_seismic_3d", "FenceSection"),
    "VolumeRegistration": ("geoviz_well_seismic_3d", "VolumeRegistration"),
    "survey_corners_from_segy": ("geoviz_well_seismic_3d", "survey_corners_from_segy"),
    "horizon_corners_from_dat": ("geoviz_well_seismic_3d", "horizon_corners_from_dat"),
    "align_horizon_corners_to_loader_axes": (
        "geoviz_well_seismic_3d",
        "align_horizon_corners_to_loader_axes",
    ),
    "select_depth_transform": ("geoviz_well_seismic_3d", "select_depth_transform"),
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
    "CancellationToken",
    "JobCancelled",
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
