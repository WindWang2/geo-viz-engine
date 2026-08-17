"""SciPy-based spatial interpolation algorithms and convex hull masking."""
import logging

import numpy as np
from scipy.interpolate import griddata, Rbf
from scipy.spatial import ConvexHull, QhullError
from matplotlib.path import Path

logger = logging.getLogger(__name__)

_SCIPY_METHODS = ("linear", "cubic", "nearest", "rbf")


def interpolate_scipy(x, y, z, grid_x, grid_y, method: str = "linear",
                      mask_convex_hull: bool = True, status: dict | None = None) -> np.ndarray:
    """Interpolate scattered points (x, y, z) onto grid (grid_x, grid_y) using SciPy methods.
    
    Filters out NaNs prior to computation.
    
    Args:
        x, y, z: 1D coordinate arrays of scattered points.
        grid_x, grid_y: 1D coordinate arrays defining the target grid.
        method: "linear", "cubic", "nearest", or "rbf".
        mask_convex_hull: If True, masks out (sets to NaN) all grid points that lie
                          outside the convex hull of the input data points.
        status: Optional dict filled when the requested method degrades (e.g.
                ``{"fallback": "nearest", "requested_method": "linear"}``).
                          
    Returns:
        A 2D array of interpolated values with shape (len(grid_y), len(grid_x)).
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    z = np.asarray(z, dtype=np.float64)
    
    # Filter NaNs
    mask = ~np.isnan(x) & ~np.isnan(y) & ~np.isnan(z)
    x = x[mask]
    y = y[mask]
    z = z[mask]
    
    if len(x) < 3:
        # SciPy methods require at least 3 points
        return np.full((len(grid_y), len(grid_x)), np.nan)

    if method not in _SCIPY_METHODS:
        raise ValueError(f"Unknown interpolation method: {method}")
        
    grid_x = np.asarray(grid_x, dtype=np.float64)
    grid_y = np.asarray(grid_y, dtype=np.float64)
    X, Y = np.meshgrid(grid_x, grid_y)
    
    # 1. Perform Interpolation
    try:
        if method == "rbf":
            rbf_func = Rbf(x, y, z, function="multiquadric")
            grid_z = rbf_func(X, Y)
        else:
            points = np.column_stack((x, y))
            grid_z = griddata(points, z, (X, Y), method=method)
    except (QhullError, ValueError, np.linalg.LinAlgError) as exc:
        logger.warning(
            "interpolate_scipy method=%s failed (%s); falling back to nearest",
            method, exc,
        )
        if status is not None:
            status["fallback"] = "nearest"
            status["requested_method"] = method
        try:
            points = np.column_stack((x, y))
            grid_z = griddata(points, z, (X, Y), method="nearest")
        except Exception:
            return np.full((len(grid_y), len(grid_x)), np.nan)
            
    # 2. Mask points outside the Convex Hull of input data
    if mask_convex_hull:
        try:
            points_2d = np.column_stack((x, y))
            hull = ConvexHull(points_2d)
            hull_vertices = points_2d[hull.vertices]
            hull_path = Path(hull_vertices)
            
            # Check grid points containment
            grid_points = np.column_stack((X.ravel(), Y.ravel()))
            containment_mask = hull_path.contains_points(grid_points)
            containment_mask = containment_mask.reshape(X.shape)
            
            # Mask out outside points
            grid_z[~containment_mask] = np.nan
        except Exception:
            # Skip convex hull masking if points are collinear or hull generation fails
            pass
            
    return grid_z


from PySide6.QtCore import QThread, Signal
from geoviz_plots.interpolation.idw import interpolate_idw

class InterpolationWorker(QThread):
    """Asynchronous worker thread for spatial interpolation calculations.
    
    Excludes calculation workloads from the PySide main GUI thread to avoid UI freeze.
    """
    result_ready = Signal(np.ndarray)
    error = Signal(str)
    
    def __init__(self, x, y, z, grid_x, grid_y, method="linear", mask_convex_hull=True, power=2.0):
        super().__init__()
        self.x = x
        self.y = y
        self.z = z
        self.grid_x = grid_x
        self.grid_y = grid_y
        self.method = method
        self.mask_convex_hull = mask_convex_hull
        self.power = power
        
    def run(self):
        try:
            if self.method == "idw":
                grid_z = interpolate_idw(
                    self.x, self.y, self.z, 
                    self.grid_x, self.grid_y, 
                    power=self.power
                )
            else:
                grid_z = interpolate_scipy(
                    self.x, self.y, self.z, 
                    self.grid_x, self.grid_y, 
                    method=self.method, 
                    mask_convex_hull=self.mask_convex_hull
                )
            self.result_ready.emit(grid_z)
        except Exception as e:
            self.error.emit(str(e))

