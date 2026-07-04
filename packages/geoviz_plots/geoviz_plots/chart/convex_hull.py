"""Point-in-polygon ray casting and SciPy Convex Hull calculation helpers."""
from typing import Sequence, Tuple
import numpy as np
from scipy.spatial import ConvexHull

def point_in_polygon_mask(x: np.ndarray, y: np.ndarray, poly_vertices: Sequence[Tuple[float, float]]) -> np.ndarray:
    """Vectorized point-in-polygon test using ray-casting algorithm.
    
    Returns boolean mask of shape (N,) indicating whether each point (x_i, y_i) is inside the polygon.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    N = len(x)
    inside = np.zeros(N, dtype=bool)

    n_vert = len(poly_vertices)
    if n_vert < 3:
        return inside

    poly = np.asarray(poly_vertices, dtype=np.float64)
    px, py = poly[:, 0], poly[:, 1]

    j = n_vert - 1
    for i in range(n_vert):
        xi, yi = px[i], py[i]
        xj, yj = px[j], py[j]

        # Check ray intersection
        intersect = ((yi > y) != (yj > y)) & (x < (xj - xi) * (y - yi) / np.maximum(1e-12, (yj - yi)) + xi)
        inside ^= intersect
        j = i

    return inside

def compute_convex_hull(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Compute 2D Convex Hull polygon vertices array of shape (K, 2)."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    
    mask = ~np.isnan(x) & ~np.isnan(y)
    x = x[mask]
    y = y[mask]

    if len(x) < 3:
        return np.column_stack([x, y])

    points = np.column_stack([x, y])
    hull = ConvexHull(points)
    return points[hull.vertices]
