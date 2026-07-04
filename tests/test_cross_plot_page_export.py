"""Integration tests for CrossPlotWidget integration in PlotsPage and 300 DPI vector PDF export."""
import os
import pytest
from src.pages.plots.page import PlotsPage

@pytest.fixture
def plots_page(qtbot):
    page = PlotsPage()
    qtbot.addWidget(page)
    page.resize(1000, 700)
    page.show()
    return page

def test_plots_page_tab_integration(plots_page):
    assert plots_page._cross_plot_widget is not None
    assert plots_page._tab_widget.count() >= 2


def test_cross_plot_export_pdf(plots_page, tmp_path):
    pdf_path = str(tmp_path / "cross_plot_report.pdf")
    plots_page.export_cross_plot_pdf(pdf_path)
    assert os.path.exists(pdf_path)
    assert os.path.getsize(pdf_path) > 0
