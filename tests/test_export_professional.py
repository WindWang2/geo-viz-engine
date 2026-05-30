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
