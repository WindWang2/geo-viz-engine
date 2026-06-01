"""Professional report PDF/SVG/PNG export module for cross-well correlation panels."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Literal, Any

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QPoint
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPageLayout
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtPrintSupport import QPrinter

_PAGE_SIZES_MM = {
    "A4": (297, 210),
    "A3": (420, 297),
    "A2": (594, 420),
}


def _page_size_mm(page_size: str, orientation: str) -> tuple[int, int]:
    w, h = _PAGE_SIZES_MM.get(page_size, (297, 210))
    if orientation == "portrait":
        return h, w
    return w, h


def _dpi_to_mm(dpi: int) -> float:
    return 25.4 / dpi


def export_cross_well_report(
    canvas: Any,
    file_path: str | Path,
    format: Literal["svg", "pdf", "png"],
    *,
    title: str,
    page_size: Literal["A4", "A3", "A2"] = "A4",
    orientation: Literal["portrait", "landscape"] = "landscape",
    dpi: int = 300,
    include_legend: bool = True,
    include_grid_frame: bool = True,
) -> None:
    """Export a professional publishing-grade cross-well correlation report.
    
    Args:
        canvas: CrossWellCanvas to export.
        file_path: Output file path.
        format: "svg", "pdf", or "png".
        title: Figure title (rendered in title block).
        page_size: Page size for PDF/print output.
        orientation: "portrait" or "landscape".
        dpi: Resolution for raster and PDF output.
        include_legend: Render formation tops legend panel.
        include_grid_frame: Render coordinate grid frame around content.
    """
    file_path = Path(file_path)
    page_w_mm, page_h_mm = _page_size_mm(page_size, orientation)
    mm_per_px = _dpi_to_mm(dpi)
    page_w = int(page_w_mm / mm_per_px)
    page_h = int(page_h_mm / mm_per_px)

    if format == "svg":
        device = QSvgGenerator()
        device.setFileName(str(file_path))
        device.setSize(QSize(page_w, page_h))
        device.setViewBox(QRectF(0, 0, page_w, page_h))
    elif format == "pdf":
        device = QPrinter(QPrinter.PrinterMode.HighResolution)
        device.setOutputFileName(str(file_path))
        device.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        device.setResolution(dpi)
        from PySide6.QtGui import QPageSize as _QPageSize
        device.setPageSize(_QPageSize(
            getattr(_QPageSize.PageSizeId, page_size)
        ))
        if orientation == "landscape":
            device.setPageOrientation(QPageLayout.Orientation.Landscape)
        else:
            device.setPageOrientation(QPageLayout.Orientation.Portrait)
    else:  # png
        from PySide6.QtGui import QPixmap
        device = QPixmap(page_w, page_h)
        device.fill(Qt.GlobalColor.white)

    painter = QPainter(device)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # Page background
    painter.fillRect(QRectF(0, 0, page_w, page_h), QColor("#ffffff"))

    # Margins (15mm)
    margin = int(15 / mm_per_px)
    
    # Title Block (height: 12mm)
    title_h = int(12 / mm_per_px)
    
    # Legend Block (height: 15mm if included)
    legend_h = int(15 / mm_per_px) if include_legend else 0

    # Content Area Rect
    content_x = margin
    content_y = margin + title_h
    content_w = page_w - margin * 2
    content_h = page_h - margin * 2 - title_h - legend_h
    content_rect = QRectF(content_x, content_y, content_w, content_h)

    # Cache original canvas size/state
    old_size = canvas.size()
    
    # Temporarily resize widgets to fit content area at target DPI
    canvas.resize(content_w, content_h)
    canvas.widget.resize(content_w, content_h)
    canvas._overlay.resize(content_w, content_h)
    canvas.widget.updateGeometry()
    canvas._overlay.updateGeometry()

    try:
        # --- Render Cross-Well Content ---
        painter.save()
        painter.setClipRect(content_rect)
        painter.translate(content_x, content_y)
        
        # Render main well-logs and picking lines overlay
        canvas.widget.render(painter, QPoint(0, 0))
        canvas._overlay.render(painter, QPoint(0, 0))
        
        painter.restore()
    finally:
        # Restore original canvas size
        canvas.resize(old_size)
        canvas.widget.resize(old_size)
        canvas._overlay.resize(old_size)
        canvas.widget.updateGeometry()
        canvas._overlay.updateGeometry()

    # --- Standardized Border Box (Grid Frame) ---
    if include_grid_frame:
        pen = QPen(QColor("#a0aec0"), 1.5)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(content_rect)

        # Tick marks along edges every 10%
        for i in range(1, 10):
            t = i / 10.0
            x = content_x + content_w * t
            # Top edge ticks
            painter.drawLine(QPointF(x, content_y), QPointF(x, content_y + 6))
            # Bottom edge ticks
            painter.drawLine(QPointF(x, content_y + content_h), QPointF(x, content_y + content_h - 6))
            
            y = content_y + content_h * t
            # Left edge ticks
            painter.drawLine(QPointF(content_x, y), QPointF(content_x + 6, y))
            # Right edge ticks
            painter.drawLine(QPointF(content_x + content_w, y), QPointF(content_x + content_w - 6, y))

    # --- Render Title Block ---
    title_rect = QRectF(margin, margin, page_w - margin * 2, title_h)
    painter.save()
    painter.setPen(QColor("#1a202c"))
    font = QFont("Arial", 16, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, title)
    painter.restore()

    # --- Render Legend Panel ---
    if include_legend and canvas.tops_model is not None:
        legend_y = page_h - margin - legend_h
        legend_rect = QRectF(margin, legend_y, page_w - margin * 2, legend_h)
        
        # Draw elegant sub-border for legend
        pen = QPen(QColor("#e2e8f0"), 1.0)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.drawRect(legend_rect)
        
        # Collect unique formation tops
        unique_tops = {}
        for well in canvas.widget._well_names:
            for top in canvas.tops_model.tops_for_well(well):
                unique_tops[top.formation_name] = top.color
                
        if unique_tops:
            painter.save()
            font = QFont("Arial", 9)
            painter.setFont(font)
            
            # Start position for swatches list
            start_x = margin + int(10 / mm_per_px)
            y_offset = legend_y + int(4 / mm_per_px)
            swatch_w = int(12 / mm_per_px)
            swatch_h = int(6 / mm_per_px)
            gap = int(15 / mm_per_px)
            
            curr_x = start_x
            for name, color_hex in unique_tops.items():
                color = QColor(color_hex)
                
                # Check wrap-around
                if curr_x + swatch_w + int(80 / mm_per_px) > page_w - margin:
                    # Multi-row layout if too many tops
                    curr_x = start_x
                    y_offset += int(8 / mm_per_px)
                
                # Draw color swatch block
                painter.fillRect(QRectF(curr_x, y_offset, swatch_w, swatch_h), color)
                painter.setPen(QPen(QColor("#718096"), 0.5))
                painter.drawRect(QRectF(curr_x, y_offset, swatch_w, swatch_h))
                
                # Draw label text
                painter.setPen(QColor("#2d3748"))
                painter.drawText(
                    QPointF(curr_x + swatch_w + int(4 / mm_per_px), y_offset + swatch_h - int(1 / mm_per_px)),
                    name
                )
                
                curr_x += swatch_w + int(4 / mm_per_px) + int(len(name) * 6 / mm_per_px) + gap
                
            painter.restore()

    painter.end()

    # Save to PNG file specifically
    if format == "png":
        device.save(str(file_path), "PNG")
