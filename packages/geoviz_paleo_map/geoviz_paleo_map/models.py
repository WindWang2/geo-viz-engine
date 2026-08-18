"""Data models for geoviz_paleo_map."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QBrush, QColor, QPicture


@dataclass(frozen=True)
class FaciesStyle:
    """Resolved styling for one facies value: base color + optional composite brush."""

    base_color: QColor
    brush: QBrush
    pattern_id: str | None = None


@dataclass(frozen=True)
class VectorPattern:
    """Vector pattern tile for crisp, scalable polygon fills.

    The QPicture records SVG vector draw commands at a 32×32 viewBox.
    The painter scales by tile_size/32 when tiling.
    """

    picture: QPicture
    base_color: QColor
    alpha: float
    tile_size: float
    # Stable pattern identity for cache keys. The picture object itself is
    # recreated on canvas rebuilds and the process-global QPixmapCache must
    # never key on id(picture): a fresh QPicture can reuse a freed id and
    # serve the old pattern's tile (#853).
    pattern_id: str | None = None
