"""Task 22a.1 — PlotsPage SVG/PDF export missing imports (TDD)."""
import pytest


def test_qsvggenerator_importable_in_page_module():
    """After fix, QSvgGenerator must be importable in the page module namespace."""
    import src.pages.plots.page as ppm
    assert hasattr(ppm, "QSvgGenerator"), (
        "QSvgGenerator must be imported in page.py for _export_svg"
    )


def test_qpainter_importable_in_page_module():
    """After fix, QPainter must be importable in the page module namespace."""
    import src.pages.plots.page as ppm
    assert hasattr(ppm, "QPainter"), (
        "QPainter must be imported in page.py for _export_svg and _export_pdf"
    )


def test_svg_export_method_exists(qtbot):
    """_export_svg method should exist and be callable."""
    from src.pages.plots.page import PlotsPage
    page = PlotsPage()
    qtbot.addWidget(page)
    assert hasattr(page, "_export_svg")
    assert callable(page._export_svg)


def test_pdf_export_method_exists(qtbot):
    """_export_pdf method should exist and be callable."""
    from src.pages.plots.page import PlotsPage
    page = PlotsPage()
    qtbot.addWidget(page)
    assert hasattr(page, "_export_pdf")
    assert callable(page._export_pdf)
