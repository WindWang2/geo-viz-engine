"""Tests for geoviz_plots package (Chart axes, IDW interpolation, and custom plotting widgets)."""
import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QWheelEvent

from geoviz_plots.chart.axes import nice_number, calculate_ticks, format_tick

def test_nice_number_rounding():
    """Verify the nice_number function correctly rounds to friendly intervals (1, 2, 5, 10)."""
    assert nice_number(0.8, True) == 1.0
    assert nice_number(1.8, True) == 2.0
    assert nice_number(4.2, True) == 5.0
    assert nice_number(8.5, True) == 10.0
    assert nice_number(12.0, True) == 10.0

def test_nice_number_loose():
    """Verify nice_number in loose mode (ceil to next nice interval)."""
    assert nice_number(0.8, False) == 1.0
    assert nice_number(1.8, False) == 2.0
    assert nice_number(4.2, False) == 5.0
    assert nice_number(8.5, False) == 10.0
    assert nice_number(12.0, False) == 20.0

def test_calculate_ticks_basic():
    """Verify tick interval and tick generation for a basic range [0, 9.5]."""
    ticks, step = calculate_ticks(0.0, 9.5, 5)
    assert step == 2.0
    assert ticks == [0.0, 2.0, 4.0, 6.0, 8.0, 10.0]

def test_calculate_ticks_shifted():
    """Verify tick interval and ticks for a range shifted away from zero [102, 107]."""
    ticks, step = calculate_ticks(102.0, 107.0, 5)
    assert step == 1.0
    assert ticks == [102.0, 103.0, 104.0, 105.0, 106.0, 107.0]

def test_calculate_ticks_sub_unity():
    """Verify tick generation for very small float ranges."""
    ticks, step = calculate_ticks(0.003, 0.0075, 5)
    assert step == pytest.approx(0.001)
    assert len(ticks) >= 5
    for t in ticks:
        # Check all ticks are clean multiples of step
        assert (t / step) == pytest.approx(round(t / step))


def test_format_tick_unique_for_milli_range():
    """#554: labels must follow the tick step, not a hardcoded two decimals."""
    ticks, step = calculate_ticks(0.001, 0.004, 6)
    labels = [format_tick(t, step) for t in ticks]
    assert "0.00" not in labels
    assert len(set(labels)) == len(labels)
    assert format_tick(0.001, 0.001) == "0.001"
    assert format_tick(2.0, 1.0) == "2"

import numpy as np
from geoviz_plots.chart.series import LineSeries, ScatterSeries, lttb_downsample

def test_series_data_bounds():
    """Verify that LineSeries and ScatterSeries calculate their data bounds correctly, ignoring NaNs."""
    x = [1.0, 2.0, float('nan'), 4.0]
    y = [10.0, float('nan'), 30.0, 40.0]
    
    series = LineSeries(x, y, name="Test Line")
    xmin, xmax, ymin, ymax = series.get_bounds()
    
    assert xmin == 1.0
    assert xmax == 4.0
    assert ymin == 10.0
    assert ymax == 40.0
    
    # Test empty series
    empty_series = ScatterSeries()
    assert empty_series.get_bounds() == (0.0, 0.0, 0.0, 0.0)


def test_series_get_bounds_ignores_inf():
    """#683: Inf samples must not leak into autofit / tick calculation."""
    import math

    series = LineSeries([0.0, 1.0, 2.0], [1.0, float("inf"), 2.0], name="inf-y")
    xmin, xmax, ymin, ymax = series.get_bounds()
    assert (xmin, xmax, ymin, ymax) == (0.0, 2.0, 1.0, 2.0)
    assert all(math.isfinite(v) for v in (xmin, xmax, ymin, ymax))

    mixed = LineSeries(
        [0.0, float("-inf"), 2.0],
        [1.0, 5.0, float("nan")],
        name="inf-x",
    )
    xmin, xmax, ymin, ymax = mixed.get_bounds()
    assert (xmin, xmax, ymin, ymax) == (0.0, 0.0, 1.0, 1.0)


def test_plot_autofit_and_paint_survive_inf_samples(qtbot):
    """#683: autofit + paintEvent must stay finite when a series contains Inf."""
    import math

    from geoviz_plots.chart.plot_widget import PlotWidget

    widget = PlotWidget()
    qtbot.addWidget(widget)
    widget.add_series(LineSeries([0.0, 1.0, 2.0], [1.0, float("inf"), 2.0]))
    widget.autofit()
    assert all(math.isfinite(v) for v in widget.view_bounds())
    widget.resize(240, 180)
    widget.show()
    qtbot.waitExposed(widget)
    widget.repaint()

def test_lttb_downsampling_basic():
    """Verify that the LTTB algorithm downsamples a larger dataset to the target threshold."""
    # Generate 1000 points (a sine wave)
    x = np.linspace(0, 10, 1000)
    y = np.sin(x)
    
    # Target downsample to 100 points
    dx, dy = lttb_downsample(x, y, 100)
    
    assert len(dx) == 100
    assert len(dy) == 100
    assert dx[0] == 0.0
    assert dx[-1] == 10.0
    # The shape should be preserved, so bounds should be very close
    assert np.min(dy) == pytest.approx(-1.0, abs=0.05)
    assert np.max(dy) == pytest.approx(1.0, abs=0.05)

def test_lttb_small_dataset():
    """Verify that LTTB returns the original data if the dataset is smaller than the threshold."""
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([10.0, 20.0, 30.0])
    dx, dy = lttb_downsample(x, y, 10)
    assert np.array_equal(dx, x)
    assert np.array_equal(dy, y)

from geoviz_plots.chart.plot_widget import PlotWidget


def test_plot_widget_emits_distinct_hover_and_click_events(qtbot):
    widget = PlotWidget()
    qtbot.addWidget(widget)
    widget.resize(800, 600)
    widget.add_series(
        ScatterSeries([10.0, 20.0], [30.0, 40.0], name="Well locations")
    )
    widget.autofit()
    widget.show()

    hovered = []
    clicked = []
    legacy_selected = []
    hover_cleared = []
    widget.point_hovered.connect(lambda *point: hovered.append(point))
    widget.point_clicked.connect(lambda *point: clicked.append(point))
    widget.point_selected.connect(
        lambda *point: legacy_selected.append(point)
    )
    widget.point_hover_cleared.connect(lambda: hover_cleared.append(True))

    px, py = widget.data_to_pixel(10.0, 30.0)
    point = QPoint(round(px), round(py))
    qtbot.mouseMove(widget, point)

    assert hovered == [("Well locations", 0, 10.0, 30.0)]
    assert clicked == []
    assert legacy_selected == []

    qtbot.mouseClick(widget, Qt.LeftButton, pos=point)

    assert clicked == [("Well locations", 0, 10.0, 30.0)]

    qtbot.mouseMove(widget, QPoint(70, 30))

    assert hover_cleared == [True]
    assert widget.hovered_point is None


def test_plot_widget_clears_hover_when_view_changes_or_pointer_leaves(qtbot):
    widget = PlotWidget()
    qtbot.addWidget(widget)
    widget.resize(800, 600)
    widget.add_series(
        ScatterSeries([10.0, 20.0], [30.0, 40.0], name="Well locations")
    )
    widget.autofit()
    cleared = []
    widget.point_hover_cleared.connect(lambda: cleared.append(True))
    px, py = widget.data_to_pixel(10.0, 30.0)

    widget.check_nearest_point(QPointF(px, py))
    widget.focus_point(10.0, 30.0)

    assert widget.hovered_point is None
    assert cleared == [True]

    px, py = widget.data_to_pixel(10.0, 30.0)
    widget.check_nearest_point(QPointF(px, py))
    QCoreApplication.sendEvent(widget, QEvent(QEvent.Leave))

    assert widget.hovered_point is None
    assert cleared == [True, True]


