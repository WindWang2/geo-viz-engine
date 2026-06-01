import pytest
from PySide6.QtGui import QColor, QBrush
from geoviz_well_log.renderer.pattern_engine import PatternEngine
from geoviz_paleo_map.style import FaciesStyleResolver


def test_evaporite_pattern_engine_resolves(qtbot):
    """Verify that evaporite / evaporite salt matches the evaporite pattern SVG."""
    engine = PatternEngine()
    
    # Test fuzzy lookup and exact mapping for rock types
    pid_rock = engine._fuzzy_lookup("蒸发岩")
    assert pid_rock == "evaporite"
    
    # Test brush generation for rock types
    brush = engine.get_brush("蒸发岩")
    assert brush is not None
    assert isinstance(brush, QBrush)
    
    # Test composite brush generation
    base_color = QColor("#e8dcc8")
    comp_brush = engine.get_composite_brush("蒸发岩", base_color)
    assert comp_brush is not None
    assert isinstance(comp_brush, QBrush)


def test_evaporite_facies_style_resolver(qtbot):
    """Verify that FaciesStyleResolver correctly maps 蒸发盐 to evaporite and returns correct style."""
    engine = PatternEngine()
    resolver = FaciesStyleResolver(engine)
    
    style = resolver.resolve("蒸发盐")
    assert style is not None
    assert style.pattern_id == "evaporite"
    assert style.base_color.name() == "#e8dcc8"
    assert isinstance(style.brush, QBrush)


def test_evaporite_sub_facies_and_micro_facies_colors():
    """Verify that all newly integrated facies, sub-facies and micro-facies names have exact colors."""
    engine = PatternEngine()
    
    # Verify sub-facies colors
    sub_color_1 = engine.get_color("三角洲前缘")
    assert sub_color_1 is not None
    assert sub_color_1.name() == "#ebd2b0"
    
    sub_color_2 = engine.get_color("超咸水潟湖")
    assert sub_color_2 is not None
    assert sub_color_2.name() == "#a0c7c0"
    
    # Verify micro-facies colors
    micro_color_1 = engine.get_color("蒸发盐")
    assert micro_color_1 is not None
    assert micro_color_1.name() == "#e8dcc8"
    
    micro_color_2 = engine.get_color("湖底泥")
    assert micro_color_2 is not None
    assert micro_color_2.name() == "#73c3ef"
