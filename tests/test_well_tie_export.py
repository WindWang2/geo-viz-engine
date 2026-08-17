"""Unit tests for WellTieReportExporter PDF and SVG exports."""
import os

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


def test_export_well_tie_svg_uses_real_metrics_and_nonzero_size(tmp_path):
    """#675: report must render caller-supplied QA text; SVG page size is non-zero."""
    svg_path = tmp_path / "well_tie_report.svg"
    export_well_tie_pdf(
        str(svg_path),
        well_name="TESTWELL",
        block="BLOCK-A",
        wavelet="Ricker (25Hz)",
        r_score=0.731,
        lag_ms=12.5,
    )
    content = svg_path.read_text(encoding="utf-8", errors="replace")
    assert "TESTWELL" in content
    assert "0.731" in content
    assert "12.5" in content
    assert "Ricker (25Hz)" in content
    assert "W101" not in content
    assert "0.925" not in content
    assert 'width="0' not in content
    assert svg_path.stat().st_size > 500
