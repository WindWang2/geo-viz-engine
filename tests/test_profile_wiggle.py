import numpy as np
import pytest

from geoviz_seismic.profile_wiggle import ProfileWiggle


def test_profile_wiggle_init(qtbot):
    widget = ProfileWiggle()
    qtbot.addWidget(widget)
    assert not widget.has_data()
    assert widget.trace_step() == 1


def test_profile_wiggle_render(qtbot):
    widget = ProfileWiggle()
    qtbot.addWidget(widget)
    data = np.random.randn(20, 50).astype(np.float32)
    widget.render(data, trace_step=2)
    assert widget.has_data()
    assert widget.trace_step() == 2


def test_profile_wiggle_no_data(qtbot):
    widget = ProfileWiggle()
    qtbot.addWidget(widget)
    assert not widget.has_data()
    assert widget.trace_step() == 1


def test_profile_wiggle_set_trace_step(qtbot):
    widget = ProfileWiggle()
    qtbot.addWidget(widget)
    data = np.random.randn(10, 20).astype(np.float32)
    widget.render(data, trace_step=1)
    widget.set_trace_step(3)
    assert widget.trace_step() == 3


def test_profile_wiggle_set_trace_step_before_render(qtbot):
    widget = ProfileWiggle()
    qtbot.addWidget(widget)
    widget.set_trace_step(4)
    assert widget.trace_step() == 4


def test_profile_wiggle_paint_event_no_crash(qtbot):
    widget = ProfileWiggle()
    qtbot.addWidget(widget)
    data = np.random.randn(20, 50).astype(np.float32)
    widget.render(data, trace_step=2)
    widget.show()
    qtbot.waitExposed(widget)
    widget.update()

