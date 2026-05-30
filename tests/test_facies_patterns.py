from PySide6.QtGui import QBrush, QColor
from geoviz_paleo_map.models import FaciesStyle
from geoviz_well_log.renderer.pattern_engine import PatternEngine


def test_facies_style_has_pattern_id():
    brush = QBrush(QColor("#ff0000"))
    style = FaciesStyle(base_color=QColor("#ff0000"), brush=brush, pattern_id="delta")
    assert style.pattern_id == "delta"


def test_facies_style_pattern_id_defaults_to_none():
    brush = QBrush(QColor("#ff0000"))
    style = FaciesStyle(base_color=QColor("#ff0000"), brush=brush)
    assert style.pattern_id is None


def test_get_facies_brush_returns_brush_for_known_pattern(qtbot):
    engine = PatternEngine()
    brush = engine.get_facies_brush("shoreface", QColor("#b5d4c1"))
    assert brush is not None


def test_get_facies_brush_returns_none_for_unknown_pattern():
    engine = PatternEngine()
    brush = engine.get_facies_brush("nonexistent_pattern", QColor("#ffffff"))
    assert brush is None


def test_get_facies_brush_caches_by_pattern_and_color():
    engine = PatternEngine()
    color = QColor("#b5d4c1")
    a = engine.get_facies_brush("shoreface", color)
    b = engine.get_facies_brush("shoreface", color)
    assert a is b
