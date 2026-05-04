import pytest
from PySide6.QtWebEngineWidgets import QWebEngineView
from src.renderers.well_log.chart_engine import ChartEngine, Bridge

def test_chart_engine_initializes(qtbot):
    engine = ChartEngine()
    qtbot.addWidget(engine)
    
    assert engine.view is not None
    assert isinstance(engine.view, QWebEngineView)
    assert engine.channel is not None
    assert engine.bridge is not None
    assert isinstance(engine.bridge, Bridge)

def test_chart_engine_render_data(qtbot):
    engine = ChartEngine()
    qtbot.addWidget(engine)
    
    # Verify that calling render_data does not raise exceptions
    try:
        engine.render_data("{}")
    except Exception as e:
        pytest.fail(f"render_data raised an exception: {e}")

def test_chart_engine_export_svg(qtbot):
    engine = ChartEngine()
    qtbot.addWidget(engine)
    
    # Verify that calling export_svg does not raise exceptions
    try:
        engine.export_svg()
    except Exception as e:
        pytest.fail(f"export_svg raised an exception: {e}")
