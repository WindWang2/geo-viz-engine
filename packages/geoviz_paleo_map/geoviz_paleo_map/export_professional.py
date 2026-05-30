"""Professional figure export with standardized frame (title, scale bar, north arrow, legend, grid)."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Literal

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtPrintSupport import QPrinter


_PAGE_SIZES_MM = {
    "A4": (297, 210),
    "A3": (420, 297),
    "A2": (594, 420),
}


def _page_size_mm(page_size: str, orientation: str) -> tuple[int, int]:
    w, h = _PAGE_SIZES_MM[page_size]
    if orientation == "portrait":
        return h, w
    return w, h


def _dpi_to_mm(dpi: int) -> float:
    return 25.4 / dpi


def export_professional_figure(
    canvas,
    file_path: str | Path,
    format: Literal["svg", "pdf", "png"],
    *,
    title: str,
    page_size: Literal["A4", "A3", "A2"] = "A4",
    orientation: Literal["portrait", "landscape"] = "landscape",
    dpi: int = 300,
    color_mode: Literal["rgb", "cmyk"] = "rgb",
    include_scale_bar: bool = True,
    include_north_arrow: bool = True,
    include_legend: bool = True,
    include_grid_frame: bool = True,
) -> None:
    """Export a professional publishing-grade figure with standardized frame.

    Args:
        canvas: PaleoMapCanvas to export.
        file_path: Output file path.
        format: "svg", "pdf", or "png".
        title: Figure title (rendered in title block).
        page_size: Page size for PDF/print output.
        orientation: "portrait" or "landscape".
        dpi: Resolution for raster and PDF output.
        color_mode: "rgb" or "cmyk".
        include_scale_bar: Render scale bar in bottom-left.
        include_north_arrow: Render north arrow in top-right.
        include_legend: Render legend panel.
        include_grid_frame: Render coordinate grid frame around map.
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
            device.setPageOrientation(Qt.Orientation.Horizontal)
        else:
            device.setPageOrientation(Qt.Orientation.Vertical)
    else:  # png
        from PySide6.QtGui import QPixmap
        device = QPixmap(page_w, page_h)
        device.fill(Qt.GlobalColor.white)

    painter = QPainter(device)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # Page background
    painter.fillRect(QRectF(0, 0, page_w, page_h), QColor("#ffffff"))

    # Margins (in pixels)
    margin = int(15 / mm_per_px)
    title_h = int(20 / mm_per_px) if title else 0
    bottom_h = int(15 / mm_per_px)
    right_w = int(60 / mm_per_px) if include_legend else 0

    # Map area
    map_x = margin
    map_y = margin + title_h
    map_w = page_w - margin * 2 - right_w
    map_h = page_h - margin - title_h - bottom_h - margin

    # --- Title Block ---
    if title:
        painter.setPen(QPen(QColor("#1a202c")))
        font = QFont("Microsoft YaHei", 14)
        font.setBold(True)
        painter.setFont(font)
        title_rect = QRectF(margin, margin, page_w - margin * 2, title_h)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, title)

    # --- Grid Frame ---
    map_rect = QRectF(map_x, map_y, map_w, map_h)
    if include_grid_frame:
        pen = QPen(QColor("#a0aec0"), 1.0)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(map_rect)
        # Tick marks every 20% along edges
        for i in range(1, 5):
            t = i / 5.0
            # Top
            x = map_x + map_w * t
            painter.drawLine(QPointF(x, map_y), QPointF(x, map_y + 5))
            # Bottom
            painter.drawLine(QPointF(x, map_y + map_h), QPointF(x, map_y + map_h - 5))
            # Left
            y = map_y + map_h * t
            painter.drawLine(QPointF(map_x, y), QPointF(map_x + 5, y))
            # Right
            painter.drawLine(QPointF(map_x + map_w, y), QPointF(map_x + map_w - 5, y))

    # --- Map Content ---
    # Create a temporary viewport scaled to the map rect
    from geoviz_paleo_map.viewport import PaleoMapViewport
    from geoviz_paleo_map.projection import world_to_lnglat
    center_lng, center_lat = world_to_lnglat(*canvas._viewport.center_world)
    vp = PaleoMapViewport(
        center_lng=center_lng,
        center_lat=center_lat,
        zoom=canvas._viewport.zoom,
        width=map_w,
        height=map_h,
    )

    painter.save()
    painter.setClipRect(map_rect)
    painter.translate(map_x, map_y)
    for layer in canvas._layers:
        layer.paint(painter, vp)
    painter.restore()

    # --- Scale Bar ---
    if include_scale_bar:
        _draw_scale_bar(painter, map_x + 10, map_y + map_h - 25,
                        canvas._viewport, dpi)

    # --- North Arrow ---
    if include_north_arrow:
        _draw_north_arrow(painter, map_x + map_w - 30, map_y + 10)

    # --- Legend Panel ---
    if include_legend:
        _draw_legend_panel(painter, map_x + map_w + 10, map_y,
                           right_w - 10, map_h, canvas)

    painter.end()

    if format == "png":
        device.save(str(file_path), "PNG")


