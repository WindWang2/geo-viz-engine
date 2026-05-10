import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from geoviz_seismic.profile_vd import ProfileVD


def test_profile_vd_init(qtbot):
    widget = ProfileVD()
    qtbot.addWidget(widget)
    assert not widget.has_data()


def test_profile_vd_render(qtbot):
    widget = ProfileVD()
    qtbot.addWidget(widget)
    data = np.random.randn(20, 50).astype(np.float32)
    widget.render(data)
    assert widget.has_data()


def test_profile_vd_default_colormap(qtbot):
    widget = ProfileVD()
    qtbot.addWidget(widget)
    assert widget.current_colormap() == "seismic"


def test_profile_vd_set_colormap(qtbot):
    widget = ProfileVD()
    qtbot.addWidget(widget)
    widget.set_colormap("gray")
    assert widget.current_colormap() == "gray"


def test_profile_vd_set_colormap_before_render(qtbot):
    widget = ProfileVD()
    qtbot.addWidget(widget)
    widget.set_colormap("jet")
    data = np.random.randn(10, 10).astype(np.float32)
    widget.render(data)
    assert widget.has_data()
    assert widget.current_colormap() == "jet"


def test_profile_vd_set_colormap_after_render(qtbot):
    widget = ProfileVD()
    qtbot.addWidget(widget)
    data = np.random.randn(10, 10).astype(np.float32)
    widget.render(data, colormap="seismic")
    assert widget.current_colormap() == "seismic"
    widget.set_colormap("gray")
    assert widget.current_colormap() == "gray"


def test_profile_vd_slice_info_stored(qtbot):
    from geoviz_seismic.models import SliceInfo

    widget = ProfileVD()
    qtbot.addWidget(widget)
    data = np.random.randn(10, 10).astype(np.float32)
    info = SliceInfo(
        slice_type="inline",
        position=100,
        axis_h_label="Xline",
        axis_v_label="Time (ms)",
        axis_h_values=list(range(10)),
        axis_v_values=list(range(10)),
    )
    widget.render(data, slice_info=info)
    assert widget.slice_info() is info


def test_profile_vd_slice_info_none_by_default(qtbot):
    widget = ProfileVD()
    qtbot.addWidget(widget)
    assert widget.slice_info() is None


def test_profile_vd_paint_event_no_crash(qtbot):
    widget = ProfileVD()
    qtbot.addWidget(widget)
    data = np.random.randn(20, 50).astype(np.float32)
    widget.render(data)
    widget.show()
    qtbot.waitExposed(widget)
    # paintEvent should not crash
    widget.update()