def test_plot_widget_clear_discards_hover_and_prior_click_gesture(qtbot):
    widget = PlotWidget()
    qtbot.addWidget(widget)
    widget.resize(800, 600)
    widget.add_series(
        ScatterSeries([10.0, 20.0], [30.0, 40.0], name="Well locations")
    )
    widget.autofit()
    widget.show()
    hover_cleared = []
    resets = []
    widget.point_hover_cleared.connect(lambda: hover_cleared.append(True))
    widget.reset_requested.connect(lambda: resets.append(True))
    px, py = widget.data_to_pixel(10.0, 30.0)
    point = QPoint(round(px), round(py))
    qtbot.mouseClick(widget, Qt.LeftButton, pos=point)

    widget.clear()

    assert hover_cleared == [True]
    assert widget.hovered_point is None
    assert widget.hover_pos is None

    qtbot.mouseDClick(widget, Qt.LeftButton, pos=point)

    assert resets == [True]


def test_plot_widget_focus_is_equal_aspect_idempotent_and_resettable(qtbot):
    widget = PlotWidget()
    qtbot.addWidget(widget)
    widget.resize(800, 600)
    widget.add_series(
        ScatterSeries([0.0, 100.0], [0.0, 50.0], name="Well locations")
    )
    widget.set_equal_aspect(True)
    widget.autofit()

    full_view = (
        widget.view_xmin,
        widget.view_xmax,
        widget.view_ymin,
        widget.view_ymax,
    )
    left, right, top, bottom = widget.get_plot_rect(widget.width(), widget.height())
    x_units_per_pixel = (widget.view_xmax - widget.view_xmin) / (right - left)
    y_units_per_pixel = (widget.view_ymax - widget.view_ymin) / (bottom - top)
    assert x_units_per_pixel == pytest.approx(y_units_per_pixel)

    widget.focus_point(25.0, 20.0, zoom_factor=4.0)
    focused_view = (
        widget.view_xmin,
        widget.view_xmax,
        widget.view_ymin,
        widget.view_ymax,
    )
    assert widget.view_xmax - widget.view_xmin == pytest.approx(
        (full_view[1] - full_view[0]) / 4.0
    )
    assert widget.view_ymax - widget.view_ymin == pytest.approx(
        (full_view[3] - full_view[2]) / 4.0
    )

    widget.focus_point(25.0, 20.0, zoom_factor=4.0)
    assert (
        widget.view_xmin,
        widget.view_xmax,
        widget.view_ymin,
        widget.view_ymax,
    ) == pytest.approx(focused_view)

    widget.reset_view()
    assert (
        widget.view_xmin,
        widget.view_xmax,
        widget.view_ymin,
        widget.view_ymax,
    ) == pytest.approx(full_view)


def test_plot_widget_public_view_snapshot_and_axis_labels(qtbot):
    widget = PlotWidget()
    qtbot.addWidget(widget)
    widget.resize(800, 600)
    widget.set_axis_labels("X (m)", "Y (m)")

    widget.set_view_bounds((-5.0, 15.0, 20.0, 40.0))

    assert widget.view_bounds() == pytest.approx(
        (-5.0, 15.0, 20.0, 40.0)
    )
    assert widget.axis_labels() == ("X (m)", "Y (m)")


def test_plot_widget_selected_point_is_independent_from_hover(qtbot):
    widget = PlotWidget()
    qtbot.addWidget(widget)
    widget.add_series(
        ScatterSeries([10.0, 20.0], [30.0, 40.0], name="Well locations")
    )

    widget.set_selected_point("Well locations", 1, label="A2")

    assert widget.selected_point == ("Well locations", 1)
    assert widget.selected_label == "A2"
    assert widget.hovered_point is None

    widget.clear_selected_point()

    assert widget.selected_point is None
    assert widget.selected_label == ""


def test_plot_widget_blank_double_click_requests_full_view_reset(qtbot):
    widget = PlotWidget()
    qtbot.addWidget(widget)
    widget.resize(800, 600)
    widget.add_series(
        ScatterSeries([10.0, 20.0], [30.0, 40.0], name="Well locations")
    )
    widget.set_equal_aspect(True)
    widget.autofit()
    full_view = (
        widget.view_xmin,
        widget.view_xmax,
        widget.view_ymin,
        widget.view_ymax,
    )
    widget.focus_point(10.0, 30.0, zoom_factor=4.0)
    resets = []
    widget.reset_requested.connect(lambda: resets.append(True))

    qtbot.mouseDClick(widget, Qt.LeftButton, pos=QPoint(70, 30))

    assert resets == [True]
    assert (
        widget.view_xmin,
        widget.view_xmax,
        widget.view_ymin,
        widget.view_ymax,
    ) == pytest.approx(full_view)


def test_plot_widget_drag_does_not_emit_point_click(qtbot):
    widget = PlotWidget()
    qtbot.addWidget(widget)
    widget.resize(800, 600)
    widget.add_series(
        ScatterSeries([10.0, 20.0], [30.0, 40.0], name="Well locations")
    )
    widget.autofit()
    clicked = []
    widget.point_clicked.connect(lambda *point: clicked.append(point))
    px, py = widget.data_to_pixel(10.0, 30.0)
    start = QPointF(px, py)
    end = QPointF(px + 20.0, py + 20.0)

    for event in (
        QMouseEvent(
            QEvent.MouseButtonPress,
            start,
            start,
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        ),
        QMouseEvent(
            QEvent.MouseMove,
            end,
            end,
            Qt.NoButton,
            Qt.LeftButton,
            Qt.NoModifier,
        ),
        QMouseEvent(
            QEvent.MouseButtonRelease,
            end,
            end,
            Qt.LeftButton,
            Qt.NoButton,
            Qt.NoModifier,
        ),
    ):
        QCoreApplication.sendEvent(widget, event)

    assert clicked == []


def test_plot_widget_equal_aspect_tracks_widget_resize(qtbot):
    widget = PlotWidget()
    qtbot.addWidget(widget)
    widget.resize(800, 600)
    widget.add_series(
        ScatterSeries([0.0, 100.0], [0.0, 50.0], name="Well locations")
    )
    widget.set_equal_aspect(True)
    widget.autofit()
    widget.show()

    widget.resize(1200, 400)
    qtbot.wait(1)

    left, right, top, bottom = widget.get_plot_rect(widget.width(), widget.height())
    x_units_per_pixel = (widget.view_xmax - widget.view_xmin) / (right - left)
    y_units_per_pixel = (widget.view_ymax - widget.view_ymin) / (bottom - top)
    assert x_units_per_pixel == pytest.approx(y_units_per_pixel)


def test_plot_widget_equal_aspect_survives_drag_and_wheel(qtbot):
    widget = PlotWidget()
    qtbot.addWidget(widget)
    widget.resize(800, 600)
    widget.add_series(
        ScatterSeries([0.0, 100.0], [0.0, 50.0], name="Well locations")
    )
    widget.set_equal_aspect(True)
    widget.autofit()
    widget.show()
    start = QPointF(300.0, 250.0)
    end = QPointF(340.0, 275.0)

    for event in (
        QMouseEvent(
            QEvent.MouseButtonPress,
            start,
            start,
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        ),
        QMouseEvent(
            QEvent.MouseMove,
            end,
            end,
            Qt.NoButton,
            Qt.LeftButton,
            Qt.NoModifier,
        ),
        QMouseEvent(
            QEvent.MouseButtonRelease,
            end,
            end,
            Qt.LeftButton,
            Qt.NoButton,
            Qt.NoModifier,
        ),
    ):
        QCoreApplication.sendEvent(widget, event)

    QCoreApplication.sendEvent(
        widget,
        QWheelEvent(
            end,
            end,
            QPoint(),
            QPoint(0, 120),
            Qt.NoButton,
            Qt.NoModifier,
            Qt.ScrollUpdate,
            False,
        ),
    )

    left, right, top, bottom = widget.get_plot_rect(widget.width(), widget.height())
    x_units_per_pixel = (widget.view_xmax - widget.view_xmin) / (right - left)
    y_units_per_pixel = (widget.view_ymax - widget.view_ymin) / (bottom - top)
    assert x_units_per_pixel == pytest.approx(y_units_per_pixel)


