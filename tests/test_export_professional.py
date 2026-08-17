import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from PySide6.QtCore import QRectF

from geoviz_paleo_map import PaleoMapCanvas
from geoviz_paleo_map.export_professional import export_professional_figure


SAMPLE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"name": "测试区", "facies": "砂岩"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[110.0, 20.0], [120.0, 20.0], [120.0, 30.0],
                                [110.0, 30.0], [110.0, 20.0]]],
            },
        }
    ],
}


def test_professional_svg_creates_file_with_title(qtbot):
    canvas = PaleoMapCanvas()
    canvas.load_features(SAMPLE["features"], period_name="测试")
    qtbot.addWidget(canvas)
    canvas.resize(400, 300)
    canvas.show()
    qtbot.waitExposed(canvas)

    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
        path = Path(f.name)

    try:
        export_professional_figure(
            canvas, str(path), format="svg",
            title="测试古地理图",
            page_size="A4", orientation="landscape",
        )
        assert path.exists()
        assert path.stat().st_size > 100

        tree = ET.parse(path)
        root = tree.getroot()
        text = ET.tostring(root, encoding="unicode")
        assert "测试古地理图" in text
    finally:
        path.unlink(missing_ok=True)


def test_professional_pdf_creates_file(qtbot):
    canvas = PaleoMapCanvas()
    canvas.load_features(SAMPLE["features"], period_name="测试")
    qtbot.addWidget(canvas)
    canvas.resize(400, 300)
    canvas.show()
    qtbot.waitExposed(canvas)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        path = Path(f.name)

    try:
        export_professional_figure(
            canvas, str(path), format="pdf",
            title="测试PDF",
            page_size="A4", orientation="landscape",
        )
        assert path.exists()
        assert path.stat().st_size > 1000
    finally:
        path.unlink(missing_ok=True)


def test_professional_png_creates_file(qtbot):
    from PIL import Image
    canvas = PaleoMapCanvas()
    canvas.load_features(SAMPLE["features"], period_name="测试")
    qtbot.addWidget(canvas)
    canvas.resize(400, 300)
    canvas.show()
    qtbot.waitExposed(canvas)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = Path(f.name)

    try:
        export_professional_figure(
            canvas, str(path), format="png",
            title="测试PNG",
            dpi=150,
        )
        assert path.exists()
        img = Image.open(path)
        assert img.size[0] > 1000  # A4 landscape at 150dpi is wide
    finally:
        path.unlink(missing_ok=True)


def test_grid_frame_uses_west_south_hemisphere_labels(qtbot):
    """#679: western/southern extents must not render as negative °E / °N."""
    west_south = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "南美", "facies": "砂岩"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-70.0, -40.0], [-50.0, -40.0], [-50.0, -20.0],
                                    [-70.0, -20.0], [-70.0, -40.0]]],
                },
            }
        ],
    }
    canvas = PaleoMapCanvas()
    canvas.load_features(west_south["features"], period_name="测试")
    qtbot.addWidget(canvas)
    canvas.resize(400, 300)
    canvas.show()
    qtbot.waitExposed(canvas)

    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
        path = Path(f.name)

    try:
        export_professional_figure(
            canvas, str(path), format="svg",
            title="西经南纬",
            include_grid_frame=True,
        )
        text = ET.tostring(ET.parse(path).getroot(), encoding="unicode")
        assert "60°W" in text
        assert "30°S" in text
        assert "-60°E" not in text
        assert "-30°N" not in text
        assert "°E" not in text
        assert "°N" not in text
    finally:
        path.unlink(missing_ok=True)


def test_professional_svg_has_legend_when_enabled(qtbot):
    canvas = PaleoMapCanvas()
    canvas.load_features(SAMPLE["features"], period_name="测试")
    qtbot.addWidget(canvas)
    canvas.resize(400, 300)
    canvas.show()
    qtbot.waitExposed(canvas)

    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
        path = Path(f.name)

    try:
        export_professional_figure(
            canvas, str(path), format="svg",
            title="测试",
            include_legend=True,
        )
        tree = ET.parse(path)
        root = tree.getroot()
        text = ET.tostring(root, encoding="unicode")
        assert "图例" in text
    finally:
        path.unlink(missing_ok=True)


def test_professional_svg_no_legend_when_disabled(qtbot):
    canvas = PaleoMapCanvas()
    canvas.load_features(SAMPLE["features"], period_name="测试")
    qtbot.addWidget(canvas)
    canvas.resize(400, 300)
    canvas.show()
    qtbot.waitExposed(canvas)

    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
        path = Path(f.name)

    try:
        export_professional_figure(
            canvas, str(path), format="svg",
            title="测试",
            include_legend=False,
        )
        tree = ET.parse(path)
        root = tree.getroot()
        text = ET.tostring(root, encoding="unicode")
        assert "图例" not in text
    finally:
        path.unlink(missing_ok=True)
