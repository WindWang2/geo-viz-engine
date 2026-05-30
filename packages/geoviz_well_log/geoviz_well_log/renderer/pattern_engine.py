from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QBrush, QColor, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import QSize, Qt

from ..pattern_map import PATTERN_MAP, FACIES_COLORS

# Sort keys by length descending so "粉砂岩" matches before "砂岩"
_SORTED_PATTERN_KEYS = sorted(PATTERN_MAP.keys(), key=len, reverse=True)


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

    def _fuzzy_lookup(self, lithology_name: str) -> str | None:
        """Find pattern_id by exact match, then by substring match.

        E.g. "浅灰色粉砂岩" contains "粉砂岩" -> returns "siltstone".
        Longer keys are tried first to avoid "砂岩" matching before "粉砂岩".
        """
        # Exact match
        pid = PATTERN_MAP.get(lithology_name)
        if pid is not None:
            return pid

        # Substring match: find the longest PATTERN_MAP key contained in the name
        for key in _SORTED_PATTERN_KEYS:
            if key in lithology_name:
                return PATTERN_MAP[key]

        return None

    def get_brush(self, lithology_name: str) -> QBrush | None:
        """Return a tiled QBrush for the given lithology name.

        Supports fuzzy matching: "浅灰色粉砂岩" matches "粉砂岩".
        Returns None if no pattern found.
        """
        if lithology_name in self._brush_cache:
            return self._brush_cache[lithology_name]

        pattern_id = self._fuzzy_lookup(lithology_name)
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

    _SORTED_COLOR_KEYS = sorted(FACIES_COLORS.keys(), key=len, reverse=True)

    def get_color_fuzzy(self, name: str) -> QColor | None:
        """Return a QColor by substring match against FACIES_COLORS.

        Longest keys are tried first so '粉砂岩' matches before '砂岩'.
        """
        hex_color = FACIES_COLORS.get(name)
        if hex_color is not None:
            return QColor(hex_color)
        for key in self._SORTED_COLOR_KEYS:
            if key in name:
                return QColor(FACIES_COLORS[key])
        return None

    def get_composite_brush(self, name: str, base_color: QColor,
                            alpha: float = 0.6) -> QBrush | None:
        """Return a tiled QBrush of base_color overlaid with the SVG pattern
        for `name` at the given alpha.

        Returns None if no pattern matches `name`. Cached per (name, color hex).
        """
        cache_key = f"composite::{name}::{base_color.name()}::{alpha:.2f}"
        if not hasattr(self, "_composite_cache"):
            self._composite_cache: dict[str, QBrush] = {}
        if cache_key in self._composite_cache:
            return self._composite_cache[cache_key]

        pattern_id = self._fuzzy_lookup(name)
        if pattern_id is None:
            return None

        filename = pattern_id.replace("-", "_")
        svg_path = self._ASSETS_DIR / f"{filename}.svg"
        if not svg_path.exists():
            return None

        renderer = QSvgRenderer(str(svg_path))
        if not renderer.isValid():
            return None

        size = QSize(self._tile_size, self._tile_size)
        pm = QPixmap(size)
        pm.fill(base_color)
        painter = QPainter(pm)
        painter.setOpacity(alpha)
        renderer.render(painter)
        painter.end()

        brush = QBrush(pm)
        self._composite_cache[cache_key] = brush
        return brush

    def get_facies_brush(self, pattern_id: str, base_color: QColor,
                         alpha: float = 0.3) -> QBrush | None:
        """Return a composite brush for a facies pattern tile.

        Looks up SVG files in the `facies/` subdirectory under assets/patterns.
        Renders base_color background with the black SVG pattern overlaid at alpha.
        Cached per (pattern_id, color hex, alpha).
        """
        cache_key = f"facies::{pattern_id}::{base_color.name()}::{alpha:.2f}"
        if not hasattr(self, "_facies_cache"):
            self._facies_cache: dict[str, QBrush] = {}
        if cache_key in self._facies_cache:
            return self._facies_cache[cache_key]

        filename = pattern_id.replace("-", "_")
        svg_path = self._ASSETS_DIR / "facies" / f"{filename}.svg"
        if not svg_path.exists():
            return None

        renderer = QSvgRenderer(str(svg_path))
        if not renderer.isValid():
            return None

        size = QSize(self._tile_size, self._tile_size)
        pm = QPixmap(size)
        pm.fill(base_color)
        painter = QPainter(pm)
        painter.setOpacity(alpha)
        renderer.render(painter)
        painter.end()

        brush = QBrush(pm)
        self._facies_cache[cache_key] = brush
        return brush
