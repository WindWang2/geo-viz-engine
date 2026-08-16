"""Point-in-polygon ray casting and SciPy Convex Hull calculation helpers."""
from typing import Sequence, Tuple
import numpy as np
from scipy.spatial import ConvexHull, QhullError

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

        # Check ray intersection. Sign-preserving zero guard: the previous
        # np.maximum(1e-12, yj - yi) flipped the sign of every descending
        # edge's denominator, so the crossing x evaluated to +/-1e12 and the
        # test degenerated to "x < xi iff xj > xi" — non-axis-aligned
        # polygons (any freehand lasso) selected inverted/wrong points
        # (#506). Edges that straddle y (the only ones the mask admits)
        # have yj != yi, so the guard only fires for exact-horizontal edges.
        den = np.where(yj != yi, yj - yi, 1e-30)
        intersect = ((yi > y) != (yj > y)) & (x < (xj - xi) * (y - yi) / den + xi)
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
    try:
        hull = ConvexHull(points)
        return points[hull.vertices]
    except QhullError:
        # Collinear points or fewer than 3 distinct locations make qhull's
        # initial simplex flat. Return the degenerate selection itself
        # (lexsorted into a stable polyline) instead of raising out of the
        # lasso event handler — the cluster and points_selected signal must
        # still fire (#557).
        order = np.lexsort((points[:, 1], points[:, 0]))
        return points[order]
