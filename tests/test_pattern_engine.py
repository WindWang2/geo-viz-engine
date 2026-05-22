import pytest
from PySide6.QtGui import QBrush, QColor

from geoviz_well_log.renderer.pattern_engine import PatternEngine


def test_pattern_engine_resolves_known_lithology(qtbot):
    """砂岩 should resolve to 'sandstone' pattern."""
    engine = PatternEngine()
    brush = engine.get_brush("砂岩")
    assert brush is not None
    assert isinstance(brush, QBrush)


def test_pattern_engine_unknown_returns_none():
    """Unknown lithology returns None brush."""
    engine = PatternEngine()
    brush = engine.get_brush("不存在的岩石")
    assert brush is None


def test_pattern_engine_fallback_color():
    """Fallback color for known FACIES_COLORS entry."""
    engine = PatternEngine()
    color = engine.get_color("砂岩")
    assert color is not None
    assert isinstance(color, QColor)
    assert color.name() == "#f0d9b5"


def test_pattern_engine_fallback_color_unknown():
    """Unknown name returns None color."""
    engine = PatternEngine()
    color = engine.get_color("不存在的岩石")
    assert color is None


def test_pattern_engine_caches_brushes(qtbot):
    """Same lithology returns same brush object (cached)."""
    engine = PatternEngine()
    b1 = engine.get_brush("砂岩")
    b2 = engine.get_brush("砂岩")
    assert b1 is b2
