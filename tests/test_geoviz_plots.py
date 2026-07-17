"""Tests for geoviz_plots package (Chart axes, IDW interpolation, and custom plotting widgets)."""
import pytest
import math
from PySide6.QtCore import QPointF
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





