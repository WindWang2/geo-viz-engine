from geoviz_paleo_map.label_policy import (
    chrome_font_size,
    region_label_font_size,
    text_fits,
)


def test_region_label_font_grows_with_screen_area():
    small = region_label_font_size(40.0, 24.0, base_size=9, zoom=2.0)
    large = region_label_font_size(220.0, 120.0, base_size=9, zoom=2.0)

    assert large > small
    assert small >= 7


def test_region_label_font_respects_hierarchy_cap():
    font_px = region_label_font_size(260.0, 160.0, base_size=8, zoom=6.0)

    assert font_px <= 14


def test_chrome_font_scales_with_viewport_size():
    compact = chrome_font_size(420, 320, base_size=8)
    spacious = chrome_font_size(1600, 1000, base_size=8)

    assert spacious > compact
    assert 7 <= compact <= 12
    assert 7 <= spacious <= 12


def test_text_fit_allows_wrapping_for_long_labels():
    assert text_fits("三角洲前缘", 96, 40, font_px=10, max_lines=2)
    assert not text_fits("三角洲前缘水下分流河道砂体复合体", 40, 12, font_px=12, max_lines=1)
