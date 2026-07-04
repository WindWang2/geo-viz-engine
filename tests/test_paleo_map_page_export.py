"""Smoke tests for PaleoMapPage export delegation (11.6-C).

Verify the page's _export_pdf/_export_svg/_export_png methods now go through
export_professional_figure (publishing-grade frame) instead of the old
grab+center pipeline that produced a frameless page.
"""
import os
import pytest

pytest.importorskip("PySide6.QtPrintSupport")

from src.pages.paleo_map.page import PaleoMapPage


SAMPLE_FEATURES = [
    {
        "type": "Feature",
        "properties": {"name": "测试相区", "facies": "砂岩"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [110.0, 20.0], [120.0, 20.0], [120.0, 30.0],
                [110.0, 30.0], [110.0, 20.0]
            ]],
        },
    }
]


def _make_page(qtbot):
    page = PaleoMapPage()
    qtbot.addWidget(page)
    page._periods = {"K1": SAMPLE_FEATURES}
    page._current_period = "K1"
    page.map_view.load_features(SAMPLE_FEATURES, period_name="K1")
    page.resize(800, 600)
    page.show()
    qtbot.waitExposed(page)
    return page


def test_export_pdf_uses_professional_figure(qtbot, tmp_path, monkeypatch):
    """_export_pdf must call export_professional_figure with title."""
    page = _make_page(qtbot)
    out_pdf = tmp_path / "out.pdf"
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *a, **kw: (str(out_pdf), "PDF (*.pdf)"),
    )

    captured = {}
    import geoviz_paleo_map.export_professional as ep

    def fake_export(canvas, path, fmt, *, title, **kw):
        captured["canvas"] = canvas
        captured["path"] = str(path)
        captured["fmt"] = fmt
        captured["title"] = title
        # Touch file so the assertion downstream can see it
        with open(path, "wb") as f:
            f.write(b"%PDF-1.4 test")

    monkeypatch.setattr(ep, "export_professional_figure", fake_export)
    # Also patch in page module where it's imported at call time
    import src.pages.paleo_map.page as page_mod
    monkeypatch.setattr(
        "geoviz_paleo_map.export_professional.export_professional_figure",
        fake_export,
    )

    page._export_pdf()
    assert captured.get("fmt") == "pdf"
    assert "K1" in captured.get("title", "")
    assert captured.get("path") == str(out_pdf)


def test_export_png_uses_professional_figure(qtbot, tmp_path, monkeypatch):
    page = _make_page(qtbot)
    out_png = tmp_path / "out.png"
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *a, **kw: (str(out_png), "PNG (*.png)"),
    )

    captured = {}

    def fake_export(canvas, path, fmt, *, title, **kw):
        captured["fmt"] = fmt
        captured["title"] = title
        with open(path, "wb") as f:
            f.write(b"\x89PNG\r\n")

    monkeypatch.setattr(
        "geoviz_paleo_map.export_professional.export_professional_figure",
        fake_export,
    )

    page._export_png()
    assert captured.get("fmt") == "png"
    assert "K1" in captured.get("title", "")


def test_export_svg_uses_professional_figure(qtbot, tmp_path, monkeypatch):
    page = _make_page(qtbot)
    out_svg = tmp_path / "out.svg"
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *a, **kw: (str(out_svg), "SVG (*.svg)"),
    )

    captured = {}

    def fake_export(canvas, path, fmt, *, title, **kw):
        captured["fmt"] = fmt
        captured["title"] = title
        with open(path, "w") as f:
            f.write("<svg/>")

    monkeypatch.setattr(
        "geoviz_paleo_map.export_professional.export_professional_figure",
        fake_export,
    )

    page._export_svg()
    assert captured.get("fmt") == "svg"
    assert "K1" in captured.get("title", "")


def test_figure_title_falls_back_when_no_period(qtbot):
    page = _make_page(qtbot)
    page._current_period = ""
    title = page._figure_title()
    assert "古地理" in title


def test_figure_title_reflects_active_facies_level(qtbot):
    """Title must use the level actually rendered (相/亚相/微相), from _resolve_level."""
    page = _make_page(qtbot)
    page._current_period = "K1"

    page.map_view._resolve_level = lambda: "micro_facies"
    assert page._figure_title() == "K1 古地理微相图"

    page.map_view._resolve_level = lambda: "sub_facies"
    assert page._figure_title() == "K1 古地理亚相图"

    page.map_view._resolve_level = lambda: "facies"
    assert page._figure_title() == "K1 古地理相图"


def test_figure_title_defaults_to_facies_word(qtbot):
    """Unknown/empty level falls back to the generic 相 wording."""
    page = _make_page(qtbot)
    page._current_period = "K1"
    page.map_view._resolve_level = lambda: ""
    assert page._figure_title() == "K1 古地理相图"


def test_export_pdf_real_run_produces_nonempty_file(qtbot, tmp_path, monkeypatch):
    """End-to-end: actual export_professional_figure run produces a real PDF."""
    page = _make_page(qtbot)
    out_pdf = tmp_path / "real.pdf"
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *a, **kw: (str(out_pdf), "PDF (*.pdf)"),
    )
    page._export_pdf()
    assert out_pdf.exists()
    assert out_pdf.stat().st_size > 1000, "PDF should be non-trivial size"


def test_do_export_threads_page_options(qtbot, tmp_path, monkeypatch):
    """_do_export must forward page_size/orientation/dpi to the figure builder."""
    page = _make_page(qtbot)
    out = tmp_path / "out.pdf"
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *a, **kw: (str(out), "PDF (*.pdf)"),
    )
    captured = {}

    def fake_export(canvas, path, fmt, *, title, page_size="A4",
                    orientation="landscape", dpi=300, **kw):
        captured.update(fmt=fmt, page_size=page_size,
                        orientation=orientation, dpi=dpi)

    monkeypatch.setattr(
        "geoviz_paleo_map.export_professional.export_professional_figure",
        fake_export,
    )
    page._do_export("pdf", page_size="A3", orientation="portrait", dpi=600)
    assert captured == {"fmt": "pdf", "page_size": "A3",
                        "orientation": "portrait", "dpi": 600}


def test_do_export_defaults_when_called_directly(qtbot, tmp_path, monkeypatch):
    """_export_pdf() (no args) still exports with A4/landscape/300 defaults."""
    page = _make_page(qtbot)
    out = tmp_path / "out.pdf"
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *a, **kw: (str(out), "PDF (*.pdf)"),
    )
    captured = {}

    def fake_export(canvas, path, fmt, *, title, page_size="A4",
                    orientation="landscape", dpi=300, **kw):
        captured.update(fmt=fmt, page_size=page_size,
                        orientation=orientation, dpi=dpi)

    monkeypatch.setattr(
        "geoviz_paleo_map.export_professional.export_professional_figure",
        fake_export,
    )
    page._export_pdf()
    assert captured == {"fmt": "pdf", "page_size": "A4",
                        "orientation": "landscape", "dpi": 300}
