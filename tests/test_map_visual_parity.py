"""Visual parity test — guards against regression of the canonical render."""
import json
from pathlib import Path

import pytest
from PySide6.QtGui import QImage

from geoviz_map import MapCanvas, ReferenceLabel, WellMarker
from tests.utils.visual_parity import (
    assert_visual_parity,
    load_golden,
    render_widget_to_image,
)


DATA_DIR = Path(__file__).parent.parent / "data"
GOLDEN = Path(__file__).parent / "golden" / "map_canvas_default.png"


@pytest.fixture(scope="module")
def golden_image() -> QImage:
    return load_golden(GOLDEN)


def _build_canvas() -> MapCanvas:
    world = json.loads((DATA_DIR / "world.json").read_text(encoding="utf-8"))
    china = json.loads((DATA_DIR / "china_provinces.json").read_text(encoding="utf-8"))
    coords = json.loads((DATA_DIR / "well_coordinates.json").read_text(encoding="utf-8"))
    wells = [
        WellMarker(
            name=w.get("well_name", w.get("name", "")),
            lng=w["longitude"],
            lat=w["latitude"],
            color="#ef4444",
            has_data=True,
        )
        for w in coords["wells"]
    ]
    labels = [
        ReferenceLabel(name="香港", lng=114.17, lat=22.32, kind="city"),
        ReferenceLabel(name="南海", lng=115.5, lat=20.2, kind="sea"),
    ]
    return MapCanvas(
        wells=wells,
        world_geojson=world,
        china_geojson=china,
        reference_labels=labels,
        initial_center=(115.14, 21.31),
        initial_zoom=8.0,
    )


def test_canonical_render_matches_golden(qtbot, golden_image):
    current = render_widget_to_image(_build_canvas(), 1200, 800, qtbot)
    assert_visual_parity(current, golden_image)
