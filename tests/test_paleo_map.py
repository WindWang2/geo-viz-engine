import json
import os
from unittest.mock import patch, MagicMock
from PySide6.QtCore import Qt

from src.renderers.paleo_map_renderer import PaleoMapRenderer
from src.pages.paleo_map_page import PaleoMapPage
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


@patch('src.pages.paleo_map_page.QMessageBox.information')
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


@patch('src.pages.paleo_map_page.QMessageBox.warning')
def test_page_load_invalid_file(mock_warning, qtbot):
    page = PaleoMapPage()
    qtbot.addWidget(page)

    page._load_file("/path/that/does/not/exist.json")
    
    mock_warning.assert_called_once()
    assert page.stack.currentWidget() == page.empty_widget


@patch('src.pages.paleo_map_page.QFileDialog.getSaveFileName')
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
