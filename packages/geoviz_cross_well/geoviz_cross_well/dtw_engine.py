from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

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
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> DTWResult:
        if len(ref_curve) < 2 or len(target_curve) < 2:
            return DTWResult(suggested_depth=0.0, cost=1.0, confidence=0.0)

        n, m = len(ref_curve), len(target_curve)
        # Default band radius bounded to keep typical 1k-sample DTW under ~0.1s
        # while still allowing generous warping (25% of the longer curve).
        if band_radius is None:
            band_radius = max(20, max(n, m) // 4)

        ref_2d = ref_curve.reshape(-1, 1)
        tgt_2d = target_curve.reshape(-1, 1)
        dist = cdist(ref_2d, tgt_2d, metric="euclidean")

        cost_matrix = np.full((n, m), np.inf)
        cost_matrix[0, 0] = dist[0, 0]

        # Vectorized row-by-row Sakoe-Chiba banded DTW.
        # For each row i, we compute the band slice [j_start:j_end].
        # The vertical+diagonal predecessors (cost[i-1, j] and cost[i-1, j-1])
        # are independent of intra-row order, so we evaluate them with a single
        # numpy min. The horizontal predecessor (cost[i, j-1]) is a serial
        # chain along j, so we sweep it once in a tight scalar Python loop —
        # but with no list-building or tuple-min per cell.
        progress_step = max(1, n // 20)
        for i in range(n):
            j_start = max(0, i - band_radius)
            j_end = min(m, i + band_radius + 1)
            if j_end <= j_start:
                continue
            row_dist = dist[i, j_start:j_end]

            if i == 0:
                # First row: cumulative left-only chain after (0,0) seed.
                # cost[0, j] = dist[0, 0] + sum(dist[0, 1:j+1])
                if j_start == 0:
                    cost_matrix[0, 0:j_end] = np.cumsum(row_dist)
                # i==0 and j_start>0 is unreachable (band_radius>=0)
            else:
                prev_row = cost_matrix[i - 1, j_start:j_end]
                # Diagonal predecessor cost[i-1, j-1] — shift right by 1.
                if j_start > 0:
                    diag = cost_matrix[i - 1, j_start - 1:j_end - 1]
                else:
                    diag = np.empty_like(prev_row)
                    diag[0] = np.inf
                    diag[1:] = cost_matrix[i - 1, 0:j_end - 1]
                vbase = np.minimum(prev_row, diag) + row_dist

                # Horizontal serial sweep
                out = cost_matrix[i, j_start:j_end]
                prev_h = np.inf
                for k in range(j_end - j_start):
                    h_candidate = prev_h + row_dist[k]
                    v = vbase[k]
                    cur = v if v < h_candidate else h_candidate
                    out[k] = cur
                    prev_h = cur

            if progress_callback is not None and (i % progress_step == 0 or i == n - 1):
                progress_callback(i + 1, n)

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
