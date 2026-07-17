"""Pure, GUI-independent domain analytics."""

from geoviz_plots.analytics.well_qc import (
    compute_sand_ratio,
    median_absolute_deviation,
    modified_z_scores,
)

__all__ = [
    "compute_sand_ratio",
    "median_absolute_deviation",
    "modified_z_scores",
]
