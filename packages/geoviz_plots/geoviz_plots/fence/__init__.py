"""Cross-well 3D curtain/fence mesh generator and inter-well seismic slice extractor.

Promoted from `paleo_workbench/viz/geomodel/fence_generator.py` (Phase-2 promote-down,
map #244 / PR-A). Headless numpy — no Qt / OpenGL dependency.
"""

from __future__ import annotations

from geoviz_plots.fence.fence_generator import (
    CrossWellFenceGenerator,
    generate_fence_mesh,
)

__all__ = [
    "CrossWellFenceGenerator",
    "generate_fence_mesh",
]
