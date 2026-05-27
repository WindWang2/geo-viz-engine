"""Visual parity test — guards against regression of the canonical render."""
import json
from pathlib import Path

import pytest
from PySide6.QtGui import QImage

from geoviz_map import MapCanvas, ReferenceLabel, WellMarker


DATA_DIR = Path(__file__).parent.parent / "data"
GOLDEN = Path(__file__).parent / "golden" / "map_canvas_default.png"


@pytest.fixture(scope="module")
def golden_image() -> QImage:
    img = QImage(str(GOLDEN))
    assert not img.isNull(), f"golden image missing: {GOLDEN}"
    return img.convertToFormat(QImage.Format.Format_ARGB32)


def _render_canonical(qtbot) -> QImage:
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
    c = MapCanvas(
        wells=wells,
        world_geojson=world,
        china_geojson=china,
        reference_labels=labels,
        initial_center=(115.14, 21.31),
        initial_zoom=8.0,
    )
    qtbot.addWidget(c)
    c.resize(1200, 800)
    c.show()
    qtbot.waitExposed(c)
    return c.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32)


def _pixel_diff_ratio(a: QImage, b: QImage, threshold: int = 30) -> float:
    assert a.size() == b.size()
    w, h = a.width(), a.height()
    differing = 0
    total = 0
    step = 4  # sample 1/16th of pixels for speed
    for y in range(0, h, step):
        for x in range(0, w, step):
            ca = a.pixelColor(x, y)
            cb = b.pixelColor(x, y)
            total += 1
            if (abs(ca.red() - cb.red())
                    + abs(ca.green() - cb.green())
                    + abs(ca.blue() - cb.blue())) > threshold:
                differing += 1
    return differing / max(total, 1)


def test_canonical_render_matches_golden(qtbot, golden_image):
    current = _render_canonical(qtbot)
    ratio = _pixel_diff_ratio(current, golden_image)
    assert ratio < 0.01, f"visual parity diff {ratio*100:.2f}% exceeds 1%"
