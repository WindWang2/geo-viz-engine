import numpy as np
import pytest

from geoviz_seismic.profile_widget import ProfileWidget


def test_profile_widget_default_vd(qtbot):
    widget = ProfileWidget()
    qtbot.addWidget(widget)
    assert widget._mode == "vd"


def test_profile_widget_switch_mode(qtbot):
    widget = ProfileWidget()
    qtbot.addWidget(widget)
    widget.set_display_mode("wiggle")
    assert widget._mode == "wiggle"


def test_profile_widget_switch_back_to_vd(qtbot):
    widget = ProfileWidget()
    qtbot.addWidget(widget)
    widget.set_display_mode("wiggle")
    widget.set_display_mode("vd")
    assert widget._mode == "vd"


def test_profile_widget_update_profile_vd(qtbot):
    widget = ProfileWidget()
    qtbot.addWidget(widget)
    data = np.random.randn(20, 50).astype(np.float32)
    widget.update_profile(data)
    assert widget._vd.has_data()


def test_profile_widget_update_profile_wiggle(qtbot):
    widget = ProfileWidget()
    qtbot.addWidget(widget)
    widget.set_display_mode("wiggle")
    data = np.random.randn(20, 50).astype(np.float32)
    widget.update_profile(data, trace_step=3)
    assert widget._wiggle.has_data()
    assert widget._wiggle.trace_step() == 3


def test_profile_widget_set_colormap(qtbot):
    widget = ProfileWidget()
    qtbot.addWidget(widget)
    widget.set_colormap("gray")
    assert widget._vd.current_colormap() == "gray"


def test_profile_widget_set_wiggle_density(qtbot):
    widget = ProfileWidget()
    qtbot.addWidget(widget)
    widget.set_wiggle_density(5)
    assert widget._wiggle.trace_step() == 5


def test_profile_widget_paint_event_no_crash(qtbot):
    widget = ProfileWidget()
    qtbot.addWidget(widget)
    data = np.random.randn(20, 50).astype(np.float32)
    widget.update_profile(data)
    widget.show()
    qtbot.waitExposed(widget)
    widget.update()