def test_plot_widget_basic(qtbot):
    """Verify that PlotWidget can add series, calculate view bounds, map coords, and zoom/pan."""
    widget = PlotWidget()
    qtbot.addWidget(widget)
    
    series = LineSeries([0.0, 1.0, 2.0], [10.0, 20.0, 30.0], name="Line1")
    widget.add_series(series)
    
    # Auto-fit should align bounds (with 5% margin padding)
    widget.autofit()
    assert widget.view_xmin == pytest.approx(-0.1)
    assert widget.view_xmax == pytest.approx(2.1)
    assert widget.view_ymin == pytest.approx(9.0)
    assert widget.view_ymax == pytest.approx(31.0)
    
    # Test coordinate mapping after widget is sized
    widget.resize(800, 600)
    px, py = widget.data_to_pixel(1.0, 20.0)
    assert 0 < px < 800
    assert 0 < py < 600
    
    # Map back
    dx, dy = widget.pixel_to_data(px, py)
    assert dx == pytest.approx(1.0)
    assert dy == pytest.approx(20.0)

def test_plot_widget_zoom_pan(qtbot):
    """Verify that zoom and pan methods correctly adjust viewport limits."""
    widget = PlotWidget()
    qtbot.addWidget(widget)
    widget.resize(800, 600)
    
    widget.view_xmin, widget.view_xmax = 0.0, 10.0
    widget.view_ymin, widget.view_ymax = 0.0, 10.0
    
    # Pan by delta in pixels
    widget.pan(100, 50)  # shift by 100 pixels horizontally, 50 pixels vertically
    assert widget.view_xmin != 0.0 or widget.view_ymin != 0.0
    
    # Zoom around a center
    widget.view_xmin, widget.view_xmax = 0.0, 10.0
    widget.view_ymin, widget.view_ymax = 0.0, 10.0
    widget.zoom(1.5, 5.0, 5.0)
    # Range should shrink when zoom factor > 1.0 (zoom in)
    assert (widget.view_xmax - widget.view_xmin) < 10.0


def test_plot_widget_tick_labels_unique_under_zoom(qtbot, monkeypatch):
    """#554: render_plot must format ticks from the computed step."""
    import geoviz_plots.chart.plot_widget as pw

    formatter = getattr(pw, "format_tick", None)
    assert formatter is not None, "plot_widget must format ticks via format_tick"
    calls = []

    def spy(value, step):
        out = formatter(value, step)
        calls.append(out)
        return out

    monkeypatch.setattr(pw, "format_tick", spy)
    widget = PlotWidget()
    qtbot.addWidget(widget)
    widget.resize(800, 400)
    widget.set_view_bounds((0.001, 0.004, 0.001, 0.004))
    widget.grab()
    assert calls
    assert "0.00" not in calls
    assert {"0.001", "0.002", "0.003", "0.004"}.issubset(set(calls))


def test_rebuild_kdtree_large_series_is_fast(qtbot):
    """#556: add_series must build the KD-tree without a per-point Python loop."""
    import inspect
    import time

    src = inspect.getsource(PlotWidget._rebuild_kdtree)
    assert "points.append" not in src
    assert "np.column_stack" in src

    widget = PlotWidget()
    qtbot.addWidget(widget)
    widget.resize(400, 300)
    rng = np.random.default_rng(0)
    n = 100_000
    series = ScatterSeries(rng.random(n), rng.random(n), name="pts")
    t0 = time.perf_counter()
    widget.add_series(series)
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.05, f"add_series/KD-tree rebuild took {elapsed:.3f}s"
    assert widget._kdtree is not None
    assert len(widget._tree_metadata) == n
    widget.autofit()
    px, py = widget.data_to_pixel(float(series.x[0]), float(series.y[0]))
    hit = widget.check_nearest_point(QPointF(px, py))
    assert hit is not None
    assert hit[0] == "pts"


def test_check_nearest_point_ranks_by_pixels_not_data_space(qtbot):
    """#694: a visually-near point must win even when data-space k=10 misses it."""
    widget = PlotWidget()
    qtbot.addWidget(widget)
    widget.resize(800, 600)
    target_x, target_y = 50.0, 0.9
    decoy_x = 52.0
    xs = [target_x] + [decoy_x + i * 0.01 for i in range(15)]
    ys = [target_y] + [0.0] * 15
    widget.add_series(ScatterSeries(xs, ys, name="pts"))
    widget.set_view_bounds((0.0, 200.0, 0.0, 1.0))
    mx, my = widget.data_to_pixel(decoy_x, target_y)
    hit = widget.check_nearest_point(QPointF(mx, my))
    assert hit is not None
    assert hit[2] == target_x
    assert hit[3] == target_y


def test_render_plot_clips_series_to_plot_rect(qtbot):
    """#686: off-view polylines must not paint into the axis margin."""
    from PySide6.QtGui import QColor, QImage, QPainter

    widget = PlotWidget()
    qtbot.addWidget(widget)
    widget.resize(400, 300)
    widget.bg_color = QColor(0, 0, 0)
    widget.plot_bg_color = QColor(0, 0, 0)
    widget.grid_color = QColor(0, 0, 0)
    widget.axis_color = QColor(0, 0, 0)
    widget.text_color = QColor(0, 0, 0)
    widget.crosshair_color = QColor(0, 0, 0)
    widget.highlight_color = QColor(0, 0, 0)
    widget.add_series(
        LineSeries(
            [-10.0, 0.5, 10.0],
            [-10.0, 0.5, 10.0],
            name="wide",
            color=QColor(255, 0, 0),
            width=3.0,
        )
    )
    widget.set_view_bounds((0.0, 1.0, 0.0, 1.0))

    image = QImage(widget.size(), QImage.Format.Format_RGB32)
    image.fill(0)
    painter = QPainter(image)
    widget.render_plot(painter, widget.width(), widget.height())
    painter.end()

    left, right, top, bottom = widget.get_plot_rect(widget.width(), widget.height())
    red_in = 0
    red_out = 0
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if color.red() < 200 or color.green() > 40 or color.blue() > 40:
                continue
            if left - 2 <= x <= right + 2 and top - 2 <= y <= bottom + 2:
                red_in += 1
            else:
                red_out += 1
    assert red_in > 0
    assert red_out == 0


def test_cross_plot_paint_large_scatter_is_fast(qtbot):
    """#552: painting 200k points must not walk drawEllipse per sample."""
    import inspect
    import time

    from geoviz_plots.chart.cross_plot_widget import CrossPlotWidget

    paint_src = inspect.getsource(CrossPlotWidget.paintEvent)
    assert "for i in range(len(px))" not in paint_src
    assert "_blit_scatter_points" in inspect.getsource(CrossPlotWidget)

    widget = CrossPlotWidget()
    qtbot.addWidget(widget)
    widget.resize(600, 400)
    rng = np.random.default_rng(0)
    widget.set_scatter_data(rng.random(200_000), rng.random(200_000))
    widget.show()
    widget.repaint()
    t0 = time.perf_counter()
    widget.repaint()
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.1, f"CrossPlotWidget.paintEvent took {elapsed:.3f}s"


def test_surface_widget_tick_labels_unique_under_zoom(qtbot, monkeypatch):
    """#554: SurfaceWidget axis labels must also follow the tick step."""
    import geoviz_plots.surface.surface_widget as sw

    formatter = getattr(sw, "format_tick", None)
    assert formatter is not None, "surface_widget must format ticks via format_tick"
    calls = []

    def spy(value, step):
        out = formatter(value, step)
        calls.append(out)
        return out

    monkeypatch.setattr(sw, "format_tick", spy)
    widget = sw.SurfaceWidget()
    qtbot.addWidget(widget)
    widget.resize(800, 400)
    widget.set_grid_data(
        np.array([0.001, 0.004]),
        np.array([0.001, 0.004]),
        np.array([[0.0, 1.0], [1.0, 2.0]]),
        levels=[0.5, 1.5],
    )
    widget.view_xmin, widget.view_xmax = 0.001, 0.004
    widget.view_ymin, widget.view_ymax = 0.001, 0.004
    widget.grab()
    assert calls
    assert "0.00" not in calls
    assert {"0.001", "0.002", "0.003", "0.004"}.issubset(set(calls))


from geoviz_plots.interpolation.idw import interpolate_idw
from geoviz_plots.interpolation.scipy_grid import interpolate_scipy

