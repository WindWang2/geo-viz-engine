import pytest
from PySide6.QtGui import QBrush, QColor, QTransform
from geoviz_paleo_map.style import FaciesStyleResolver, FaciesStyle
from geoviz_well_log.renderer.pattern_engine import PatternEngine

def test_facies_style_resolver_adaptive_brush():
    pe = PatternEngine()
    resolver = FaciesStyleResolver(pe)
    
    facies = "砂岩" 
    style = resolver.resolve(facies)
    assert style.brush is not None
    
    # We want a method that returns a brush with appropriate transform for a given scale
    b1 = resolver.get_adaptive_brush(facies, scale=1.0)
    b2 = resolver.get_adaptive_brush(facies, scale=4.0)
    
    # They should be different
    assert b1.transform() != b2.transform()
    
    # scale=4 -> grain_scale=2
    t2 = b2.transform()
    assert t2.m11() == 2.0
    assert t2.m22() == 2.0
