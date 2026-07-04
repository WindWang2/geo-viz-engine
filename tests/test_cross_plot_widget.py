"""Unit tests for CrossPlotWidget interactive scatter plot canvas."""
import pytest
import numpy as np
from PySide6.QtCore import QPointF
from geoviz_plots.chart.cross_plot_widget import CrossPlotWidget

@pytest.fixture
def cross_plot_widget(qtbot):
    widget = CrossPlotWidget()
    qtbot.addWidget(widget)
    widget.resize(600, 400)
    widget.show()
    return widget

def test_cross_plot_widget_scatter_data(cross_plot_widget):
    x = np.array([10.0, 20.0, 30.0, 40.0])
    y = np.array([5.0, 15.0, 25.0, 35.0])
    z = np.array([1.0, 2.0, 3.0, 4.0])

    cross_plot_widget.set_scatter_data(x, y, z, x_label="GR", y_label="NPHI", z_label="Depth")
    assert len(cross_plot_widget.x_data) == 4
    assert len(cross_plot_widget.y_data) == 4
    assert cross_plot_widget.x_label == "GR"

def test_lasso_selection(cross_plot_widget, qtbot):
    x = np.array([1.0, 5.0, 10.0, 20.0])
    y = np.array([1.0, 5.0, 10.0, 20.0])
    cross_plot_widget.set_scatter_data(x, y, x_label="GR", y_label="NPHI")

    selected_count = []
    cross_plot_widget.points_selected.connect(lambda indices, bounds: selected_count.append(len(indices)))

    # Set lasso polygon enclosing points (1,1) and (5,5)
    lasso_pts = [QPointF(0.0, 0.0), QPointF(6.0, 0.0), QPointF(6.0, 6.0), QPointF(0.0, 6.0)]
    cross_plot_widget.apply_lasso_polygon(lasso_pts)

    assert len(selected_count) == 1
    assert selected_count[0] == 2
    assert len(cross_plot_widget.clusters) == 1
