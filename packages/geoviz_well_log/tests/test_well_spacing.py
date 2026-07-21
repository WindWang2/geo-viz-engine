"""CrossWellWidget.set_well_spacing / set_track_visible_by_label tests."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_canvas():
    from geoviz_well_log.models import CurveData
    from geoviz_well_log.renderer.canvas import WellLogCanvas
    from geoviz_well_log.renderer.curve_track import CurveTrack

    curve = CurveData(
        name="GR", unit="API",
        depth=[float(i) for i in range(10)],
        values=[float(i) for i in range(10)],
        display_range=(0.0, 10.0),
    )
    canvas = WellLogCanvas()
    canvas.add_track(CurveTrack([curve], label="GR"))
    return canvas


def _make_widget(n: int = 2):
    from geoviz_well_log.cross_well_widget import CrossWellWidget

    widget = CrossWellWidget()
    for i in range(n):
        widget.add_canvas(_make_canvas(), f"W{i + 1}")
    return widget


def test_default_spacing_is_150(qapp):
    widget = _make_widget()
    assert widget._container_layout.spacing() == 150


def test_set_well_spacing_updates_layout_and_minimum_width(qapp):
    widget = _make_widget()
    widget.set_well_spacing(80)
    assert widget._container_layout.spacing() == 80
    margins = widget._container_layout.contentsMargins()
    expected = (
        margins.left() + margins.right()
        + sum(c.minimumWidth() for c in widget._canvases)
        + 80 * (len(widget._canvases) - 1)
    )
    assert widget.minimumWidth() == expected


def test_export_png_uses_current_spacing(qapp, tmp_path):
    widget = _make_widget()
    widget.resize(800, 600)
    for c in widget._canvases:
        c.resize(200, 600)
    widget.set_well_spacing(50)
    out = tmp_path / "x.png"
    widget.export_composite(str(out), fmt="png")
    from PySide6.QtGui import QImage

    img = QImage(str(out))
    expected_w = sum(c.width() for c in widget._canvases) + 50 * (len(widget._canvases) - 1)
    assert img.width() == expected_w


def test_set_track_visible_by_label(qapp):
    widget = _make_widget()
    widget.set_track_visible_by_label("GR", False)
    for canvas in widget._canvases:
        assert canvas.tracks[0]._visible is False
    widget.set_track_visible_by_label("GR", True)
    for canvas in widget._canvases:
        assert canvas.tracks[0]._visible is True


def test_set_manual_link_is_idempotent(qapp):
    widget = _make_widget()
    widget.set_manual_link(True)
    assert widget._manual_link_active is True
    widget.set_manual_link(True)
    assert widget._manual_link_active is True
    widget._manual_link_picks.append(("W1", None))
    widget.set_manual_link(False)
    assert widget._manual_link_active is False
    assert widget._manual_link_picks == []


def test_clear_all_resets_manual_link_state(qapp):
    widget = _make_widget()
    widget.set_manual_link(True)
    widget._manual_link_picks.append(("W1", None))
    widget.clear_all()
    assert widget._manual_link_active is False
    assert widget._manual_link_picks == []


def test_track_labels_union_in_order(qapp):
    widget = _make_widget()
    assert widget.track_labels() == ["GR"]
