"""Publishing 300 DPI Vector PDF / SVG report exporter for Well-Seismic Tie Workspace."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QRectF, QMarginsF, QSize, Qt
from PySide6.QtGui import QPainter, QFont, QColor, QPen, QPageSize, QPageLayout
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtSvg import QSvgGenerator


def _dash(value) -> str:
    if value is None or value == "":
        return "—"
    return str(value)


def export_well_tie_pdf(
    output_path: str,
    *,
    well_name: str | None = None,
    block: str | None = None,
    horizon: str | None = None,
    wavelet: str | None = None,
    r_score: float | None = None,
    lag_ms: float | None = None,
    org: str | None = None,
    date_str: str | None = None,
):
    """Export 300 DPI vector PDF or SVG report for well-seismic tie calibration."""
    page_w_mm, page_h_mm = 297.0, 210.0
    if output_path.endswith(".svg"):
        generator = QSvgGenerator()
        generator.setFileName(output_path)
        generator.setResolution(300)
        width_px = int(round(page_w_mm / 25.4 * 300.0))
        height_px = int(round(page_h_mm / 25.4 * 300.0))
        generator.setSize(QSize(width_px, height_px))
        generator.setViewBox(QRectF(0, 0, width_px, height_px))
        painter = QPainter(generator)
        _render_report_page(
            painter,
            float(width_px),
            float(height_px),
            well_name=well_name,
            block=block,
            horizon=horizon,
            wavelet=wavelet,
            r_score=r_score,
            lag_ms=lag_ms,
            org=org,
            date_str=date_str,
        )
        painter.end()
    else:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Landscape, QMarginsF(0, 0, 0, 0)))
        printer.setOutputFileName(output_path)

        painter = QPainter(printer)
        rect = printer.pageRect(QPrinter.Unit.Point)
        _render_report_page(
            painter,
            rect.width(),
            rect.height(),
            well_name=well_name,
            block=block,
            horizon=horizon,
            wavelet=wavelet,
            r_score=r_score,
            lag_ms=lag_ms,
            org=org,
            date_str=date_str,
        )
        painter.end()


def _render_report_page(
    painter: QPainter,
    width: float,
    height: float,
    *,
    well_name: str | None = None,
    block: str | None = None,
    horizon: str | None = None,
    wavelet: str | None = None,
    r_score: float | None = None,
    lag_ms: float | None = None,
    org: str | None = None,
    date_str: str | None = None,
):
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

    r_text = f"{r_score:.3f}" if r_score is not None else "—"
    lag_text = f"{lag_ms:.1f} ms" if lag_ms is not None else "—"
    when = date_str or date.today().isoformat()

    painter.drawText(
        r1,
        Qt.AlignmentFlag.AlignCenter,
        f"井名: {_dash(well_name)} | 区块: {_dash(block)}\n层位: {_dash(horizon)}",
    )
    painter.drawText(
        r2,
        Qt.AlignmentFlag.AlignCenter,
        f"子波: {_dash(wavelet)}\n相关系数 R: {r_text} | 偏置: {lag_text}",
    )
    painter.drawText(
        r3,
        Qt.AlignmentFlag.AlignCenter,
        f"编制单位: {_dash(org) if org else 'GeoViz Research Engine'}\n日期: {when} | 比例尺: —",
    )

    painter.drawLine(int(tb_rect.x() + col_w), int(tb_rect.y()), int(tb_rect.x() + col_w), int(tb_rect.y() + tb_h))
    painter.drawLine(int(tb_rect.x() + 2 * col_w), int(tb_rect.y()), int(tb_rect.x() + 2 * col_w), int(tb_rect.y() + tb_h))
