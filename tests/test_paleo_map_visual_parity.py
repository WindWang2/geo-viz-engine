"""Visual parity test — guards against regression of the canonical paleo render."""
import json
from pathlib import Path

import pytest
from PySide6.QtGui import QImage

from geoviz_paleo_map import PaleoMapCanvas
from tests.utils.visual_parity import (
    assert_visual_parity, load_golden, render_widget_to_image,
)


REPO = Path(__file__).parent.parent
SAMPLE = REPO / "samples" / "sample_paleo.geojson"
WELLS = REPO / "data" / "well_coordinates.json"
GOLDEN = Path(__file__).parent / "golden" / "paleo_map_default.png"


@pytest.fixture(scope="module")
def golden_image() -> QImage:
    return load_golden(GOLDEN)


def _build_canvas() -> PaleoMapCanvas:
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    wells_data = json.loads(WELLS.read_text(encoding="utf-8"))
    wells = [
        {"name": w["well_name"], "lng": w["longitude"], "lat": w["latitude"]}
        for w in wells_data["wells"]
    ]
    c = PaleoMapCanvas()
    c.load_features(sample["features"], period_name="测试", wells=wells)
    c._viewport.center_world = (115.0, 31.5)
    c._viewport.zoom = 4.0
    return c


def test_canonical_paleo_render_matches_golden(qtbot, golden_image):
    current = render_widget_to_image(_build_canvas(), 1200, 800, qtbot)
    assert_visual_parity(current, golden_image, max_diff=0.01)
