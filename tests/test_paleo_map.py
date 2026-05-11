import json
import os
from unittest.mock import patch, MagicMock
from PySide6.QtCore import Qt

from src.pages.paleo_map.renderer import PaleoMapRenderer
from src.pages.paleo_map import PaleoMapPage
from geoviz_well_log.pattern_map import PATTERN_MAP, FACIES_COLORS


def test_renderer_initialization(qtbot):
    renderer = PaleoMapRenderer()
    qtbot.addWidget(renderer)
    assert renderer._tmp_html is not None
    assert os.path.exists(renderer._tmp_html)


def test_renderer_load_valid_geojson(qtbot, tmp_path):
    renderer = PaleoMapRenderer()
    qtbot.addWidget(renderer)

    valid_json = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"facies": "砂岩"},
                "geometry": {"type": "Polygon", "coordinates": [[[0,0], [1,0], [1,1], [0,1], [0,0]]]}
            }
        ]
    }
    geo_file = tmp_path / "valid.geojson"
    with open(geo_file, "w", encoding="utf-8") as f:
        json.dump(valid_json, f)

    renderer.load_geojson(str(geo_file))
    
    # We verify it doesn't crash and the tmp_html file was recreated
    assert renderer._tmp_html is not None
    assert os.path.exists(renderer._tmp_html)
    with open(renderer._tmp_html, "r", encoding="utf-8") as f:
        html = f.read()
        assert "file://" in html
        assert "faciesColors" in html
        assert "boundaryStyle" in html
        assert "makeCompositePattern" in html
        assert "preloadPatterns" in html


def test_renderer_missing_svg_fallback(qtbot, tmp_path):
    renderer = PaleoMapRenderer()
    qtbot.addWidget(renderer)

    valid_json = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"facies": "未知神秘岩性"},  # No mapping exists
                "geometry": {"type": "Polygon", "coordinates": [[[0,0], [1,0], [1,1], [0,1], [0,0]]]}
            }
        ]
    }
    geo_file = tmp_path / "unknown.geojson"
    with open(geo_file, "w", encoding="utf-8") as f:
        json.dump(valid_json, f)

    renderer.load_geojson(str(geo_file))
    assert renderer._tmp_html is not None


@patch('src.pages.paleo_map.page.QMessageBox.information')
def test_page_empty_state_and_load(mock_info, qtbot, tmp_path):
    page = PaleoMapPage()
    qtbot.addWidget(page)

    # Initial state should be empty widget
    assert page.stack.currentWidget() == page.empty_widget

    # Empty FeatureCollection: new page detects "no valid data" and stays on empty_widget
    empty_json = {"type": "FeatureCollection", "features": []}
    empty_file = tmp_path / "empty.geojson"
    with open(empty_file, "w", encoding="utf-8") as f:
        json.dump(empty_json, f)

    page._load_file(str(empty_file))
    assert page.stack.currentWidget() == page.empty_widget
    mock_info.assert_called_once()

    # Valid FeatureCollection with a real feature: switches to map_container
    valid_json = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"facies": "砂岩"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                },
            }
        ],
    }
    geo_file = tmp_path / "valid.geojson"
    with open(geo_file, "w", encoding="utf-8") as f:
        json.dump(valid_json, f)

    page._load_file(str(geo_file))
    assert page.stack.currentWidget() == page.map_container


@patch('src.pages.paleo_map.page.QMessageBox.warning')
def test_page_load_invalid_file(mock_warning, qtbot):
    page = PaleoMapPage()
    qtbot.addWidget(page)

    page._load_file("/path/that/does/not/exist.json")
    
    mock_warning.assert_called_once()
    assert page.stack.currentWidget() == page.empty_widget


