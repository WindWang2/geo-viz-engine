import numpy as np

def rdp_simplify(points: np.ndarray, epsilon: float) -> np.ndarray:
    """Simplify a path using the Ramer-Douglas-Peucker algorithm.

    Iterative (explicit stack) implementation — output is point-identical to
    the classic recursion but cannot hit ``RecursionError`` on long paths.
    """
    if len(points) < 3:
        return points

    n = len(points)
    keep = np.zeros(n, dtype=bool)
    keep[0] = True
    keep[-1] = True

    # Stack of (start_idx, end_idx) segments still to examine.
    stack = [(0, n - 1)]
    while stack:
        start_idx, end_idx = stack.pop()
        if end_idx - start_idx < 2:
            continue

        start = points[start_idx]
        end = points[end_idx]

        # Vector from start to end
        line_vec = end - start
        line_len_sq = np.sum(line_vec**2)

        segment = points[start_idx + 1:end_idx]
        if line_len_sq == 0.0:
            # Start and end are the same point, distance is just distance to start
            dists = np.sqrt(np.sum((segment - start)**2, axis=1))
        else:
            # Cross product of (start -> end) and (start -> points) gives the area
            # divided by line length gives height (distance)
            vecs = segment - start
            cross = vecs[:, 0] * line_vec[1] - vecs[:, 1] * line_vec[0]
            dists = np.abs(cross) / np.sqrt(line_len_sq)

        if len(dists) == 0:
            continue

        rel_index = int(np.argmax(dists))
        dmax = dists[rel_index]

        if dmax > epsilon:
            # index is for points[start_idx+1:end_idx], so actual index is +1
            split = start_idx + 1 + rel_index
            keep[split] = True
            stack.append((start_idx, split))
            stack.append((split, end_idx))

    return points[keep]
