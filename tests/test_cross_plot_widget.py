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


def test_lasso_selection_rotated_polygon_selects_correct_points(cross_plot_widget, qtbot):
    """#506: a non-axis-aligned lasso must select the points it visually
    encloses (descending edges mis-evaluated before the sign fix)."""
    x = np.array([2.0, 3.6, 3.5, 2.9])
    y = np.array([2.0, 1.5, 0.4, 2.0])
    cross_plot_widget.set_scatter_data(x, y, x_label="GR", y_label="NPHI")

    emitted = []
    cross_plot_widget.points_selected.connect(
        lambda indices, bounds: emitted.append(list(indices))
    )
    diamond = [QPointF(2.0, 0.0), QPointF(4.0, 2.0), QPointF(2.0, 4.0), QPointF(0.0, 2.0)]
    cross_plot_widget.apply_lasso_polygon(diamond)

    assert emitted == [[0, 3]]  # (2,2) and (2.9,2) inside; slanted-edge points outside
    assert len(cross_plot_widget.clusters) == 1


def test_lasso_selection_collinear_points_still_emits(cross_plot_widget, qtbot):
    """#557: lassoing points on a line (the normal crossplot trend case)
    must still create the cluster and emit points_selected — no QhullError
    out of the event handler."""
    x = np.array([1.0, 2.0, 3.0, 4.0])
    y = np.array([1.0, 2.0, 3.0, 4.0])
    cross_plot_widget.set_scatter_data(x, y, x_label="GR", y_label="NPHI")

    emitted = []
    cross_plot_widget.points_selected.connect(
        lambda indices, bounds: emitted.append(list(indices))
    )
    lasso = [QPointF(0.0, 0.0), QPointF(5.0, 5.0), QPointF(5.0, 4.0), QPointF(0.0, -1.0)]
    cross_plot_widget.apply_lasso_polygon(lasso)

    assert len(emitted) == 1
    assert len(emitted[0]) == 4
    assert len(cross_plot_widget.clusters) == 1


def test_cross_plot_widget_nan_samples_do_not_poison_bounds(cross_plot_widget):
    """A single NaN sample must not blank the whole plot (#553)."""
    x = np.array([1.0, 2.0, np.nan, 4.0])
    y = np.array([10.0, 20.0, 30.0, np.nan])

    cross_plot_widget.set_scatter_data(x, y)

    assert np.isfinite(cross_plot_widget.view_xmin)
    assert np.isfinite(cross_plot_widget.view_xmax)
    assert np.isfinite(cross_plot_widget.view_ymin)
    assert np.isfinite(cross_plot_widget.view_ymax)
    assert cross_plot_widget.view_xmin == 1.0
    # (4.0, NaN) and (NaN, 30.0) are excluded by the joint finite mask.
    assert cross_plot_widget.view_xmax == 2.0
    assert cross_plot_widget.view_ymin == 10.0
    assert cross_plot_widget.view_ymax == 20.0


def test_cross_plot_widget_all_nan_keeps_default_bounds(cross_plot_widget):
    x = np.array([np.nan, np.nan])
    y = np.array([np.nan, np.nan])
    cross_plot_widget.set_scatter_data(x, y)
    assert np.isfinite(cross_plot_widget.view_xmin)
    assert cross_plot_widget.view_xmin == 0.0
    assert cross_plot_widget.view_xmax == 1.0
