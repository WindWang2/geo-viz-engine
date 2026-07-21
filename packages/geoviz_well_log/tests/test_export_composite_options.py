"""CrossWellWidget.export_composite optional-parameter tests."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_widget():
    from geoviz_well_log.cross_well_widget import CrossWellWidget
    from geoviz_well_log.models import CurveData
    from geoviz_well_log.renderer.canvas import WellLogCanvas
    from geoviz_well_log.renderer.curve_track import CurveTrack

    widget = CrossWellWidget()
    for i in range(2):
        curve = CurveData(
            name="GR", unit="API",
            depth=[float(d) for d in range(10)],
            values=[float(v) for v in range(10)],
            display_range=(0.0, 10.0),
        )
        canvas = WellLogCanvas()
        canvas.add_track(CurveTrack([curve], label="GR"))
        canvas.resize(200, 600)
        widget.add_canvas(canvas, f"W{i + 1}")
    widget.resize(800, 600)
    return widget


def test_default_png_unchanged(qapp, tmp_path):
    widget = _make_widget()
    out = tmp_path / "default.png"
    widget.export_composite(str(out), fmt="png")
    from PySide6.QtGui import QImage

    img = QImage(str(out))
    natural_w = sum(c.width() for c in widget._canvases) + 150 * (len(widget._canvases) - 1)
    assert img.width() == natural_w
    assert img.height() == 600


def test_width_px_scales_output(qapp, tmp_path):
    widget = _make_widget()
    out = tmp_path / "wide.png"
    widget.export_composite(str(out), fmt="png", width_px=1100)
    from PySide6.QtGui import QImage

    img = QImage(str(out))
    assert img.width() == 1100
    natural_w = sum(c.width() for c in widget._canvases) + 150
    assert img.height() == round(600 * 1100 / natural_w)


def test_png_dpi_metadata(qapp, tmp_path):
    widget = _make_widget()
    out = tmp_path / "dpi.png"
    widget.export_composite(str(out), fmt="png", dpi=300)
    from PySide6.QtGui import QImage

    img = QImage(str(out))
    assert img.dotsPerMeterX() == int(300 / 0.0254)
    assert img.dotsPerMeterY() == int(300 / 0.0254)


def test_pdf_content_sized_and_a4(qapp, tmp_path):
    widget = _make_widget()
    out1 = tmp_path / "content.pdf"
    widget.export_composite(str(out1), fmt="pdf", dpi=150)
    assert out1.exists() and out1.stat().st_size > 500
    out2 = tmp_path / "a4.pdf"
    widget.export_composite(str(out2), fmt="pdf", page_size="A4")
    assert out2.exists() and out2.stat().st_size > 500


def test_svg_width_px_changes_viewbox(qapp, tmp_path):
    widget = _make_widget()
    out = tmp_path / "scaled.svg"
    widget.export_composite(str(out), fmt="svg", width_px=1000)
    text = out.read_text(encoding="utf-8")
    assert 'viewBox="0 0 1000 ' in text


def test_positional_call_still_works(qapp, tmp_path):
    """export_service compatibility: positional (path, fmt) call."""
    widget = _make_widget()
    out = tmp_path / "pos.svg"
    widget.export_composite(str(out), "svg")
    assert out.exists()
