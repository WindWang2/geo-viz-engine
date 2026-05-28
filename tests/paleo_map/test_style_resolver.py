from PySide6.QtGui import QBrush, QColor

from geoviz_paleo_map.models import FaciesStyle
from geoviz_paleo_map.style import FaciesStyleResolver, boundary_pen
from geoviz_well_log.renderer.pattern_engine import PatternEngine


def test_resolves_known_facies_to_color_and_brush():
    engine = PatternEngine()
    r = FaciesStyleResolver(engine)
    style = r.resolve("砂岩")
    assert isinstance(style, FaciesStyle)
    assert style.base_color.isValid()
    assert isinstance(style.brush, QBrush)


def test_unknown_facies_falls_back_to_default_color():
    engine = PatternEngine()
    r = FaciesStyleResolver(engine)
    style = r.resolve("无此相")
    # Default color "#d9d4c8"
    assert style.base_color == QColor("#d9d4c8")


def test_resolve_caches_styles_per_facies_name():
    engine = PatternEngine()
    r = FaciesStyleResolver(engine)
    a = r.resolve("砂岩")
    b = r.resolve("砂岩")
    assert a is b  # same FaciesStyle instance returned


def test_boundary_pen_confirmed_solid_gray():
    pen = boundary_pen("confirmed")
    assert pen.color() == QColor("#555555")
    assert pen.widthF() == 1.5


def test_boundary_pen_fault_solid_red():
    pen = boundary_pen("fault")
    assert pen.color() == QColor("#e53e3e")


def test_boundary_pen_inferred_dashed():
    pen = boundary_pen("inferred")
    assert pen.dashPattern() == [6.0, 3.0]
