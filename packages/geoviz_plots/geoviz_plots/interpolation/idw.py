"""NumPy vectorized Inverse Distance Weighting (IDW) interpolation."""
import numpy as np

def interpolate_idw(x, y, z, grid_x, grid_y, power: float = 2.0, epsilon: float = 1e-12) -> np.ndarray:
    """Interpolate scattered 3D points (x, y, z) onto a grid (grid_x, grid_y) using vectorized IDW.
    
    Filters out NaNs prior to calculation.
    
    Args:
        x, y, z: 1D arrays of scattered point coordinates and values.
        grid_x, grid_y: 1D coordinate arrays defining the target interpolation grid.
        power: Power parameter for weighting (standard is 2.0).
        epsilon: Small buffer value to avoid division by zero.
        
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
    
    if len(x) == 0:
        return np.zeros((len(grid_y), len(grid_x)))
        
    grid_x = np.asarray(grid_x, dtype=np.float64)
    grid_y = np.asarray(grid_y, dtype=np.float64)
    
    # Create meshgrid
    X, Y = np.meshgrid(grid_x, grid_y)  # shape (H, W)
    
    # Compute distances to all points: expand X, Y to (H, W, N) and broadcast
    dx = X[:, :, np.newaxis] - x  # shape (H, W, N)
    dy = Y[:, :, np.newaxis] - y  # shape (H, W, N)
    dist = np.hypot(dx, dy)       # shape (H, W, N)
    
    # Bound the distance to avoid division by zero
    dist = np.maximum(dist, epsilon)
    
    # Calculate weights
    weights = 1.0 / (dist ** power)
    sum_weights = np.sum(weights, axis=-1)
    
    # Ensure sum_weights is non-zero to protect against zero-division
    sum_weights = np.maximum(sum_weights, epsilon)
    
    grid_z = np.sum(weights * z, axis=-1) / sum_weights
    return grid_z
