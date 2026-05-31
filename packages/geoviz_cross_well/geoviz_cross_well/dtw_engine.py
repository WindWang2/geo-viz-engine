from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.spatial.distance import cdist


@dataclass
class DTWResult:
    suggested_depth: float
    cost: float
    confidence: float


class DTWEngine:
    def correlate(
        self,
        ref_curve: np.ndarray,
        ref_depths: np.ndarray,
        target_curve: np.ndarray,
        target_depths: np.ndarray,
        band_radius: int | None = None,
        ref_depth: float | None = None,
    ) -> DTWResult:
        if len(ref_curve) < 2 or len(target_curve) < 2:
            return DTWResult(suggested_depth=0.0, cost=1.0, confidence=0.0)

        n, m = len(ref_curve), len(target_curve)
        if band_radius is None:
            band_radius = max(n, m)

        ref_2d = ref_curve.reshape(-1, 1)
        tgt_2d = target_curve.reshape(-1, 1)
        dist = cdist(ref_2d, tgt_2d, metric="euclidean")

        cost_matrix = np.full((n, m), np.inf)
        cost_matrix[0, 0] = dist[0, 0]

        for i in range(n):
            j_start = max(0, i - band_radius)
            j_end = min(m, i + band_radius + 1)
            for j in range(j_start, j_end):
                if i == 0 and j == 0:
                    continue
                prev = []
                if i > 0:
                    prev.append(cost_matrix[i - 1, j])
                if j > 0:
                    prev.append(cost_matrix[i, j - 1])
                if i > 0 and j > 0:
                    prev.append(cost_matrix[i - 1, j - 1])
                cost_matrix[i, j] = dist[i, j] + min(prev)

        i, j = n - 1, m - 1
        path: list[tuple[int, int]] = [(i, j)]
        while i > 0 or j > 0:
            candidates = []
            if i > 0 and j > 0:
                candidates.append((cost_matrix[i - 1, j - 1], i - 1, j - 1))
            if i > 0:
                candidates.append((cost_matrix[i - 1, j], i - 1, j))
            if j > 0:
                candidates.append((cost_matrix[i, j - 1], i, j - 1))
            if not candidates:
                break
            _, ni, nj = min(candidates, key=lambda x: x[0])
            i, j = ni, nj
            path.append((i, j))

        path.reverse()
        total_cost = sum(dist[pi, pj] for pi, pj in path)
        normalized_cost = total_cost / len(path)

        if ref_depth is None:
            ref_idx = n // 2
        else:
            ref_idx = int(np.argmin(np.abs(ref_depths - ref_depth)))

        target_indices = [pj for pi, pj in path if pi == ref_idx]
        if target_indices:
            matched_target_idx = int(np.median(target_indices))
        else:
            matched_target_idx = path[min(ref_idx, len(path) - 1)][1]
        suggested_depth = float(target_depths[matched_target_idx])

        max_possible = float(np.max(dist)) if dist.size > 0 else 1.0
        norm_cost = min(normalized_cost / max_possible, 1.0) if max_possible > 0 else 0.0

        return DTWResult(
            suggested_depth=suggested_depth,
            cost=norm_cost,
            confidence=1.0 - norm_cost,
        )
