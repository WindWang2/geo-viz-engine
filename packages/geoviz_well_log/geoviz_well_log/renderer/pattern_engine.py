from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QBrush, QColor, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import QSize, Qt

from ..pattern_map import PATTERN_MAP, FACIES_COLORS


class PatternEngine:
    """Cache that converts SVG pattern files to tiled QBrush objects."""

    _ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "patterns"

    def __init__(self, tile_size: int = 20):
        self._tile_size = tile_size
        self._brush_cache: dict[str, QBrush] = {}

    def _load_svg(self, pattern_id: str) -> QBrush | None:
        """Load an SVG file and return a tiled QBrush."""
        filename = pattern_id.replace("-", "_")
        svg_path = self._ASSETS_DIR / f"{filename}.svg"
        if not svg_path.exists():
            return None

        renderer = QSvgRenderer(str(svg_path))
        if not renderer.isValid():
            return None

        size = QSize(self._tile_size, self._tile_size)
        pm = QPixmap(size)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        renderer.render(painter)
        painter.end()
        return QBrush(pm)

    def get_brush(self, lithology_name: str) -> QBrush | None:
        """Return a tiled QBrush for the given lithology name.

        Returns None if the name has no PATTERN_MAP entry or the SVG file is missing.
        """
        if lithology_name in self._brush_cache:
            return self._brush_cache[lithology_name]

        pattern_id = PATTERN_MAP.get(lithology_name)
        if pattern_id is None:
            return None

        brush = self._load_svg(pattern_id)
        if brush is not None:
            self._brush_cache[lithology_name] = brush
        return brush

    def get_color(self, name: str) -> QColor | None:
        """Return fallback color from FACIES_COLORS for a given name."""
        hex_color = FACIES_COLORS.get(name)
        if hex_color is None:
            return None
        return QColor(hex_color)
