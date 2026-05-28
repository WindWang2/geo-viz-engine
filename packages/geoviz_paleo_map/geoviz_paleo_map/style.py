"""FaciesStyleResolver — facies name → base color + composite brush.

Caches per facies name; multiple polygons of the same facies share one
FaciesStyle instance, and the underlying composite brush is cached inside
PatternEngine itself.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPen

from geoviz_well_log.renderer.pattern_engine import PatternEngine

from geoviz_paleo_map.models import FaciesStyle


DEFAULT_BASE_COLOR = QColor("#d9d4c8")


class FaciesStyleResolver:
    def __init__(self, pattern_engine: PatternEngine):
        self._engine = pattern_engine
        self._cache: dict[str, FaciesStyle] = {}

    def resolve(self, facies_name: str) -> FaciesStyle:
        if facies_name in self._cache:
            return self._cache[facies_name]
        base = self._engine.get_color_fuzzy(facies_name) or QColor(DEFAULT_BASE_COLOR)
        brush = self._engine.get_composite_brush(facies_name, base)
        if brush is None:
            brush = QBrush(base)
        style = FaciesStyle(base_color=base, brush=brush)
        self._cache[facies_name] = style
        return style


def boundary_pen(kind: str | None) -> QPen:
    """Return the QPen for a polygon boundary type."""
    if kind == "inferred":
        pen = QPen(QColor("#555555"), 1.5)
        pen.setDashPattern([6.0, 3.0])
        return pen
    if kind == "fault":
        return QPen(QColor("#e53e3e"), 2.0)
    if kind == "confirmed":
        return QPen(QColor("#555555"), 1.5)
    return QPen(QColor("#555555"), 1.0)
