import numpy as np

def rdp_simplify(points: np.ndarray, epsilon: float) -> np.ndarray:
    """Simplify a path using the Ramer-Douglas-Peucker algorithm."""
    if len(points) < 3:
        return points

    # Find the point with the maximum distance from the line segment between start and end
    start = points[0]
    end = points[-1]
    
    # Vector from start to end
    line_vec = end - start
    line_len_sq = np.sum(line_vec**2)
    
    if line_len_sq == 0.0:
        # Start and end are the same point, distance is just distance to start
        dists = np.sum((points[1:-1] - start)**2, axis=1)
        dists = np.sqrt(dists)
    else:
        # Cross product of (start -> end) and (start -> points) gives the area
        # divided by line length gives height (distance)
        vecs = points[1:-1] - start
        cross = vecs[:, 0] * line_vec[1] - vecs[:, 1] * line_vec[0]
        dists = np.abs(cross) / np.sqrt(line_len_sq)

    if len(dists) == 0:
        dmax = 0
        index = 0
    else:
        index = np.argmax(dists)
        dmax = dists[index]

    if dmax > epsilon:
        # Recursive call
        # index is for points[1:-1], so actual index is index + 1
        rec_results1 = rdp_simplify(points[:index + 2], epsilon)
        rec_results2 = rdp_simplify(points[index + 1:], epsilon)
        
        # Combine, skipping the duplicated point
        return np.vstack((rec_results1[:-1], rec_results2))
    else:
        return np.array([start, end])
