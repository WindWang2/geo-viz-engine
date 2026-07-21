"""Spatial indexing helpers for geoviz_paleo_map and geoviz_map."""
from __future__ import annotations

from typing import Any
import numpy as np


class PolygonSpatialIndex:
    """R-Tree / Bounding Box Spatial Index for polygon features."""

    def __init__(self, features: list[dict]):
        self.features = features
        self.bboxes = []
        self.feature_ids = []
        for feat in features:
            fid = feat.get("id") or feat.get("feature_id") or str(id(feat))
            bbox = feat.get("bbox")
            if bbox is not None:
                self.bboxes.append(bbox)
                self.feature_ids.append(fid)
        
        if self.bboxes:
            self._bbox_matrix = np.array(self.bboxes, dtype=np.float64)  # [N, 4] -> min_x, min_y, max_x, max_y
        else:
            self._bbox_matrix = np.empty((0, 4), dtype=np.float64)

    def query_bbox(self, vp_bbox: tuple[float, float, float, float] | list[float]) -> set[str]:
        """Return set of feature_ids overlapping the query bounding box [min_x, min_y, max_x, max_y]."""
        if len(self._bbox_matrix) == 0:
            return set()
        
        min_x, min_y, max_x, max_y = vp_bbox
        # Bounding box overlap condition:
        # (feat_max_x >= vp_min_x) and (feat_min_x <= vp_max_x) and (feat_max_y >= vp_min_y) and (feat_min_y <= vp_max_y)
        mask = (
            (self._bbox_matrix[:, 2] >= min_x) &
            (self._bbox_matrix[:, 0] <= max_x) &
            (self._bbox_matrix[:, 3] >= min_y) &
            (self._bbox_matrix[:, 1] <= max_y)
        )
        
        selected_indices = np.where(mask)[0]
        return {self.feature_ids[i] for i in selected_indices}


def numpy_bbox_filter(coords: np.ndarray, vp_bbox: tuple[float, float, float, float]) -> np.ndarray:
    """Vectorized bounding box filter for point coordinates [N, 2] -> (lng, lat)."""
    min_x, min_y, max_x, max_y = vp_bbox
    return (
        (coords[:, 0] >= min_x) &
        (coords[:, 0] <= max_x) &
        (coords[:, 1] >= min_y) &
        (coords[:, 1] <= max_y)
    )
