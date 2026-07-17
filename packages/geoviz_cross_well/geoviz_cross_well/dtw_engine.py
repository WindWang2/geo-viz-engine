from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

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
        if band_radius is None:
            band_radius = max(20, max(n, m) // 4)

        # Compact cost matrix: row i, column j maps to cost_compact[i, j - (i - band_radius)]
        # width = 2 * band_radius + 1
        width = 2 * band_radius + 1
        cost_compact = np.full((n, width), np.inf)
        
        def get_compact_idx(i, j):
            return j - (i - band_radius)

        # Initialize (0,0)
        # i=0, j=0 => idx = 0 - (0 - band_radius) = band_radius
        start_idx = get_compact_idx(0, 0)
        cost_compact[0, start_idx] = np.abs(ref_curve[0] - target_curve[0])
        
        # Cumulative first row
        for j in range(1, min(m, band_radius + 1)):
            idx = get_compact_idx(0, j)
            cost_compact[0, idx] = cost_compact[0, idx-1] + np.abs(ref_curve[0] - target_curve[j])

        progress_step = max(1, n // 20)
        for i in range(1, n):
            j_start = max(0, i - band_radius)
            j_end = min(m, i + band_radius + 1)

            # Recurrence for the current row:
            #   c[j] = dist[j] + min(diagonal[j], vertical[j], c[j-1])
            # The horizontal dependency is a min-plus prefix scan.  Rewriting
            # it with cumulative distances lets NumPy evaluate the whole band
            # without the former ~500k Python scalar loop for 1k samples.
            current_idx = np.arange(j_start, j_end) - i + band_radius
            diagonal = cost_compact[i - 1, current_idx]
            vertical = np.full(diagonal.shape, np.inf, dtype=np.float64)
            vertical_valid = current_idx + 1 < width
            vertical[vertical_valid] = cost_compact[
                i - 1, current_idx[vertical_valid] + 1
            ]
            base = np.minimum(diagonal, vertical)
            row_dist = np.abs(ref_curve[i] - target_curve[j_start:j_end])
            prefix = np.cumsum(row_dist, dtype=np.float64)
            prefix_before = np.empty_like(prefix)
            prefix_before[0] = 0.0
            prefix_before[1:] = prefix[:-1]
            row_cost = prefix + np.minimum.accumulate(base - prefix_before)
            cost_compact[i, current_idx] = row_cost

            if progress_callback is not None and (i % progress_step == 0 or i == n - 1):
                progress_callback(i + 1, n)

        # Backtrace
        i, j = n - 1, m - 1
        path: list[tuple[int, int]] = [(i, j)]
        total_dist = 0.0
        
        while i > 0 or j > 0:
            candidates = []
            # Diag
            if i > 0 and j > 0:
                idx = get_compact_idx(i-1, j-1)
                if 0 <= idx < width: candidates.append((cost_compact[i-1, idx], i-1, j-1))
            # Vert
            if i > 0:
                idx = get_compact_idx(i-1, j)
                if 0 <= idx < width: candidates.append((cost_compact[i-1, idx], i-1, j))
            # Horiz
            if j > 0:
                idx = get_compact_idx(i, j-1)
                if 0 <= idx < width: candidates.append((cost_compact[i, idx], i, j-1))
            
            if not candidates: break
            c_val, ni, nj = min(candidates, key=lambda x: x[0])
            if c_val == np.inf: break
            
            total_dist += np.abs(ref_curve[i] - target_curve[j]) # distance of current step
            i, j = ni, nj
            path.append((i, j))
            
        total_dist += np.abs(ref_curve[0] - target_curve[0]) # distance of start
        path.reverse()
        
        normalized_cost = total_dist / len(path)

        if ref_depth is None:
            ref_idx = n // 2
        else:
            ref_idx = int(np.argmin(np.abs(ref_depths - ref_depth)))

        target_indices = [pj for pi, pj in path if pi == ref_idx]
        if target_indices:
            matched_target_idx = int(np.median(target_indices))
        else:
            # find closest i in path
            closest_p_idx = np.argmin([abs(pi - ref_idx) for pi, pj in path])
            matched_target_idx = path[closest_p_idx][1]
            
        suggested_depth = float(target_depths[matched_target_idx])

        # Confidence calculation
        max_diff = np.max(np.abs(ref_curve)) + np.max(np.abs(target_curve))
        norm_cost = min(normalized_cost / max(1e-6, max_diff), 1.0)

        return DTWResult(
            suggested_depth=suggested_depth,
            cost=norm_cost,
            confidence=1.0 - norm_cost,
        )