def test_idw_interpolation():
    """Verify that IDW spatial interpolation produces the correct shape and interpolates correctly."""
    # Scattered data (a simple gradient)
    x = np.array([0.0, 1.0, 0.0, 1.0])
    y = np.array([0.0, 0.0, 1.0, 1.0])
    z = np.array([0.0, 10.0, 10.0, 20.0])  # Average center should be 10.0
    
    grid_x = np.linspace(0.0, 1.0, 5)
    grid_y = np.linspace(0.0, 1.0, 5)
    
    grid_z = interpolate_idw(x, y, z, grid_x, grid_y)
    
    assert grid_z.shape == (5, 5)
    # Center point (idx 2, 2) should be approx 10.0
    assert grid_z[2, 2] == pytest.approx(10.0)

def test_scipy_interpolation_masking():
    """Verify that SciPy interpolation works and correctly masks points outside the convex hull."""
    x = np.array([0.0, 1.0, 0.0, 1.0])
    y = np.array([0.0, 0.0, 1.0, 1.0])
    z = np.array([0.0, 10.0, 10.0, 20.0])
    
    # Grid that extends beyond [0, 1]
    grid_x = np.linspace(-0.5, 1.5, 5)
    grid_y = np.linspace(-0.5, 1.5, 5)
    
    # Test linear method with convex hull masking
    grid_z = interpolate_scipy(x, y, z, grid_x, grid_y, method="linear", mask_convex_hull=True)
    
    assert grid_z.shape == (5, 5)
    # Corner points like (0, 0) in grid corresponds to x=-0.5, y=-0.5, which is outside the hull
    assert np.isnan(grid_z[0, 0])
    # Center point is inside the hull
    assert not np.isnan(grid_z[2, 2])
    assert grid_z[2, 2] == pytest.approx(10.0)


from geoviz_plots.interpolation.scipy_grid import InterpolationWorker

def test_async_interpolation(qtbot):
    """Verify that InterpolationWorker runs asynchronously in QThread and emits result_ready."""
    x = np.array([0.0, 1.0, 0.0, 1.0])
    y = np.array([0.0, 0.0, 1.0, 1.0])
    z = np.array([0.0, 10.0, 10.0, 20.0])
    grid_x = np.linspace(0, 1, 5)
    grid_y = np.linspace(0, 1, 5)
    
    worker = InterpolationWorker(x, y, z, grid_x, grid_y, method="linear")
    
    # Track signal emission
    with qtbot.waitSignal(worker.result_ready, timeout=2000) as blocker:
        worker.start()
        
    grid_z = blocker.args[0]
    assert grid_z.shape == (5, 5)
    assert grid_z[2, 2] == pytest.approx(10.0)


def test_interpolation_worker_finished_is_qthread_lifecycle(qtbot):
    """#689: InterpolationWorker.finished must remain QThread.finished."""
    from PySide6.QtCore import QThread

    from geoviz_plots.interpolation.scipy_grid import InterpolationWorker

    assert InterpolationWorker.finished is QThread.finished
    assert hasattr(InterpolationWorker, "result_ready")

    x = np.array([0.0, 1.0, 0.0, 1.0])
    y = np.array([0.0, 0.0, 1.0, 1.0])
    z = np.array([0.0, 10.0, 10.0, 20.0])
    worker = InterpolationWorker(x, y, z, np.linspace(0, 1, 4), np.linspace(0, 1, 4))
    seen: dict[str, bool] = {}
    worker.finished.connect(lambda: seen.__setitem__("finished", worker.isFinished()))
    with qtbot.waitSignal(worker.finished, timeout=2000):
        worker.start()
    worker.wait(1000)
    assert seen.get("finished") is True


def test_interpolate_scipy_collinear_fallback_is_detectable(caplog):
    """#690: linear/cubic Qhull failure must flag nearest fallback."""
    import logging

    x = np.array([0.0, 1.0, 2.0])
    y = np.array([0.0, 0.0, 0.0])
    z = np.array([1.0, 2.0, 3.0])
    grid_x = np.linspace(0.0, 2.0, 5)
    grid_y = np.linspace(-1.0, 1.0, 5)
    status: dict = {}
    with caplog.at_level(logging.WARNING, logger="geoviz_plots.interpolation.scipy_grid"):
        grid_z = interpolate_scipy(
            x, y, z, grid_x, grid_y, method="linear", status=status,
        )
    assert status.get("fallback") == "nearest"
    assert status.get("requested_method") == "linear"
    assert np.isfinite(grid_z).any()
    assert "nearest" in caplog.text.lower()


