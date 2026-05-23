import pytest
from geoviz_well_log.renderer.track_base import (
    BaseTrack, ECHARTS_BORDER, ECHARTS_GRID, ECHARTS_HEADER_BG,
    ECHARTS_SUB_HEADER_BG, ECHARTS_TEXT,
)
from geoviz_well_log.renderer.depth_track import DepthTrack


def test_echarts_border_color():
    assert ECHARTS_BORDER == "#94a3b8"

def test_echarts_grid_color():
    assert ECHARTS_GRID == "#cbd5e1"

def test_echarts_header_bg():
    assert ECHARTS_HEADER_BG == "#e2e8f0"

def test_echarts_sub_header_bg():
    assert ECHARTS_SUB_HEADER_BG == "#f8fafc"

def test_echarts_text_color():
    assert ECHARTS_TEXT == "#0f172a"

def test_base_track_header_height_default(qtbot):
    t = DepthTrack(top_depth=0, bottom_depth=100)
    qtbot.addWidget(t)
    assert t.header_height == 56
