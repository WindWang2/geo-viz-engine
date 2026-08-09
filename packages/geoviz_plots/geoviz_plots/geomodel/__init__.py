"""Headless geometry generators for 3D geological models.

Promoted from ``paleo_workbench/viz/geomodel/`` (阶段 1 engine sink-down, see
``docs/agents/geo-viz-boundary.md``). Everything here is pure numpy with no Qt /
OpenGL dependency, so it is safe to call from worker threads.

- :mod:`~geoviz_plots.geomodel.primitives` — cylinder / swept tube / faulted surface meshes
- :mod:`~geoviz_plots.geomodel.borehole_tunnel` — seam-based borehole segmentation, RMF tunnel tubes
- :mod:`~geoviz_plots.geomodel.fault_dislocation` — fault throw with optional drag decay
"""

from __future__ import annotations

from geoviz_plots.geomodel.borehole_tunnel import (
    BoreholeTraceGenerator,
    TunnelMeshGenerator,
    get_seam_boundaries,
)
from geoviz_plots.geomodel.fault_dislocation import FaultCuttingEngine
from geoviz_plots.geomodel.primitives import (
    generate_cylinder_geometry,
    generate_fault_geometry,
    generate_tube_geometry,
)

__all__ = [
    "BoreholeTraceGenerator",
    "FaultCuttingEngine",
    "TunnelMeshGenerator",
    "generate_cylinder_geometry",
    "generate_fault_geometry",
    "generate_tube_geometry",
    "get_seam_boundaries",
]
