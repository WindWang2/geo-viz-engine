"""Factor-map interpolation pure core (IDW / SciPy / directional trend).

Promoted from ``paleo_workbench/workflow/factor_interpolation.py`` and
``paleo_workbench/workflow/directional_trend.py`` (Phase-2 promote-down,
map #244 / PR-A #256). Pure numpy + the ``geoviz`` facade; no dependency on
``paleo_workbench.project.models`` (T10 decision: ``project/models.py`` is
not promoted).

The split:
- **here (pure):** sample-point extraction, grid-axis construction, the
  backend dispatch (IDW / SciPy linear-cubic-nearest-rbf / directional
  trend), leave-one-out R², the JSON-serializable grid dict, synthetic
  sample points, anisotropy params, directional-weight extraction.
- **Workbench adapter (stays):** ``apply_interpolation_to_task`` and
  ``batch_prepare_factor_maps`` mutate ``FactorMapTask`` / ``ProjectDocument``;
  ``constraints.py`` (ConstraintLayers/ConstraintLine adapters) is entirely
  model-coupled and stays.
"""

from __future__ import annotations

from geoviz_plots.factor.directional import (
    DEFAULT_SEMI_MAJOR,
    DEFAULT_SEMI_MINOR,
    extract_xy_z_weights,
    resolve_anisotropy_params,
)
from geoviz_plots.factor.interpolation import (
    DEFAULT_FACTOR_TYPES,
    DEFAULT_GRID_N,
    GENERATOR_VERSION,
    MAX_LOO_SAMPLES,
    extract_xy_values,
    interpolate_factor_grid,
    method_to_backend,
    mvp_note_for,
    snapshot_hash,
    synthetic_sample_points,
)

__all__ = [
    "GENERATOR_VERSION",
    "DEFAULT_FACTOR_TYPES",
    "DEFAULT_GRID_N",
    "MAX_LOO_SAMPLES",
    "DEFAULT_SEMI_MAJOR",
    "DEFAULT_SEMI_MINOR",
    "extract_xy_values",
    "extract_xy_z_weights",
    "interpolate_factor_grid",
    "method_to_backend",
    "mvp_note_for",
    "resolve_anisotropy_params",
    "snapshot_hash",
    "synthetic_sample_points",
]
