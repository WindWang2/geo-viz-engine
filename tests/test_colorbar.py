"""Unit tests for ColorbarWidget continuous and discrete modes."""
import pytest
from PySide6.QtGui import QColor
from geoviz_plots.chart.colorbar import ColorbarWidget

@pytest.fixture
def colorbar_widget(qtbot):
    widget = ColorbarWidget()
    qtbot.addWidget(widget)
    widget.resize(60, 400)
    widget.show()
    return widget

def test_colorbar_continuous_mode(colorbar_widget):
    colorbar_widget.set_continuous_range(0.0, 100.0, colormap_name="viridis")
    assert colorbar_widget._mode == "continuous"
    assert colorbar_widget._vmin == 0.0
    assert colorbar_widget._vmax == 100.0

def test_colorbar_discrete_mode(colorbar_widget):
    swatches = [
        ("砂岩", QColor(255, 220, 95)),
        ("页岩", QColor(100, 110, 120)),
    ]
    colorbar_widget.set_discrete_swatches(swatches)
    assert colorbar_widget._mode == "discrete"
    assert len(colorbar_widget._swatches) == 2
