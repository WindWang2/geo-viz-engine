"""Lithology crossplot statistics (GR vs acoustic impedance).

Promoted from ``paleo_workbench/viz/geomodel/well_seismic.py::LithologyCrossplotEngine``.
Headless numpy — the Qt crossplot dialog lives in :mod:`geoviz_seismic.dialogs.crossplot`.
"""

from __future__ import annotations

import numpy as np

__all__ = ["analyze_lithology_crossplot"]

UNKNOWN_LITHOLOGY = "Unknown"


def analyze_lithology_crossplot(
    gr: np.ndarray,
    ai: np.ndarray,
    lithology: list[str],
) -> dict:
    """Group GR / acoustic-impedance samples by lithology and summarize each cluster.

    Args:
        gr: Gamma-ray values, one per sample.
        ai: Acoustic impedance values, aligned with ``gr``.
        lithology: Lithology label per sample. Shorter than ``gr`` is tolerated —
            missing labels fall back to ``"Unknown"``.

    Returns:
        ``{"points": [{"gr", "ai", "lithology"}, ...],
           "clusters": {label: {"count", "mean_gr", "mean_ai", "std_gr", "std_ai"}}}``
    """
    gr = np.asarray(gr, dtype=float)
    ai = np.asarray(ai, dtype=float)

    points = []
    grouped: dict[str, list[int]] = {}

    for i in range(len(gr)):
        label = lithology[i] if i < len(lithology) else UNKNOWN_LITHOLOGY
        points.append({"gr": float(gr[i]), "ai": float(ai[i]), "lithology": label})
        grouped.setdefault(label, []).append(i)

    clusters = {}
    for label, indices in grouped.items():
        gr_group = gr[indices]
        ai_group = ai[indices]
        clusters[label] = {
            "count": len(indices),
            "mean_gr": float(np.mean(gr_group)),
            "mean_ai": float(np.mean(ai_group)),
            "std_gr": float(np.std(gr_group)),
            "std_ai": float(np.std(ai_group)),
        }

    return {"points": points, "clusters": clusters}
