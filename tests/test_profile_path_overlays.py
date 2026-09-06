"""R1-B1 regression: path overlays render without annotations.

The well-trace overlay draw call was nested under ``if self._annotations:``
so a fresh section (no manual annotations) never painted the overlay.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("PySide6")

from geoviz_seismic.profile_vd import ProfileVD


def _grab_pixels(widget) -> np.ndarray:
    image = widget.grab().toImage()
    w, h = image.width(), image.height()
    arr = np.zeros((h, w), dtype=np.uint32)
    for y in range(h):
        for x in range(w):
            arr[y, x] = uint(image.pixel(x, y))
    return arr


def uint(color_int: int) -> int:
    return int(color_int) & 0xFFFFFFFF


from geoviz_seismic.models import SliceInfo


@pytest.fixture()
def loaded(qtbot):
    widget = ProfileVD()
    qtbot.addWidget(widget)
    widget.resize(320, 240)
    data = np.zeros((40, 60), dtype=np.float32)  # flat zero-amplitude section
    info = SliceInfo(
        slice_type="inline",
        position=100,
        axis_h_label="XL",
        axis_v_label="TWT (ms)",
        axis_h_values=[float(200 + i) for i in range(60)],
        axis_v_values=[float(4 * i) for i in range(40)],
    )
    widget.render(data, slice_info=info)
    widget.show()
    return widget


def test_path_overlay_renders_without_annotations(loaded):
    before = _grab_pixels(loaded)
    assert loaded._annotations == []  # no annotations on a fresh section

    loaded.set_path_overlays(
        [
            {
                "h_values": [210.0, 230.0, 250.0],
                "v_values": [40.0, 80.0, 120.0],
                "label": "W-1",
                "color": "#FF00FF",
            }
        ]
    )
    after = _grab_pixels(loaded)

    assert not np.array_equal(before, after), (
        "overlay did not change the rendered pixels — the B1 regression "
        "(draw nested under annotations) is back"
    )


def test_clear_path_overlays_restores_bare_section(loaded):
    loaded.set_path_overlays(
        [
            {
                "h_values": [210.0, 250.0],
                "v_values": [40.0, 120.0],
                "color": "#FF00FF",
            }
        ]
    )
    with_overlay = _grab_pixels(loaded)
    loaded.clear_path_overlays()
    cleared = _grab_pixels(loaded)
    assert not np.array_equal(with_overlay, cleared)