def test_interpolate_scipy_unknown_method_does_not_fallback():
    """#690: unknown method names must raise, not silently become nearest."""
    x = np.array([0.0, 1.0, 0.0])
    y = np.array([0.0, 0.0, 1.0])
    z = np.array([1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match="Unknown interpolation method"):
        interpolate_scipy(x, y, z, [0.0, 1.0], [0.0, 1.0], method="not-a-method")


from geoviz_plots.surface.marching_squares import extract_contour_lines, extract_filled_contours
from geoviz_plots.surface.marching_squares import BandedFill

def test_contour_extraction():
    """Verify that contour line and filled polygon extraction works correctly, including handling NaNs."""
    # Create grid data with a single central peak
    grid_x = np.linspace(0.0, 2.0, 3)
    grid_y = np.linspace(0.0, 2.0, 3)
    grid_z = np.array([
        [0.0, 0.0, 0.0],
        [0.0, 1.0, float('nan')],  # Contains a NaN
        [0.0, 0.0, 0.0]
    ])

    # 1. Test Line Extraction
    lines_dict = extract_contour_lines(grid_x, grid_y, grid_z, levels=[0.5])
    assert 0.5 in lines_dict
    assert isinstance(lines_dict[0.5], list)

    # 2. Test Filled Contour Extraction (Phase-2 T3: returns list[BandedFill])
    bands = extract_filled_contours(grid_x, grid_y, grid_z, levels=[0.2, 0.8])
    assert len(bands) == 1
    band = bands[0]
    assert isinstance(band, BandedFill)
    assert band.level_min == 0.2
    assert band.level_max == 0.8
    assert isinstance(band.polygons, list)
    assert isinstance(band.offsets, list)
    # color is resolved against the default "viridis" palette at the band midpoint
    assert band.color is not None
    # label is "min-max"
    assert band.label == "0.2-0.8"


def test_contour_extraction_honours_cancellation_before_work():
    class CancelledToken:
        def raise_if_cancelled(self):
            raise RuntimeError("cancelled checkpoint")

    grid_x = np.linspace(0.0, 1.0, 4)
    grid_y = np.linspace(0.0, 1.0, 4)
    grid_z = np.add.outer(grid_y, grid_x)

    with pytest.raises(RuntimeError, match="cancelled checkpoint"):
        extract_contour_lines(
            grid_x,
            grid_y,
            grid_z,
            levels=[0.5],
            cancellation_token=CancelledToken(),
        )

    # Phase-2 T3: filled-contour extraction honours the same cancellation token.
    with pytest.raises(RuntimeError, match="cancelled checkpoint"):
        extract_filled_contours(
            grid_x,
            grid_y,
            grid_z,
            levels=[0.3, 0.7],
            cancellation_token=CancelledToken(),
        )


from geoviz_plots.surface.surface_widget import SurfaceWidget

def test_surface_widget_basic(qtbot):
    """Verify that SurfaceWidget can bind grid data, compute viewport bounds, map coords, and export."""
    widget = SurfaceWidget()
    qtbot.addWidget(widget)
    
    grid_x = np.linspace(0.0, 10.0, 5)
    grid_y = np.linspace(0.0, 10.0, 5)
    grid_z = np.zeros((5, 5))
    grid_z[2, 2] = 5.0
    
    widget.set_grid_data(grid_x, grid_y, grid_z, levels=[0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    
    # Auto-fit should align bounds
    widget.autofit()
    assert widget.view_xmin == 0.0
    assert widget.view_xmax == 10.0
    assert widget.view_ymin == 0.0
    assert widget.view_ymax == 10.0
    
    # Test coordinate mapping
    widget.resize(800, 600)
    px, py = widget.data_to_pixel(5.0, 5.0)
    assert 0 < px < 800
    assert 0 < py < 600
    
    # Map back
    dx, dy = widget.pixel_to_data(px, py)
    assert dx == pytest.approx(5.0)
    assert dy == pytest.approx(5.0)


def test_generate_fence_mesh_two_wells():
    """Verify the cross-well fence mesh builds a per-segment quad strip between two wells."""
    import numpy as np

    from geoviz_plots.fence import generate_fence_mesh

    wells = [
        {"name": "A", "x": 0.0, "y": 0.0, "depth": 100.0},
        {"name": "B", "x": 200.0, "y": 50.0, "depth": 150.0},
    ]
    verts, faces, colors = generate_fence_mesh(wells, nz_samples=10)

    # Two vertical lines × 10 samples per well = 20 vertices.
    assert verts.shape == (20, 3)
    assert verts.dtype == np.float32
    # (nz_samples - 1) quads × 2 triangles = 18 faces for one segment.
    assert faces.shape == (18, 3)
    assert faces.dtype == np.int32
    # One RGBA color per face.
    assert colors.shape == (18, 4)
    assert colors.dtype == np.float32
    # Depth axis should be non-positive (z from 0 → -depth).
    assert verts[:, 2].max() == pytest.approx(0.0)
    assert verts[:, 2].min() < 0.0


def test_generate_fence_mesh_single_well_returns_empty():
    """A single well cannot form a fence segment — expect empty arrays, not a raise."""
    import numpy as np

    from geoviz_plots.fence import generate_fence_mesh

    verts, faces, colors = generate_fence_mesh(
        [{"name": "A", "x": 0.0, "y": 0.0, "depth": 100.0}],
    )
    assert verts.shape == (0, 3)
    assert faces.shape == (0, 3)
    assert colors.shape == (0, 4)


def test_generate_fence_mesh_three_wells_two_segments():
    """Three wells produce two independent segments; offsets must not collide."""
    import numpy as np

    from geoviz_plots.fence import generate_fence_mesh

    wells = [
        {"name": "A", "x": 0.0, "y": 0.0, "depth": 100.0},
        {"name": "B", "x": 100.0, "y": 0.0, "depth": 100.0},
        {"name": "C", "x": 200.0, "y": 0.0, "depth": 100.0},
    ]
    verts, faces, _ = generate_fence_mesh(wells, nz_samples=5)
    # 3 wells → 2 segments × (2 lines × 5 samples) = 20 vertices.
    assert verts.shape == (20, 3)
    # 2 segments × (5-1) quads × 2 triangles = 16 faces.
    assert faces.shape == (16, 3)
    # All face indices must be within the vertex buffer.
    assert faces.max() < verts.shape[0]


def test_contour_draft_suggest_levels_basic():
    """suggest_levels returns interior levels excluding exact min/max."""
    import numpy as np

    from geoviz_plots.contour_draft import suggest_levels, DEFAULT_N_LEVELS

    grid = np.array([[0.0, 5.0], [10.0, 15.0]])
    levels = suggest_levels(grid, n_levels=4)
    # n_levels=4 -> linspace(lo, hi, 6)[1:-1] = 4 interior levels
    assert len(levels) == 4
    assert all(0.0 < v < 15.0 for v in levels)
    # Endpoints excluded
    assert 0.0 not in levels
    assert 15.0 not in levels


def test_contour_draft_suggest_levels_degenerate():
    """Flat / non-finite grids return degenerate level lists, not raise."""
    import numpy as np

    from geoviz_plots.contour_draft import suggest_levels

    # All-NaN -> empty
    assert suggest_levels(np.full((3, 3), np.nan)) == []
    # Flat grid (lo == hi) -> single level
    flat = np.full((3, 3), 7.5)
    assert suggest_levels(flat) == [7.5]


def test_contour_draft_coerce_grid_handles_none_cells():
    """coerce_grid converts JSON-stored None cells to NaN."""
    import numpy as np

    from geoviz_plots.contour_draft import coerce_grid

    params = {
        "grid_x": [0.0, 1.0, 2.0],
        "grid_y": [0.0, 1.0],
        "grid_z": [[1.0, None, 3.0], [4.0, 5.0, 6.0]],
    }
    gx, gy, gz = coerce_grid(params)
    assert gx.shape == (3,)
    assert gy.shape == (2,)
    assert gz.shape == (2, 3)
    assert np.isnan(gz[0, 1])
    assert gz[0, 0] == 1.0


def test_contour_draft_coerce_grid_missing_raises():
    """coerce_grid raises ValueError when grid arrays are absent."""
    import pytest

    from geoviz_plots.contour_draft import coerce_grid

    with pytest.raises(ValueError, match="grid_x/grid_y/grid_z"):
        coerce_grid({})
    with pytest.raises(ValueError, match="grid_x/grid_y/grid_z"):
        coerce_grid({"grid_x": [0.0], "grid_y": [0.0]})  # no grid_z


def test_contour_draft_extract_segments_synthetic():
    """extract_contour_segments returns ContourSegments for a simple peaked grid."""
    import numpy as np

    from geoviz_plots.contour_draft import extract_contour_segments, ContourSegment

    # 9x9 grid with a single peak at the center; contourpy will draw rings.
    xs = np.linspace(0.0, 8.0, 9)
    ys = np.linspace(0.0, 8.0, 9)
    X, Y = np.meshgrid(xs, ys)
    Z = np.exp(-((X - 4) ** 2 + (Y - 4) ** 2) / 4.0)  # peak=1.0 at center
    levels = [0.2, 0.5, 0.8]

    segments = extract_contour_segments(xs, ys, Z, levels)
    assert len(segments) >= 3  # at least one per level
    assert all(isinstance(s, ContourSegment) for s in segments)
    # Levels should be tagged on each segment
    segment_levels = {round(s.level, 1) for s in segments}
    assert {0.2, 0.5, 0.8}.issubset(segment_levels)
    # Each segment has >= 2 coordinate pairs (a real polyline)
    assert all(len(s.coordinates) >= 2 for s in segments)
    # Closed rings expected around a peak (not strictly guaranteed by every
    # level, but at least one should close)
    assert any(s.closed for s in segments)


def test_contour_draft_segments_to_line_features():
    """segments_to_line_features emits role=contour line_feature dicts."""
    from geoviz_plots.contour_draft import ContourSegment, segments_to_line_features

    segments = [
        ContourSegment(
            level=5.0,
            coordinates=[[0.0, 0.0], [1.0, 1.0], [2.0, 0.0]],
            closed=False,
            properties={"level": 5.0},
            id="seg-1",
        ),
        ContourSegment(
            level=10.0,
            coordinates=[[3.0, 3.0]],  # too short - should be skipped
            closed=False,
            id="seg-2",
        ),
    ]
    features = segments_to_line_features(
        segments, draft_id="draft-1", factor_type="sand", target_horizon="H1"
    )
    # Only the 2-point+ segment survives
    assert len(features) == 1
    feat = features[0]
    assert feat["kind"] == "line"
    assert feat["role"] == "contour"
    assert feat["name"] == "L=5"
    assert feat["properties"]["contour_draft_id"] == "draft-1"
    assert feat["properties"]["factor_type"] == "sand"
    assert feat["properties"]["target_horizon"] == "H1"
    assert feat["properties"]["level"] == 5.0


def test_factor_method_to_backend_and_mvp_note():
    """method_to_backend resolves UI labels; mvp_note_for tags the kriging MVP."""
    from geoviz_plots.factor import method_to_backend, mvp_note_for

    assert method_to_backend("IDW") == "idw"
    assert method_to_backend("克里金(MVP·线性)") == "linear"
    assert method_to_backend("方向趋势") == "directional"
    assert method_to_backend("unknown") == "idw"  # default fallback
    assert "ISS-KRIG-01" in mvp_note_for("linear")
    assert mvp_note_for("idw") is None


def test_factor_extract_xy_values_accepts_lnglat():
    """extract_xy_values accepts x/y or lng/lat, skips NaN and missing-value points."""
    import numpy as np

    from geoviz_plots.factor import extract_xy_values

    pts = [
        {"x": 1.0, "y": 2.0, "value": 10.0},
        {"lng": 3.0, "lat": 4.0, "z": 20.0},
        {"x": float("nan"), "y": 0, "value": 1.0},  # NaN -> skipped
        {"x": 5.0, "y": 6.0},  # no value/z/v -> skipped
    ]
    x, y, z = extract_xy_values(pts)
    assert len(z) == 2
    assert list(z) == [10.0, 20.0]


def test_factor_extract_xy_z_weights_skips_qc_flagged():
    """extract_xy_z_weights skips qc_flagged points and defaults q/b_i to 1.0."""
    import numpy as np

    from geoviz_plots.factor import extract_xy_z_weights

    pts = [
        {"x": 1.0, "y": 2.0, "value": 10.0, "q": 0.5, "b_i": 2.0},
        {"x": 3.0, "y": 4.0, "value": 20.0, "qc_flag": "bad"},  # skipped
        {"x": 5.0, "y": 6.0, "value": 30.0},  # q/b_i default
    ]
    x, y, z, q, bi = extract_xy_z_weights(pts)
    assert len(z) == 2
    assert list(z) == [10.0, 30.0]
    assert list(q) == [0.5, 1.0]
    assert list(bi) == [2.0, 1.0]


def test_factor_resolve_anisotropy_params():
    """resolve_anisotropy_params returns defaults for empty/negative inputs."""
    from geoviz_plots.factor import resolve_anisotropy_params, DEFAULT_SEMI_MAJOR, DEFAULT_SEMI_MINOR

    assert resolve_anisotropy_params(None) == (0.0, DEFAULT_SEMI_MAJOR, DEFAULT_SEMI_MINOR)
    assert resolve_anisotropy_params([{"azimuth_deg": 90, "semi_major": 2, "semi_minor": 0.5}]) == (90.0, 2.0, 0.5)
    # Negative axes fall back to defaults
    assert resolve_anisotropy_params([{"semi_major": -1}]) == (0.0, DEFAULT_SEMI_MAJOR, DEFAULT_SEMI_MINOR)


def test_factor_synthetic_sample_points_deterministic():
    """synthetic_sample_points is deterministic per (seed, factor_type)."""
    from geoviz_plots.factor import synthetic_sample_points

    s1 = synthetic_sample_points(seed=42, factor_type="砂岩含量", count=4)
    s2 = synthetic_sample_points(seed=42, factor_type="砂岩含量", count=4)
    assert s1 == s2
    assert len(s1) == 4
    assert all("x" in p and "y" in p and "value" in p for p in s1)
    # Different factor_type -> different RNG seed -> different points
    s3 = synthetic_sample_points(seed=42, factor_type="泥岩含量", count=4)
    assert s3 != s1


def test_factor_snapshot_hash_sorted_keys():
    """snapshot_hash is stable regardless of dict key order."""
    from geoviz_plots.factor import snapshot_hash

    h1 = snapshot_hash({"a": 1, "b": 2})
    h2 = snapshot_hash({"b": 2, "a": 1})
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_factor_interpolate_factor_grid_idw():
    """interpolate_factor_grid produces a JSON-serializable grid dict via IDW backend."""
    import math

    from geoviz_plots.factor import interpolate_factor_grid

    # 4 sample points forming a simple gradient
    pts = [
        {"x": 0.0, "y": 0.0, "value": 0.0},
        {"x": 10.0, "y": 0.0, "value": 10.0},
        {"x": 0.0, "y": 10.0, "value": 5.0},
        {"x": 10.0, "y": 10.0, "value": 15.0},
    ]
    result = interpolate_factor_grid(pts, method="IDW", grid_n=10, power=2.0)
    assert result["backend"] == "idw"
    assert result["method"] == "IDW"
    assert result["grid_n"] == 10
    assert len(result["grid_x"]) == 10
    assert len(result["grid_y"]) == 10
    assert len(result["grid_z"]) == 10 and len(result["grid_z"][0]) == 10
    assert result["n_points"] == 4
    assert result["min"] <= result["mean"] <= result["max"]
    assert result["r_squared"] is None or math.isfinite(result["r_squared"])
    # grid_z cells are either float or None (JSON-serializable)
    assert all(isinstance(v, float) or v is None for row in result["grid_z"] for v in row)


# ---------------------------------------------------------------------------
# map_edit API smoke tests (pure-Python fallback path; no map_edit_core in CI)
# ---------------------------------------------------------------------------


def test_map_edit_hit_test_point_and_ring():
    """hit_test finds a point feature by tolerance and a ring by point-in-polygon."""
    from geoviz_plots.map_edit import hit_test

    records = [
        {"id": "p1", "coordinates": [50.0, 50.0]},  # point far from ring
        {"id": "r1", "coordinates": [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]},  # closed square
    ]
    # Point hit within tolerance
    assert hit_test(records, 50.1, 50.0, tolerance=0.5) == "p1"
    # Ring hit: point inside the square (no point feature competes here)
    assert hit_test(records, 5.0, 5.0, tolerance=0.0) == "r1"
    # Miss: far away
    assert hit_test(records, 100.0, 100.0, tolerance=0.5) is None


def test_map_edit_set_vertex_syncs_closed_ring():
    """set_vertex on a closed ring updates both the vertex and its closing duplicate."""
    from geoviz_plots.map_edit import set_vertex

    ring = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]  # closed
    set_vertex(ring, 0, 1.0, 2.0)
    assert ring[0] == [1.0, 2.0]
    assert ring[-1] == [1.0, 2.0]  # closing duplicate synced


def test_map_edit_insert_and_delete_vertex():
    """insert_vertex adds a point; delete_vertex removes it, respecting min-size."""
    from geoviz_plots.map_edit import insert_vertex, delete_vertex

    ring = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]  # closed, 4 unique
    insert_vertex(ring, 1, 5.0, 0.0)
    assert len(ring) == 6  # 5 unique + close
    assert ring[1] == [5.0, 0.0]

    deleted = delete_vertex(ring, 1)
    assert deleted is True
    assert len(ring) == 5  # back to 4 unique + close


def test_map_edit_snap_point_finds_nearest():
    """snap_point returns the nearest candidate within tolerance."""
    from geoviz_plots.map_edit import snap_point

    candidates = [(0.0, 0.0), (10.0, 0.0), (5.0, 5.0)]
    # Snap near (5, 5)
    assert snap_point(candidates, 5.1, 5.0, tol=0.5) == (5.0, 5.0)
    # No candidate within tolerance -> original point
    assert snap_point(candidates, 100.0, 100.0, tol=0.5) == (100.0, 100.0)


def test_map_edit_validate_ring_detects_self_intersection():
    """validate_ring flags a bowtie (self-intersecting) polygon."""
    from geoviz_plots.map_edit import validate_ring

    # Bowtie: crosses itself at the center
    bowtie = [[0, 0], [10, 10], [10, 0], [0, 10], [0, 0]]
    issues = validate_ring(bowtie)
    assert len(issues) >= 1
    assert issues[0]["code"] == "self_intersection"

    # Valid simple square -> no issues
    square = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    assert validate_ring(square) == []


def test_map_edit_merge_rings_unions_two_squares():
    """merge_rings (shapely-backed) unions two overlapping polygons into one."""
    from geoviz_plots.map_edit import merge_rings, HAS_SHAPELY

    if not HAS_SHAPELY:
        pytest.skip("shapely not available")

    ring_a = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    ring_b = [[5, 0], [15, 0], [15, 10], [5, 10], [5, 0]]  # overlaps right half
    merged = merge_rings(ring_a, ring_b)
    assert merged is not None
    assert len(merged) >= 4  # a valid exterior ring


def test_map_edit_merge_rings_disjoint_rejects_not_drops():
    """#844: merging two DISJOINT rings unions into a MultiPolygon and the
    old code silently kept only the largest part — geometry loss. A union
    that cannot collapse into one ring must be rejected (None), never
    truncated to the larger operand."""
    from geoviz_plots.map_edit import merge_rings, HAS_SHAPELY

    if not HAS_SHAPELY:
        pytest.skip("shapely not available")

    ring_a = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    ring_b = [[20, 0], [30, 0], [30, 10], [20, 10], [20, 0]]  # disjoint
    assert merge_rings(ring_a, ring_b) is None


def test_map_edit_feature_editor_load_move_undo():
    """FeatureEditor loads a layer, moves a vertex, and undoes the transaction."""
    from geoviz_plots.map_edit import FeatureEditor

    editor = FeatureEditor()
    editor.load_layer({
        "type": "FeatureCollection",
        "features": [
            {"id": "f1", "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]}},
        ],
    })
    # Select vertex 1 (10, 0) and move it
    editor.on_pointer_down(10.0, 0.0, tolerance=1.0)
    assert editor.selected_feature_id == "f1"
    editor.on_pointer_move(12.0, 0.0, snap=False)
    editor.on_pointer_up()  # commits

    # Vertex should have moved
    feat = editor.features["f1"]
    ring = feat["geometry"]["coordinates"][0]
    assert ring[1] == [12.0, 0.0]

    # Undo restores
    assert editor.undo() is True
    ring = editor.features["f1"]["geometry"]["coordinates"][0]
    assert ring[1] == [10.0, 0.0]


def test_map_edit_feature_editor_topology_rollback():
    """FeatureEditor auto-rollbacks when a move creates a self-intersection."""
    from geoviz_plots.map_edit import FeatureEditor, TopologyError

    editor = FeatureEditor()
    editor.load_layer({
        "type": "FeatureCollection",
        "features": [
            {"id": "f1", "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]}},
        ],
    })
    editor.on_pointer_down(0.0, 0.0, tolerance=1.0)
    # Move vertex 0 (0,0) to (10,5) -> edges 1-2 and 3-0 properly intersect (bowtie)
    with pytest.raises(TopologyError):
        editor.on_pointer_move(10.0, 5.0, snap=False)
    # Auto-rollback: vertex unchanged
    ring = editor.features["f1"]["geometry"]["coordinates"][0]
    assert ring[0] == [0, 0]


def test_feature_editor_select_at_point_and_multipolygon():
    """#688: Point clicks must not TypeError; MultiPolygon vertices are walkable."""
    from geoviz_plots.map_edit import FeatureEditor

    editor = FeatureEditor()
    editor.load_layer({
        "type": "FeatureCollection",
        "features": [
            {"id": "pt", "geometry": {"type": "Point", "coordinates": [5.0, 5.0]}},
            {
                "id": "poly",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
                },
            },
            {
                "id": "mp",
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": [[[[20, 20], [22, 20], [22, 22], [20, 22], [20, 20]]]],
                },
            },
        ],
    })
    point_hit = editor.on_pointer_down(5.0, 5.0, tolerance=1.0)
    assert point_hit is not None
    assert point_hit["feature_id"] == "pt"
    assert point_hit["point"] == (5.0, 5.0)

    mp_hit = editor.on_pointer_down(22.0, 20.0, tolerance=1.0)
    assert mp_hit is not None
    assert mp_hit["feature_id"] == "mp"
    assert mp_hit["point"] == (22.0, 20.0)


def test_feature_editor_move_does_not_deepcopy_store(monkeypatch):
    """#684: vertex drag must not deepcopy the whole feature store per move."""
    import copy

    from geoviz_plots.map_edit import FeatureEditor

    editor = FeatureEditor()
    editor.load_layer({
        "type": "FeatureCollection",
        "features": [
            {
                "id": "f1",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
                },
            },
        ],
    })
    editor.on_pointer_down(10.0, 0.0, tolerance=1.0)
    calls = {"n": 0}
    orig = copy.deepcopy

    def _spy(obj):
        calls["n"] += 1
        return orig(obj)

    monkeypatch.setattr(copy, "deepcopy", _spy)
    assert editor.on_pointer_move(12.0, 0.0, snap=False) is True
    assert calls["n"] == 0
    ring = editor.features["f1"]["geometry"]["coordinates"][0]
    assert ring[1] == [12.0, 0.0]