@patch('src.pages.paleo_map.page.QFileDialog.getSaveFileName')
def test_page_export_image(mock_get_save, qtbot, tmp_path):
    page = PaleoMapPage()
    qtbot.addWidget(page)

    export_path = tmp_path / "test_export.png"
    mock_get_save.return_value = (str(export_path), "")

    # Mock the map_view.grab() since we are headless in tests
    mock_pixmap = MagicMock()
    page.map_view.grab = MagicMock(return_value=mock_pixmap)

    # Call _export_png directly (new _on_export_clicked shows a dialog)
    page._export_png()

    mock_pixmap.save.assert_called_once_with(str(export_path), "PNG")


def test_renderer_boundary_styles_in_template(qtbot, tmp_path):
    renderer = PaleoMapRenderer()
    qtbot.addWidget(renderer)

    valid_json = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"facies": "砂岩", "boundary_type": "confirmed"},
             "geometry": {"type": "Polygon", "coordinates": [[[0,0],[1,0],[1,1],[0,1],[0,0]]]}},
            {"type": "Feature", "properties": {"facies": "灰岩", "boundary_type": "inferred"},
             "geometry": {"type": "Polygon", "coordinates": [[[1,1],[2,1],[2,2],[1,2],[1,1]]]}},
            {"type": "Feature", "properties": {"facies": "深水盆地", "boundary_type": "fault"},
             "geometry": {"type": "Polygon", "coordinates": [[[2,2],[3,2],[3,3],[2,3],[2,2]]]}}
        ]
    }
    geo_file = tmp_path / "boundaries.geojson"
    geo_file.write_text(json.dumps(valid_json), encoding="utf-8")
    renderer.load_geojson(str(geo_file))

    with open(renderer._tmp_html, "r", encoding="utf-8") as f:
        html = f.read()
        assert "confirmed" in html
        assert "inferred" in html
        assert "fault" in html
        assert "#e53e3e" in html


def test_page_compare_mode_toggle(qtbot, tmp_path):
    csv_content = "period,facies,lon_min,lon_max,lat_min,lat_max\n"
    csv_content += "期A,砂岩,100,105,30,35\n"
    csv_content += "期B,灰岩,100,105,30,35\n"
    csv_file = tmp_path / "compare.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    page = PaleoMapPage()
    qtbot.addWidget(page)
    page._load_file(str(csv_file))

    assert page.stack.currentWidget() == page.map_container
    assert page._period_combo.count() == 2

    page._toggle_compare(True)
    assert hasattr(page, 'map_view_b')
    assert hasattr(page, '_splitter')

    page._toggle_compare(False)
    assert not hasattr(page, 'map_view_b')


def test_page_compare_mode_rejects_single_period(qtbot, tmp_path):
    """Compare mode with <2 periods shows message instead of activating."""
    valid_json = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"facies": "砂岩"},
             "geometry": {"type": "Polygon", "coordinates": [[[0,0],[1,0],[1,1],[0,1],[0,0]]]}}
        ]
    }
    geo_file = tmp_path / "single.geojson"
    geo_file.write_text(json.dumps(valid_json), encoding="utf-8")

    page = PaleoMapPage()
    qtbot.addWidget(page)
    page._load_file(str(geo_file))

    with patch('src.pages.paleo_map.page.QMessageBox.information') as mock_msg:
        page._toggle_compare(True)
        mock_msg.assert_called_once()
        assert not page._compare_btn.isChecked()


def test_facies_colors_has_entry_for_every_pattern():
    for facies_keyword in PATTERN_MAP:
        assert facies_keyword in FACIES_COLORS, f"Missing color for {facies_keyword}"


def test_new_patterns_have_svg_files():
    from pathlib import Path
    patterns_dir = Path(__file__).parent.parent / "src" / "patterns"
    from geoviz_well_log.pattern_map import PATTERN_MAP
    for facies, pattern_name in PATTERN_MAP.items():
        svg_filename = pattern_name.replace("-", "_") + ".svg"
        svg_path = patterns_dir / svg_filename
        assert svg_path.exists(), f"Missing SVG for {facies} -> {svg_filename}"


def test_facies_colors_are_valid_hex():
    import re
    for facies, color in FACIES_COLORS.items():
        assert re.match(r'^#[0-9a-f]{6}$', color), f"Invalid color {color} for {facies}"
