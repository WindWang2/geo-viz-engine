import pytest
from geoviz_well_log.renderer.systems_tract import SystemsTractTrack, _TRACT_COLORS


def test_tst_color_matches_echarts():
    assert _TRACT_COLORS.get("TST") == "#93c5fd"

def test_hst_color_matches_echarts():
    assert _TRACT_COLORS.get("HST") == "#fde047"

def test_lst_color_matches_echarts():
    assert _TRACT_COLORS.get("LST") == "#70AD47"

def test_chinese_tst_color():
    assert _TRACT_COLORS.get("海侵体系域") == "#93c5fd"

def test_chinese_hst_color():
    assert _TRACT_COLORS.get("高位体系域") == "#fde047"

def test_chinese_lst_color():
    assert _TRACT_COLORS.get("低位体系域") == "#70AD47"
