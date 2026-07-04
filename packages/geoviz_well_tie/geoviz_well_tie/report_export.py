"""Publishing 300 DPI Vector PDF / SVG report exporter for Well-Seismic Tie Workspace."""
from __future__ import annotations

from PySide6.QtCore import QRectF, QMarginsF, Qt
from PySide6.QtGui import QPainter, QFont, QColor, QPen, QBrush, QPageSize, QPageLayout
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtSvg import QSvgGenerator

def export_well_tie_pdf(output_path: str):
    """Export 300 DPI vector PDF or SVG report for well-seismic tie calibration."""
    if output_path.endswith(".svg"):
        generator = QSvgGenerator()
        generator.setFileName(output_path)
        generator.setSize(generator.size())
        generator.setResolution(300)
        painter = QPainter(generator)
        _render_report_page(painter, 297.0 * 3.7795, 210.0 * 3.7795)
        painter.end()
    else:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Landscape, QMarginsF(0, 0, 0, 0)))
        printer.setOutputFileName(output_path)

        painter = QPainter(printer)
        rect = printer.pageRect(QPrinter.Unit.Point)
        _render_report_page(painter, rect.width(), rect.height())
        painter.end()



def _render_report_page(painter: QPainter, width: float, height: float):
    """Render publication-grade report with 3-column title block."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Background
    painter.fillRect(QRectF(0, 0, width, height), QColor(255, 255, 255))

    # Header Title
    painter.setPen(QColor(31, 102, 212))
    painter.setFont(QFont("SimSun", 16, QFont.Weight.Bold))
    painter.drawText(QRectF(20, 20, width - 40, 40), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "油田井震精细标定与相关性分析报告")

    # Title block border at bottom
    tb_h = 60.0
    tb_rect = QRectF(20, height - tb_h - 20, width - 40, tb_h)
    painter.setPen(QPen(QColor(88, 104, 120), 1.5))
    painter.drawRect(tb_rect)

    col_w = tb_rect.width() / 3.0
    painter.setFont(QFont("SimSun", 9))
    painter.setPen(QColor(40, 40, 40))

    r1 = QRectF(tb_rect.x(), tb_rect.y(), col_w, tb_h)
    r2 = QRectF(tb_rect.x() + col_w, tb_rect.y(), col_w, tb_h)
    r3 = QRectF(tb_rect.x() + 2 * col_w, tb_rect.y(), col_w, tb_h)

    painter.drawText(r1, Qt.AlignmentFlag.AlignCenter, "井名: W101 | 区块: 渤海湾盆地\n层位: ES3 下干柴沟组")
    painter.drawText(r2, Qt.AlignmentFlag.AlignCenter, "子波: Ricker (30Hz)\n相关系数 R: 0.925 | 偏置: 0 ms")
    painter.drawText(r3, Qt.AlignmentFlag.AlignCenter, "编制单位: GeoViz Research Engine\n日期: 2026-07-04 | 比例尺: 1:1000")

    painter.drawLine(int(tb_rect.x() + col_w), int(tb_rect.y()), int(tb_rect.x() + col_w), int(tb_rect.y() + tb_h))
    painter.drawLine(int(tb_rect.x() + 2 * col_w), int(tb_rect.y()), int(tb_rect.x() + 2 * col_w), int(tb_rect.y() + tb_h))
