from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QApplication

from geoviz_well_log.renderer.pattern_engine import PatternEngine


def _ensure_app():
    QApplication.instance() or QApplication([])


def test_get_color_fuzzy_returns_color_for_known_facies():
    _ensure_app()
    engine = PatternEngine()
    color = engine.get_color_fuzzy("砂岩")
    assert color is not None
    assert color.isValid()


def test_get_color_fuzzy_substring_match_longest_first():
    """'浅灰色粉砂岩' must match '粉砂岩' before '砂岩' (longer key wins)."""
    from geoviz_well_log.pattern_map import FACIES_COLORS

    _ensure_app()
    engine = PatternEngine()
    assert PatternEngine._SORTED_COLOR_KEYS == sorted(
        FACIES_COLORS.keys(), key=len, reverse=True
    )
    c_specific = engine.get_color_fuzzy("浅灰色粉砂岩")
    c_generic = engine.get_color_fuzzy("浅灰色砂岩")
    c_silt = engine.get_color_fuzzy("粉砂岩")
    c_sand = engine.get_color_fuzzy("砂岩")
    assert c_specific is not None and c_generic is not None
    assert c_specific == c_silt
    assert c_generic == c_sand
    assert c_specific != c_generic


def test_get_color_fuzzy_unknown_returns_none():
    _ensure_app()
    engine = PatternEngine()
    assert engine.get_color_fuzzy("绝不存在的相") is None


def test_get_composite_brush_known_pattern_returns_brush():
    _ensure_app()
    engine = PatternEngine()
    brush = engine.get_composite_brush("砂岩", QColor("#ffeecc"))
    assert isinstance(brush, QBrush)


def test_get_composite_brush_unknown_returns_none():
    _ensure_app()
    engine = PatternEngine()
    brush = engine.get_composite_brush("无此相", QColor("#ffffff"))
    assert brush is None


def test_get_composite_brush_caches_by_name_and_color():
    _ensure_app()
    engine = PatternEngine()
    a = engine.get_composite_brush("砂岩", QColor("#ffeecc"))
    b = engine.get_composite_brush("砂岩", QColor("#ffeecc"))
    assert a is b
