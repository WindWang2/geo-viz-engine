"""geoviz_plots — General-purpose 2D plotting and point-to-surface contour rendering library."""

__version__ = "0.1.0"

from geoviz_plots.chart.axes import calculate_ticks, nice_number
from geoviz_plots.chart.series import Series, LineSeries, ScatterSeries, lttb_downsample
from geoviz_plots.chart.plot_widget import PlotWidget

from geoviz_plots.interpolation.idw import interpolate_idw
from geoviz_plots.interpolation.scipy_grid import interpolate_scipy, InterpolationWorker

from geoviz_plots.surface.marching_squares import extract_contour_lines, extract_filled_contours
from geoviz_plots.surface.surface_widget import SurfaceWidget

__all__ = [
    "calculate_ticks",
    "nice_number",
    "Series",
    "LineSeries",
    "ScatterSeries",
    "lttb_downsample",
    "PlotWidget",
    "interpolate_idw",
    "interpolate_scipy",
    "InterpolationWorker",
    "extract_contour_lines",
    "extract_filled_contours",
    "SurfaceWidget",
]