def _draw_scale_bar(painter: QPainter, x: float, y: float, viewport, dpi: int) -> None:
    """Draw a metric scale bar with auto-computed length."""
    from geoviz_paleo_map.projection import world_to_lnglat
    _lng, lat = world_to_lnglat(*viewport.center_world)
    km_per_deg = 111.32 * math.cos(math.radians(lat))
    km_per_px = km_per_deg * (360.0 / (256.0 * (2 ** viewport.zoom)))

    # Pick a nice round length (1, 2, 5, 10, 20, 50, 100, 200, 500 km)
    target_px = 100
    target_km = target_px * km_per_px
    nice_lengths = [0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]
    bar_km = min(nice_lengths, key=lambda v: abs(v - target_km))
    bar_px = bar_km / km_per_px

    pen = QPen(QColor("#1a202c"), 2.0)
    pen.setCosmetic(True)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    # Bar line
    painter.drawLine(QPointF(x, y), QPointF(x + bar_px, y))
    # Ticks
    painter.drawLine(QPointF(x, y - 4), QPointF(x, y + 4))
    painter.drawLine(QPointF(x + bar_px, y - 4), QPointF(x + bar_px, y + 4))

    # Label
    painter.setPen(QPen(QColor("#1a202c")))
    font = QFont("Microsoft YaHei", 8)
    painter.setFont(font)
    label = f"{bar_km:g} km"
    painter.drawText(QRectF(x, y + 6, bar_px, 16),
                     Qt.AlignmentFlag.AlignCenter, label)


def _draw_north_arrow(painter: QPainter, x: float, y: float, size: float = 20.0) -> None:
    """Draw a simple north arrow."""
    pen = QPen(QColor("#1a202c"), 1.5)
    pen.setCosmetic(True)
    painter.setPen(pen)
    painter.setBrush(QColor("#1a202c"))

    # Arrow head (triangle pointing up)
    arrow = QPainterPath()
    arrow.moveTo(x + size / 2, y)
    arrow.lineTo(x + size, y + size)
    arrow.lineTo(x + size / 2, y + size * 0.7)
    arrow.lineTo(x, y + size)
    arrow.closeSubpath()
    painter.drawPath(arrow)

    # N label
    painter.setPen(QPen(QColor("#1a202c")))
    font = QFont("Microsoft YaHei", 8)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(QRectF(x, y + size + 2, size, 14),
                     Qt.AlignmentFlag.AlignCenter, "N")


def _draw_legend_panel(painter: QPainter, x: float, y: float,
                       width: float, height: float, canvas) -> None:
    """Draw a legend panel with color swatches and facies names."""
    # Use the legend layer's facies names if available
    legend_layer = None
    for layer in canvas._layers:
        if hasattr(layer, "facies_names"):
            legend_layer = layer
            break

    if legend_layer is None:
        return

    facies_names = list(getattr(legend_layer, "facies_names", []))
    if not facies_names:
        return

    # Panel background
    painter.fillRect(QRectF(x, y, width, height), QColor("#f8fafc"))
    border_pen = QPen(QColor("#cbd5e1"), 1.0)
    border_pen.setCosmetic(True)
    painter.setPen(border_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(QRectF(x, y, width, height))

    # Title
    painter.setPen(QPen(QColor("#1a202c")))
    font = QFont("Microsoft YaHei", 9)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(QRectF(x + 4, y + 4, width - 8, 18),
                     Qt.AlignmentFlag.AlignLeft, "图例")

    # Swatches
    resolver = canvas._resolver
    swatch_size = 14
    row_h = 20
    text_x = x + swatch_size + 10
    text_w = width - swatch_size - 14

    painter.setFont(QFont("Microsoft YaHei", 8))
    for i, name in enumerate(facies_names):
        row_y = y + 24 + i * row_h
        style = resolver.resolve(name)
        painter.fillRect(QRectF(x + 4, row_y, swatch_size, swatch_size),
                         style.brush)
        painter.setPen(border_pen)
        painter.drawRect(QRectF(x + 4, row_y, swatch_size, swatch_size))
        painter.setPen(QPen(QColor("#1a202c")))
        painter.drawText(QRectF(text_x, row_y, text_w, swatch_size),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         name)