def test_feature_editor_drag_uses_incremental_ring_validation():
    """#118: on_pointer_move validates only the edges adjacent to the moved
    vertex (O(V)) instead of re-checking every edge pair of the ring
    (O(V^2)) plus the whole geometry via shapely. A drag on a large ring
    must stay inside a generous per-move budget; the full-ring reference
    must agree with the incremental result on a bow-tie drag."""
    import math
    import time

    from geoviz_plots.map_edit import FeatureEditor
    from geoviz_plots.map_edit.api import validate_ring, validate_ring_local

    n = 1500
    ring = [[math.cos(2 * math.pi * i / n) * 10.0,
             math.sin(2 * math.pi * i / n) * 10.0] for i in range(n)]
    ring.append(list(ring[0]))
    editor = FeatureEditor()
    editor.load_layer({
        "type": "FeatureCollection",
        "features": [{"id": "big",
                      "geometry": {"type": "Polygon", "coordinates": [ring]}}],
    })
    editor.on_pointer_down(ring[1][0], ring[1][1], tolerance=0.5)

    t0 = time.perf_counter()
    for k in range(10):
        assert editor.on_pointer_move(ring[1][0] + 0.01 * (k + 1), ring[1][1], snap=False) is True
    elapsed = time.perf_counter() - t0
    # 10 incremental moves on a 1500-vertex ring: ~ms each locally; the old
    # full O(V^2) + shapely re-validation measured in whole seconds.
    assert elapsed < 2.0, f"drag validation regressed: {elapsed:.2f}s for 10 moves"

    # Sufficiency: any self-intersection the full check flags on a dragged
    # ring involves a moved-vertex-adjacent edge, so the incremental check
    # flags it too (bow-tie from dragging vertex 0 across the ring).
    bowtie = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    dragged = [[10, 5], [10, 0], [10, 10], [0, 10], [10, 5]]
    assert validate_ring(dragged) != []
    assert validate_ring_local(dragged, [0]) != []
    assert validate_ring_local(bowtie, [0]) == []


