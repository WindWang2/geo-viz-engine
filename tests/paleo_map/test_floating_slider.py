import pytest
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QMouseEvent
from geoviz_paleo_map.floating_slider import FloatingScaleSlider


def test_slider_init(qtbot):
    slider = FloatingScaleSlider()
    qtbot.addWidget(slider)
    assert slider._zoom == 2.0
    assert slider.height() == 54
    assert slider.width() == 320


def test_slider_params_and_conversions(qtbot):
    slider = FloatingScaleSlider()
    qtbot.addWidget(slider)

    # Set some typical parameters
    # canvas_w=800, kpd=100.0, thresholds=[2.0, 5.0]
    slider.set_params(800, 100.0, [2.0, 5.0])

    # Check minimum and maximum denominators are calculated
    assert slider._scale_min > 0
    assert slider._scale_max > slider._scale_min
    assert slider._log2_smin == pytest.approx(slider._log2_smin)

    # Check zoom to fraction and back
    zoom = 5.0
    frac = slider._zoom_to_frac(zoom)
    assert 0.0 <= frac <= 1.0

    zoom_back = slider._frac_to_zoom(frac)
    assert zoom_back == pytest.approx(zoom, abs=1e-4)


def test_slider_signals(qtbot):
    slider = FloatingScaleSlider()
    qtbot.addWidget(slider)
    slider.set_params(800, 111.32, [3.0, 6.0])

    # Test signal emission when programmatically setting zoom via slider methods
    with qtbot.wait_signal(slider.zoom_changed) as blocker:
        slider._zoom_by(1.0)
    assert blocker.args[0] == pytest.approx(3.0)

    with qtbot.wait_signal(slider.zoom_changed) as blocker:
        slider._zoom_by(-0.5)
    assert blocker.args[0] == pytest.approx(2.5)


def test_slider_drag_calculations(qtbot):
    slider = FloatingScaleSlider()
    qtbot.addWidget(slider)
    slider.set_params(800, 111.32, [3.0, 6.0])

    # Test x coordinate mapping
    x0, x1 = slider._track_rect()
    assert x0 < x1

    # Leftmost position should equal minimum denominator (maximum zoom = 10.0)
    frac_left = slider._x_to_frac(x0)
    assert frac_left == 0.0
    zoom_left = slider._frac_to_zoom(frac_left)
    assert zoom_left == pytest.approx(10.0)

    # Rightmost position should equal maximum denominator (minimum zoom = 0.1)
    frac_right = slider._x_to_frac(x1)
    assert frac_right == 1.0
    zoom_right = slider._frac_to_zoom(frac_right)
    assert zoom_right == pytest.approx(0.1)
