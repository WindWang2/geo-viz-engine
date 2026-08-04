"""Tests for geoviz_plots package (Chart axes, IDW interpolation, and custom plotting widgets)."""
import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QWheelEvent

from geoviz_plots.chart.axes import nice_number, calculate_ticks

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
    """Verify that InterpolationWorker runs asynchronously in QThread and emits finished signal."""
    x = np.array([0.0, 1.0, 0.0, 1.0])
    y = np.array([0.0, 0.0, 1.0, 1.0])
    z = np.array([0.0, 10.0, 10.0, 20.0])
    grid_x = np.linspace(0, 1, 5)
    grid_y = np.linspace(0, 1, 5)
    
    worker = InterpolationWorker(x, y, z, grid_x, grid_y, method="linear")
    
    # Track signal emission
    with qtbot.waitSignal(worker.finished, timeout=2000) as blocker:
        worker.start()
        
    grid_z = blocker.args[0]
    assert grid_z.shape == (5, 5)
    assert grid_z[2, 2] == pytest.approx(10.0)


from geoviz_plots.surface.marching_squares import extract_contour_lines, extract_filled_contours

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
    
    # 2. Test Filled Contour Extraction
    filled_list = extract_filled_contours(grid_x, grid_y, grid_z, levels=[0.2, 0.8])
    # Returns a list of tuples: (level_min, level_max, polygons, offsets)
    assert len(filled_list) == 1
    lev_min, lev_max, polys, offsets = filled_list[0]
    assert lev_min == 0.2
    assert lev_max == 0.8
    assert isinstance(polys, list)
    assert isinstance(offsets, list)


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