def test_feature_editor_defers_whole_geometry_check_to_pointer_up():
    """#118: dragging an outer-ring vertex across a hole keeps the outer
    ring simple (incremental check passes during the move) but makes the
    assembled Polygon invalid. The full validation must then intercept at
    pointer release: TopologyError is raised, the drag is rolled back to
    the last committed state and nothing enters the undo history."""
    from geoviz_plots.map_edit import FeatureEditor, TopologyError

    editor = FeatureEditor()
    editor.load_layer({
        "type": "FeatureCollection",
        "features": [{
            "id": "f1",
            "geometry": {"type": "Polygon", "coordinates": [
                [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],      # outer
                [[3.5, 2], [7, 2], [7, 6], [3.5, 6], [3.5, 2]],    # hole
            ]},
        }],
    })
    editor.on_pointer_down(10.0, 0.0, tolerance=1.0)  # outer vertex slot 1

    # The move itself succeeds: the outer ring stays simple, only the
    # shell/hole relationship breaks (invisible to per-ring checks).
    assert editor.on_pointer_move(5.0, 5.0, snap=False) is True

    with pytest.raises(TopologyError):
        editor.on_pointer_up()

    ring = editor.features["f1"]["geometry"]["coordinates"][0]
    assert ring[1] == [10.0, 0.0], "invalid drag must be rolled back entirely"
    assert not editor.can_undo, "nothing may be committed from an invalid drag"


def test_factor_loo_r2_keeps_negative_values():
    """#687: LOO R² worse than the mean must stay negative, not clamp to 0."""
    from geoviz_plots.factor.interpolation import _r_squared

    observed = np.array([0.0, 1.0, 2.0, 3.0])
    preds = np.array([3.0, 2.0, 1.0, 0.0])
    r2 = _r_squared(observed, preds)
    assert r2 < 0.0


def test_factor_interpolate_grid_reports_nearest_fallback():
    """#690: collinear 克里金/linear samples must mark the nearest fallback."""
    from geoviz_plots.factor import interpolate_factor_grid

    pts = [
        {"x": 0.0, "y": 0.0, "value": 1.0},
        {"x": 1.0, "y": 0.0, "value": 2.0},
        {"x": 2.0, "y": 0.0, "value": 3.0},
    ]
    result = interpolate_factor_grid(pts, method="克里金", grid_n=5)
    assert result["degraded"] is True
    assert result["fallback"] == "nearest"


# --- Phase-2 T3: extract_filled_contours extensions (study_area_clip / palette) ---

