"""Unit tests for 7-track WellTieCanvas widget."""
import pytest
import numpy as np
from geoviz_well_tie.canvas import WellTieCanvas

@pytest.fixture
def well_tie_canvas(qtbot):
    canvas = WellTieCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(900, 600)
    canvas.show()
    return canvas

def test_well_tie_canvas_initialization(well_tie_canvas):
    assert well_tie_canvas.width() == 900
    assert well_tie_canvas.height() == 600

def test_set_tie_data(well_tie_canvas):
    depths = np.linspace(1000, 2000, 100)
    twt = np.linspace(800, 1600, 100)
    sonic = np.linspace(300, 200, 100)
    density = np.linspace(2.0, 2.5, 100)
    seismic = np.random.randn(100)

    well_tie_canvas.set_tie_data(depths, twt, sonic, density, seismic)
    assert well_tie_canvas._depths is not None
    assert well_tie_canvas._synthetic is not None
    assert len(well_tie_canvas._synthetic) == 99
