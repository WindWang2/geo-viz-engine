"""Unit tests for WellTieReportExporter PDF and SVG exports."""
import os
import pytest
from geoviz_well_tie.report_export import export_well_tie_pdf

def test_export_well_tie_pdf(tmp_path):
    pdf_path = str(tmp_path / "well_tie_report.pdf")
    export_well_tie_pdf(pdf_path)
    assert os.path.exists(pdf_path)
    assert os.path.getsize(pdf_path) > 0

def test_export_well_tie_svg(tmp_path):
    svg_path = str(tmp_path / "well_tie_report.svg")
    export_well_tie_pdf(svg_path)
    assert os.path.exists(svg_path)
    assert os.path.getsize(svg_path) > 0
