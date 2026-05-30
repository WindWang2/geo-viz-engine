import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from PySide6.QtCore import QRectF

from geoviz_paleo_map import PaleoMapCanvas
from geoviz_paleo_map.save_export import export_vector_svg


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


def test_export_vector_svg_creates_file_with_path_elements(qtbot):
    canvas = PaleoMapCanvas()
    canvas.load_features(SAMPLE["features"], period_name="测试")
    qtbot.addWidget(canvas)
    canvas.resize(400, 300)
    canvas.show()
    qtbot.waitExposed(canvas)

    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
        path = Path(f.name)

    try:
        export_vector_svg(canvas, str(path), QRectF(0, 0, 400, 300))
        assert path.exists()
        assert path.stat().st_size > 100

        # Parse and verify it contains at least one <path> element
        tree = ET.parse(path)
        root = tree.getroot()
        ns = {"svg": "http://www.w3.org/2000/svg"}
        paths = root.findall(".//svg:path", ns)
        assert len(paths) > 0, "SVG should contain <path> elements"
    finally:
        path.unlink(missing_ok=True)
