from __future__ import annotations

from PySide6.QtCore import QSizeF, QMarginsF
from PySide6.QtGui import QPageSize, QPageLayout
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtGui import QPainter

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .renderer.canvas import WellLogCanvas


def export_svg(canvas: WellLogCanvas, path: str):
    """Export to SVG -- fully vector, identical to display."""
    generator = QSvgGenerator()
    generator.setFileName(path)
    generator.setSize(canvas.size())
    generator.setViewBox(canvas.rect())
    painter = QPainter(generator)
    canvas.paint_all(painter)
    painter.end()


def export_pdf(canvas: WellLogCanvas, path: str):
    """Export to PDF -- fully vector, identical to display."""
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFileName(path)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    # Page size matches canvas aspect ratio
    size_mm = QSizeF(canvas.width() * 0.264583, canvas.height() * 0.264583)
    printer.setPageSize(QPageSize(size_mm, QPageSize.Unit.Millimeter))
    printer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)
    painter = QPainter(printer)
    painter.setWindow(canvas.rect())
    canvas.paint_all(painter)
    painter.end()


def export_png(canvas: WellLogCanvas, path: str):
    """Export to PNG -- raster screenshot of display."""
    pixmap = canvas.grab()
    pixmap.save(path, "PNG")
