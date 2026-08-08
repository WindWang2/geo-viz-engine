"""geoviz_plots — General-purpose 2D plotting and point-to-surface contour rendering library."""

__version__ = "0.1.0"

from geoviz_plots.chart.axes import calculate_ticks, nice_number
from geoviz_plots.chart.series import Series, LineSeries, ScatterSeries, lttb_downsample
from geoviz_plots.chart.plot_widget import PlotWidget

from geoviz_plots.interpolation.idw import interpolate_idw
from geoviz_plots.interpolation.directional import (
    azimuth_to_rad,
    directional_distance,
    directional_trend_grid,
    directional_weights,
    rotate_to_uv,
    trend_value_at,
)
from geoviz_plots.interpolation.scipy_grid import interpolate_scipy, InterpolationWorker
from geoviz_plots.analytics import (
    compute_sand_ratio,
    median_absolute_deviation,
    modified_z_scores,
)

from geoviz_plots.surface.marching_squares import extract_contour_lines, extract_filled_contours, BandedFill
from geoviz_plots.surface.surface_widget import SurfaceWidget

from geoviz_plots.crs import (
    coerce_to_project_crs,
    get_project_crs,
    list_known_crs,
    set_project_crs,
)

from geoviz_plots.fence import CrossWellFenceGenerator, generate_fence_mesh

from geoviz_plots.geomodel import (
    BoreholeTraceGenerator,
    FaultCuttingEngine,
    TunnelMeshGenerator,
    generate_cylinder_geometry,
    generate_fault_geometry,
    generate_tube_geometry,
    get_seam_boundaries,
)

from geoviz_plots.contour_draft import (
    ContourSegment,
    DEFAULT_N_LEVELS,
    GENERATOR_VERSION,
    coerce_grid,
    extract_contour_segments,
    segments_to_line_features,
    suggest_levels,
)

from geoviz_plots.factor import (
    DEFAULT_FACTOR_TYPES,
    DEFAULT_GRID_N,
    DEFAULT_SEMI_MAJOR,
    DEFAULT_SEMI_MINOR,
    MAX_LOO_SAMPLES,
    extract_xy_values,
    extract_xy_z_weights,
    interpolate_factor_grid,
    method_to_backend,
    mvp_note_for,
    resolve_anisotropy_params,
    snapshot_hash,
    synthetic_sample_points,
)

from geoviz_plots.map_edit import (
    FeatureEditor,
    HAS_CPP,
    HAS_SHAPELY,
    SnapCandidateIndex,
    TopologyError,
    closest_edge,
    delete_vertex,
    hit_test,
    insert_vertex,
    merge_rings,
    move_features,
    rebuild_topology,
    set_vertex,
    snap_point,
    snap_point_indexed,
    snap_shared_nodes,
    split_ring_by_line,
    validate_adjacency,
    validate_ring,
)

__all__ = [
    "calculate_ticks",
    "nice_number",
    "Series",
    "LineSeries",
    "ScatterSeries",
    "lttb_downsample",
    "PlotWidget",
    "interpolate_idw",
    "azimuth_to_rad",
    "directional_distance",
    "directional_trend_grid",
    "directional_weights",
    "rotate_to_uv",
    "trend_value_at",
    "compute_sand_ratio",
    "median_absolute_deviation",
    "modified_z_scores",
    "interpolate_scipy",
    "InterpolationWorker",
    "extract_contour_lines",
    "extract_filled_contours",
    "BandedFill",
    "SurfaceWidget",
    "coerce_to_project_crs",
    "get_project_crs",
    "list_known_crs",
    "set_project_crs",
    "CrossWellFenceGenerator",
    "generate_fence_mesh",
    "BoreholeTraceGenerator",
    "FaultCuttingEngine",
    "TunnelMeshGenerator",
    "generate_cylinder_geometry",
    "generate_fault_geometry",
    "generate_tube_geometry",
    "get_seam_boundaries",
    "ContourSegment",
    "DEFAULT_N_LEVELS",
    "GENERATOR_VERSION",
    "coerce_grid",
    "extract_contour_segments",
    "segments_to_line_features",
    "suggest_levels",
    "DEFAULT_FACTOR_TYPES",
    "DEFAULT_GRID_N",
    "DEFAULT_SEMI_MAJOR",
    "DEFAULT_SEMI_MINOR",
    "MAX_LOO_SAMPLES",
    "extract_xy_values",
    "extract_xy_z_weights",
    "interpolate_factor_grid",
    "method_to_backend",
    "mvp_note_for",
    "resolve_anisotropy_params",
    "snapshot_hash",
    "synthetic_sample_points",
    "FeatureEditor",
    "HAS_CPP",
    "HAS_SHAPELY",
    "SnapCandidateIndex",
    "TopologyError",
    "closest_edge",
    "delete_vertex",
    "hit_test",
    "insert_vertex",
    "merge_rings",
    "move_features",
    "rebuild_topology",
    "set_vertex",
    "snap_point",
    "snap_point_indexed",
    "snap_shared_nodes",
    "split_ring_by_line",
    "validate_adjacency",
    "validate_ring",
]
