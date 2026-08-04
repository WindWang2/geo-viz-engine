"""Map-edit geometry API and transactional feature editor.

Promoted from ``paleo_workbench/mapping/map_edit_api.py`` and
``feature_editor.py`` (Phase-2 promote-down, map #244 / PR-A #256).

The third Workbench sibling, ``reference_layers.py``, is NOT promoted: it's
an adapter layer (every function takes/returns ``MapReferenceLayer`` from
``paleo_workbench.project.models``) plus a GDAL dependency the engine doesn't
carry. It stays in Workbench.
"""

from __future__ import annotations

from geoviz_plots.map_edit.api import (
    HAS_CPP,
    HAS_SHAPELY,
    SnapCandidateIndex,
    closest_edge,
    delete_vertex,
    hit_test,
    insert_vertex,
    merge_rings,
    move_features,
    rebuild_topology,
    set_vertex,
    snap_point,
    snap_point_indexed,
    snap_shared_nodes,
    split_ring_by_line,
    validate_adjacency,
    validate_ring,
)
from geoviz_plots.map_edit.feature_editor import FeatureEditor, TopologyError

__all__ = [
    "HAS_CPP",
    "HAS_SHAPELY",
    "FeatureEditor",
    "TopologyError",
    "SnapCandidateIndex",
    "closest_edge",
    "delete_vertex",
    "hit_test",
    "insert_vertex",
    "merge_rings",
    "move_features",
    "rebuild_topology",
    "set_vertex",
    "snap_point",
    "snap_point_indexed",
    "snap_shared_nodes",
    "split_ring_by_line",
    "validate_adjacency",
    "validate_ring",
]
