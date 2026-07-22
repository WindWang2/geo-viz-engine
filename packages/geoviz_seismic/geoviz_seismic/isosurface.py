"""Isosurface extractor hook installed by the host application.

The engine cannot depend on the host's native extensions; the workbench
injects its C++ marching-tetrahedra implementation at startup via
``set_isosurface_extractor`` (same pattern as the well-log downsample hook).
"""
from __future__ import annotations

from typing import Callable

import numpy as np

ExtractorFn = Callable[[np.ndarray, float], "tuple[np.ndarray, np.ndarray]"]

_extractor: ExtractorFn | None = None


def set_isosurface_extractor(fn: ExtractorFn | None) -> None:
    """Install (or clear, with None) the isosurface extraction provider."""
    global _extractor
    _extractor = fn


def get_isosurface_extractor() -> ExtractorFn | None:
    """Return the installed isosurface extraction provider, or None."""
    return _extractor
