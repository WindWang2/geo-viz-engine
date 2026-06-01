"""Spatial scattered points interpolation engines."""
from geoviz_plots.interpolation.idw import interpolate_idw
from geoviz_plots.interpolation.scipy_grid import interpolate_scipy

__all__ = ["interpolate_idw", "interpolate_scipy"]
