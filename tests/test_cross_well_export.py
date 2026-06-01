import tempfile
from pathlib import Path
import pytest
from geoviz_cross_well.canvas import CrossWellCanvas
# Import the function from public API
from geoviz_cross_well import export_cross_well_report

def test_export_cross_well_pdf_creates_file(qtbot):
    """Verify that export_cross_well_report successfully generates a PDF file."""
    canvas = CrossWellCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.show()
    qtbot.waitExposed(canvas)
    
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        path = Path(f.name)
        
    try:
        export_cross_well_report(
            canvas,
            path,
            format="pdf",
            title="测试连井剖面报告",
            page_size="A4",
            orientation="landscape"
        )
        assert path.exists()
        assert path.stat().st_size > 1000
    finally:
        path.unlink(missing_ok=True)

def test_export_cross_well_svg_creates_file(qtbot):
    """Verify that export_cross_well_report successfully generates an SVG file."""
    canvas = CrossWellCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.show()
    qtbot.waitExposed(canvas)
    
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
        path = Path(f.name)
        
    try:
        export_cross_well_report(
            canvas,
            path,
            format="svg",
            title="测试连井剖面报告 SVG",
            page_size="A4",
            orientation="landscape"
        )
        assert path.exists()
        assert path.stat().st_size > 100
    finally:
        path.unlink(missing_ok=True)

def test_export_cross_well_png_creates_file(qtbot):
    """Verify that export_cross_well_report successfully generates a PNG file."""
    canvas = CrossWellCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.show()
    qtbot.waitExposed(canvas)
    
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = Path(f.name)
        
    try:
        export_cross_well_report(
            canvas,
            path,
            format="png",
            title="测试连井剖面报告 PNG",
            dpi=150
        )
        assert path.exists()
        assert path.stat().st_size > 100
    finally:
        path.unlink(missing_ok=True)
