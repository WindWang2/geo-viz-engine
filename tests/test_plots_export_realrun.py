"""Regression: plots PDF/SVG export must produce a real, non-empty file.

Root cause guarded here: legacy unscoped Qt5 enums (``QPrinter.A4``,
``QPrinter.Landscape``) and the wrong method name (``setOutputFile``) raised
``AttributeError`` inside the Qt slot. Qt swallows slot exceptions, so the
file was silently never written and no success dialog appeared
("导出的文件没有实际生成"). These tests fail without the modern-API fix.
"""
import pytest

pytest.importorskip("PySide6.QtPrintSupport")

from unittest import mock

from geoviz_plots.surface.surface_widget import SurfaceWidget
from geoviz_plots.chart.plot_widget import PlotWidget
from src.pages.plots.page import PlotsPage


def test_surface_widget_export_pdf_writes_file(qtbot, tmp_path):
    w = SurfaceWidget()
    qtbot.addWidget(w)
    w.resize(400, 300)
    out = tmp_path / "surface.pdf"
    w.export_pdf(str(out))
    assert out.exists()
    assert out.stat().st_size > 500, "PDF should be non-trivial size"


def test_plot_widget_export_pdf_writes_file(qtbot, tmp_path):
    w = PlotWidget()
    qtbot.addWidget(w)
    w.resize(400, 300)
    out = tmp_path / "plot.pdf"
    w.export_pdf(str(out))
    assert out.exists()
    assert out.stat().st_size > 500, "PDF should be non-trivial size"


def test_plots_page_export_pdf_writes_file(qtbot, tmp_path):
    page = PlotsPage()
    qtbot.addWidget(page)
    page.resize(800, 600)
    out = tmp_path / "contour.pdf"
    with mock.patch(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        return_value=(str(out), "PDF (*.pdf)"),
    ), mock.patch("PySide6.QtWidgets.QMessageBox.information"):
        page._export_pdf()
    assert out.exists()
    assert out.stat().st_size > 500, "PDF should be non-trivial size"


def test_plots_page_export_svg_writes_file(qtbot, tmp_path):
    page = PlotsPage()
    qtbot.addWidget(page)
    page.resize(800, 600)
    out = tmp_path / "contour.svg"
    with mock.patch(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        return_value=(str(out), "SVG (*.svg)"),
    ), mock.patch("PySide6.QtWidgets.QMessageBox.information"):
        page._export_svg()
    assert out.exists()
    assert out.stat().st_size > 100, "SVG should be non-trivial size"