def test_extract_filled_contours_palette_resolves_band_color():
    """The ``palette`` kwarg resolves each band's ``color`` against COLORMAPS."""
    grid_x = np.linspace(0.0, 2.0, 4)
    grid_y = np.linspace(0.0, 2.0, 4)
    grid_z = np.add.outer(grid_y, grid_x)

    bands_viridis = extract_filled_contours(
        grid_x, grid_y, grid_z, levels=[1.0, 3.0, 5.0], palette="viridis",
    )
    bands_thermal = extract_filled_contours(
        grid_x, grid_y, grid_z, levels=[1.0, 3.0, 5.0], palette="thermal",
    )
    assert len(bands_viridis) == 2 == len(bands_thermal)
    # Same band midpoint -> different color under different palettes.
    assert bands_viridis[0].color != bands_thermal[0].color
    # Unknown palette falls back to viridis (SurfaceWidget default behavior).
    bands_unknown = extract_filled_contours(
        grid_x, grid_y, grid_z, levels=[1.0, 3.0, 5.0], palette="not_a_cmap",
    )
    assert bands_unknown[0].color == bands_viridis[0].color


def test_extract_filled_contours_study_area_clip_returns_bands():
    """``study_area_clip`` is accepted; with shapely it intersects band rings."""
    grid_x = np.linspace(0.0, 4.0, 5)
    grid_y = np.linspace(0.0, 4.0, 5)
    grid_z = np.add.outer(grid_y, grid_x)

    # Clip to a small square in the lower-left quadrant.
    clip = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0), (0.0, 0.0)]
    bands = extract_filled_contours(
        grid_x, grid_y, grid_z, levels=[1.0, 5.0], study_area_clip=clip,
    )
    assert len(bands) == 1
    band = bands[0]
    assert isinstance(band, BandedFill)
    assert band.level_min == 1.0 and band.level_max == 5.0
    # Color + label still populated when clipping is on.
    assert band.color is not None
    assert band.label == "1-5"


def test_extract_filled_contours_empty_levels_returns_empty():
    bands = extract_filled_contours(
        np.linspace(0, 1, 3), np.linspace(0, 1, 3),
        np.zeros((3, 3)), levels=[],
    )
    assert bands == []


def test_extract_filled_contours_fill_type_kwarg_accepted():
    """``fill_type`` is passed through to contourpy without error."""
    grid_x = np.linspace(0.0, 2.0, 4)
    grid_y = np.linspace(0.0, 2.0, 4)
    grid_z = np.add.outer(grid_y, grid_x)
    bands = extract_filled_contours(
        grid_x, grid_y, grid_z, levels=[1.0, 3.0], fill_type="OuterOffset",
    )
    assert len(bands) == 1


# --- Phase-2 T2: CRS facade helpers ---

def test_crs_helpers_list_known_crs_includes_cnpc_datums():
    from geoviz_plots.crs import list_known_crs
    codes = list_known_crs()
    # WGS84 + CNPC-standard geodetic datums (T2 / #246 resolution).
    assert "EPSG:4326" in codes   # WGS 84
    assert "EPSG:4490" in codes   # CGCS2000
    assert "EPSG:4610" in codes   # Beijing 1954
    assert "EPSG:4612" in codes   # Xian 1980


def test_crs_coerce_identity_when_source_equals_project():
    from geoviz_plots.crs import coerce_to_project_crs
    pts = np.array([[116.0, 30.0], [117.0, 31.0]])
    out = coerce_to_project_crs(pts, "EPSG:4326")
    assert np.allclose(out, pts)


def test_crs_coerce_reprojects_wgs84_to_web_mercator():
    from geoviz_plots.crs import set_project_crs, get_project_crs, coerce_to_project_crs
    import pyproj
    try:
        set_project_crs("EPSG:3857")
        assert get_project_crs() == "EPSG:3857"
        out = coerce_to_project_crs([116.0, 30.0], "EPSG:4326")
        # Cross-check against pyproj's own transformer.
        t = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        x_ref, y_ref = t.transform(116.0, 30.0)
        assert abs(out[0] - x_ref) < 1e-6 and abs(out[1] - y_ref) < 1e-6
    finally:
        set_project_crs("EPSG:4326")  # reset to default


def test_crs_set_project_crs_rejects_invalid_code():
    from geoviz_plots.crs import set_project_crs
    import pyproj
    with pytest.raises(pyproj.exceptions.CRSError):
        set_project_crs("NOT_A_CRS")




def test_feature_editor_degree_layer_does_not_merge_nearby_vertices():
    """#844: the coincident-vertex tolerance was a hard-coded absolute 1e-4
    map units — on degree-coordinate layers that is ~11 m, silently treating
    distinct nearby vertices as one shared node. Dragging one must NOT drag
    a vertex 1e-4 degrees away."""
    from geoviz_plots.map_edit import FeatureEditor

    editor = FeatureEditor()
    editor.load_layer({
        "type": "FeatureCollection",
        "features": [
            {"id": "A", "geometry": {"type": "Polygon", "coordinates": [
                [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0]]
            ]}},
            {"id": "B", "geometry": {"type": "Polygon", "coordinates": [
                # Vertex 1e-4 degrees north of A's (10, 0) — ~11 m apart.
                [[10.0, 0.0001], [20.0, 0.0001], [20.0, 10.0], [10.0, 10.0], [10.0, 0.0001]]
            ]}},
        ],
    })
    editor.on_pointer_down(10.0, 0.0, tolerance=1.0)  # selects A's (10, 0)
    assert editor.selected_feature_id == "A"
    editor.on_pointer_move(12.0, 2.0, snap=False)
    editor.on_pointer_up()

    b_ring = editor.features["B"]["geometry"]["coordinates"][0]
    assert b_ring[0] == [10.0, 0.0001], (
        "distinct vertex 1e-4 deg away must NOT be treated as coincident"
    )


def test_feature_editor_degree_layer_snap_default_does_not_jump_degrees():
    """#844: the snap tolerance defaulted to a fixed 5.0 map units — ~555 km
    on degree layers; dragging near a vertex 0.5 degrees away snapped to it.
    The scale-aware default (1% of median segment length) must not snap there,
    while an explicit large tolerance still does."""
    from geoviz_plots.map_edit import FeatureEditor

    editor = FeatureEditor()
    editor.load_layer({
        "type": "FeatureCollection",
        "features": [
            {"id": "A", "geometry": {"type": "Polygon", "coordinates": [
                [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0]]
            ]}},
            {"id": "B", "geometry": {"type": "Polygon", "coordinates": [
                [[5.0, 5.5], [15.0, 5.5], [15.0, 20.0], [5.0, 20.0], [5.0, 5.5]]
            ]}},
        ],
    })
    editor.on_pointer_down(10.0, 0.0, tolerance=1.0)  # selects A's (10, 0)
    # Drag toward (5, 5); B's (5, 5.5) vertex is 0.5 deg away.
    editor.on_pointer_move(5.0, 5.0, snap=True)
    editor.on_pointer_up()

    a_ring = editor.features["A"]["geometry"]["coordinates"][0]
    moved = a_ring[1]  # A's (10, 0) vertex slot
    assert moved == [5.0, 5.0], (
        "scale-aware default snap must not jump 0.5 deg to a distant vertex"
    )

    # Explicit large tolerance still snaps (mechanism preserved).
    editor2 = FeatureEditor()
    editor2.load_layer({
        "type": "FeatureCollection",
        "features": [
            {"id": "A", "geometry": {"type": "Polygon", "coordinates": [
                [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0]]
            ]}},
            {"id": "B", "geometry": {"type": "Polygon", "coordinates": [
                [[5.0, 5.5], [15.0, 5.5], [15.0, 20.0], [5.0, 20.0], [5.0, 5.5]]
            ]}},
        ],
    })
    editor2.on_pointer_down(10.0, 0.0, tolerance=1.0)
    editor2.on_pointer_move(5.0, 5.0, snap=True, snap_tolerance=10.0)
    editor2.on_pointer_up()
    a2_ring = editor2.features["A"]["geometry"]["coordinates"][0]
    assert a2_ring[1] == [5.0, 5.5], (
        "explicit snap_tolerance must still snap to the nearby vertex"
    )
