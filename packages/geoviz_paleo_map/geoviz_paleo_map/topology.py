"""Topology model for shared-vertex polygon editing."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TopologyVertex:
    """A shared point referenced by multiple polygon rings."""
    x: float  # longitude (world coord)
    y: float  # latitude (world coord)
    id: int   # unique vertex ID


@dataclass
class RingRef:
    """An ordered list of vertex IDs forming a closed polygon ring."""
    vertex_ids: list[int]


@dataclass
class FeatureRef:
    """A feature's geometry as references into the topology graph."""
    feature_id: str
    rings: list[RingRef]       # outer ring + holes
    level: str                 # "facies" | "sub_facies" | "micro_facies"
    parent_id: str | None
    source_file: str | None    # for hierarchy-aware save
    properties: dict           # original GeoJSON properties


@dataclass
class TopologyModel:
    """Complete topology: vertices + feature references."""
    vertices: list[TopologyVertex] = field(default_factory=list)
    features: list[FeatureRef] = field(default_factory=list)
