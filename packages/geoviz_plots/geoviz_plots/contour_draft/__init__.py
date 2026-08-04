"""Contour draft extraction: isolines from interpolation grids (ISS-DOM-03).

Promoted pure-numpy core from ``paleo_workbench/workflow/contour_draft.py``
(Phase-2 promote-down, map #244 / PR-A #256). The Workbench-side adapter
(``paleo_workbench/workflow/contour_draft.py``) keeps the ``FactorMapTask`` /
``ProjectDocument`` / ``ContourDraft`` (pydantic) coupling; this module
operates on plain arrays and a local ``ContourSegment`` dataclass so the
engine has no dependency on ``paleo_workbench.project.models`` (T10 decision:
``project/models.py`` is not promoted).

The split:
- **here (pure):** ``suggest_levels``, ``coerce_grid``, ``extract_contour_segments``,
  ``segments_to_line_features``, ``ContourSegment`` (local dataclass).
- **Workbench adapter (stays):** ``_grid_from_task``, ``contour_draft_from_factor_task``,
  ``upsert_contour_draft``, ``apply_contour_draft_to_map``, ``compile_*``.
"""

from __future__ import annotations

from geoviz_plots.contour_draft.levels import DEFAULT_N_LEVELS, GENERATOR_VERSION, suggest_levels
from geoviz_plots.contour_draft.segments import (
    ContourSegment,
    coerce_grid,
    extract_contour_segments,
    segments_to_line_features,
)

__all__ = [
    "GENERATOR_VERSION",
    "DEFAULT_N_LEVELS",
    "ContourSegment",
    "suggest_levels",
    "coerce_grid",
    "extract_contour_segments",
    "segments_to_line_features",
]
