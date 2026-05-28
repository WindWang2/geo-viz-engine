"""Hierarchical facies model for paleogeographic maps.

Builds a tree: Facies → SubFacies → MicroFacies from GeoJSON files
that have `level`, `id`, and `parent_id` properties.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FaciesFeature:
    """A single GeoJSON feature with hierarchy metadata."""
    id: str
    facies_name: str
    display_name: str
    level: str          # "facies" | "sub_facies" | "micro_facies"
    period: str
    parent_id: str | None
    geometry: dict      # raw GeoJSON geometry dict


@dataclass
class FaciesNode:
    """A node in the facies hierarchy tree."""
    feature: FaciesFeature
    children: list[FaciesNode] = field(default_factory=list)


class FaciesHierarchy:
    """Hierarchical tree of facies / sub-facies / micro-facies.

    Usage::

        hier = FaciesHierarchy.from_geojson_files([
            "test_paleo_facies.geojson",
            "test_paleo_sub_facies.geojson",
            "test_paleo_micro_facies.geojson",
        ])
        for root in hier.roots:
            print(root.feature.facies_name, len(root.children))
    """

    def __init__(self, roots: list[FaciesNode], by_id: dict[str, FaciesNode]):
        self.roots = roots
        self._by_id = by_id

    @classmethod
    def from_geojson_files(cls, file_paths: list[str]) -> FaciesHierarchy:
        """Build hierarchy from one or more GeoJSON files.

        Features must have `id` and `parent_id` properties to establish
        the tree structure. Features without `parent_id` become roots.
        """
        all_features: list[FaciesFeature] = []

        for fp in file_paths:
            with open(fp, encoding="utf-8") as f:
                data = json.load(f)
            for feat in data.get("features", []):
                props = feat.get("properties") or {}
                ff = FaciesFeature(
                    id=props.get("id", ""),
                    facies_name=props.get("facies") or props.get("name") or "",
                    display_name=props.get("name") or props.get("facies") or "",
                    level=props.get("level", ""),
                    period=props.get("period", ""),
                    parent_id=props.get("parent_id"),
                    geometry=feat.get("geometry") or {},
                )
                all_features.append(ff)

        return cls._build_tree(all_features)

    @classmethod
    def from_features(cls, features: list[dict]) -> FaciesHierarchy:
        """Build hierarchy from a flat list of GeoJSON feature dicts."""
        all_features: list[FaciesFeature] = []
        for feat in features:
            props = feat.get("properties") or {}
            ff = FaciesFeature(
                id=props.get("id", ""),
                facies_name=props.get("facies") or props.get("name") or "",
                display_name=props.get("name") or props.get("facies") or "",
                level=props.get("level", ""),
                period=props.get("period", ""),
                parent_id=props.get("parent_id"),
                geometry=feat.get("geometry") or {},
            )
            all_features.append(ff)
        return cls._build_tree(all_features)

    @classmethod
    def _build_tree(cls, features: list[FaciesFeature]) -> FaciesHierarchy:
        nodes: dict[str, FaciesNode] = {}
        roots: list[FaciesNode] = []

        # Create all nodes
        for ff in features:
            if ff.id:
                nodes[ff.id] = FaciesNode(feature=ff)

        # Link children to parents
        for ff in features:
            node = nodes.get(ff.id)
            if node is None:
                continue
            if ff.parent_id and ff.parent_id in nodes:
                nodes[ff.parent_id].children.append(node)
            elif not ff.parent_id:
                roots.append(node)

        return cls(roots=roots, by_id=nodes)

    def get_features_at_level(self, level: str) -> list[FaciesFeature]:
        """Get all features at a specific hierarchy level."""
        return [node.feature for node in self._by_id.values()
                if node.feature.level == level]

    def get_all_features(self) -> list[FaciesFeature]:
        """Get all features in the hierarchy."""
        return [node.feature for node in self._by_id.values()]

    def get_node(self, feature_id: str) -> FaciesNode | None:
        """Look up a node by its id."""
        return self._by_id.get(feature_id)

    def get_ancestors(self, feature_id: str) -> list[FaciesFeature]:
        """Get parent chain from root to this node (exclusive)."""
        chain = []
        node = self._by_id.get(feature_id)
        if node is None:
            return chain
        parent_id = node.feature.parent_id
        while parent_id and parent_id in self._by_id:
            parent = self._by_id[parent_id]
            chain.append(parent.feature)
            parent_id = parent.feature.parent_id
        chain.reverse()
        return chain

    def get_hierarchy_label(self, feature_id: str) -> str:
        """Build a display string like '相: 三角洲 > 亚相: 三角洲前缘'."""
        ancestors = self.get_ancestors(feature_id)
        node = self._by_id.get(feature_id)
        parts = []
        level_labels = {"facies": "相", "sub_facies": "亚相", "micro_facies": "微相"}
        for a in ancestors:
            label = level_labels.get(a.level, a.level)
            parts.append(f"{label}: {a.facies_name}")
        if node:
            label = level_labels.get(node.feature.level, node.feature.level)
            parts.append(f"{label}: {node.feature.facies_name}")
        return " > ".join(parts)
