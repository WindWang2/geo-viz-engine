import os
import tempfile

from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_well_log.renderer.depth_track import DepthTrack
from geoviz_well_log.renderer.curve_track import CurveTrack
from geoviz_well_log.models import CurveData
from geoviz_well_log.export_qpainter import export_svg, export_pdf, export_png


def _make_canvas():
    canvas = WellLogCanvas()
    canvas.resize(210, 500)
    canvas.add_track(DepthTrack(top_depth=0, bottom_depth=100))
    curve = CurveData(name="GR", depth=list(range(100)), values=[50.0] * 100,
                      display_range=(0, 150), color="#00ff00")
    canvas.add_track(CurveTrack(curves=[curve], label="GR", width=150))
    canvas.set_depth_range(0, 100)
    return canvas


def test_export_svg_creates_file(qtbot):
    canvas = _make_canvas()
    qtbot.addWidget(canvas)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test.svg")
        export_svg(canvas, path)
        assert os.path.exists(path)
        content = open(path).read()
        assert "<svg" in content.lower() or "svg" in content.lower()
        assert os.path.getsize(path) > 100


def test_export_pdf_creates_file(qtbot):
    canvas = _make_canvas()
    qtbot.addWidget(canvas)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test.pdf")
        export_pdf(canvas, path)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 100


def test_export_png_creates_file(qtbot):
    canvas = _make_canvas()
    qtbot.addWidget(canvas)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test.png")
        export_png(canvas, path)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 100


def test_export_png_omits_hover_crosshair(qtbot, tmp_path):
    """#725: PNG export must paint_all, not grab() the hover overlay."""
    from PySide6.QtGui import QColor, QImage, QPixmap

    canvas = _make_canvas()
    qtbot.addWidget(canvas)
    canvas.crosshair.set_cursor_pos(80.0, 250.0)

    # Inject a red grab() so any screenshot path is visible in the file.
    stained = QPixmap(canvas.size())
    stained.fill(QColor("#ef4444"))
    canvas.grab = lambda *a, **k: stained

    path = tmp_path / "hover.png"
    export_png(canvas, str(path))
    img = QImage(str(path))
    assert not img.isNull()
    cursor = QColor("#ef4444")
    for y in range(img.height()):
        for x in range(img.width()):
            c = QColor(img.pixel(x, y))
            if (
                abs(c.red() - cursor.red()) <= 8
                and abs(c.green() - cursor.green()) <= 8
                and abs(c.blue() - cursor.blue()) <= 8
            ):
                raise AssertionError("exported PNG used grab() hover pixels")
