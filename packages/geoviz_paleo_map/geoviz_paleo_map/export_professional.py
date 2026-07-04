"""Professional figure export with standardized frame (title, scale bar, north arrow, legend, grid)."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Literal

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPageLayout
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


def _compute_data_bounds(
    features: list[dict],
) -> tuple[float, float, float, float] | None:
    """Compute (min_lng, max_lng, min_lat, max_lat) from GeoJSON features.

    Fallback used when the canvas viewport has no fitted data bounds (e.g. the
    widget was never sized, so ``fit_viewport_to_data`` early-returned).
    """
    lngs: list[float] = []
    lats: list[float] = []
    for feat in features:
        geom = feat.get("geometry") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates")
        if not coords:
            continue
        if gtype == "Polygon":
            polygons = [coords]
        elif gtype == "MultiPolygon":
            polygons = coords
        else:
            continue
        for poly in polygons:
            for ring in poly:
                for pt in ring:
                    if len(pt) >= 2:
                        lngs.append(pt[0])
                        lats.append(pt[1])
    if not lngs or not lats:
        return None
    return (min(lngs), max(lngs), min(lats), max(lats))


def _fit_zoom_for_bounds(
    data_bounds: tuple[float, float, float, float],
    map_w: int,
    map_h: int,
) -> float:
    """Zoom that makes the data fill the map area (max scale, fill-and-crop).

    Mirrors ``PaleoMapCanvas.fit_viewport_to_data`` so the exported map fills
    the page the same way the on-screen canvas fills the widget, instead of
    inheriting the widget's pixel scale into a much larger page.
    """
    min_lng, max_lng, min_lat, max_lat = data_bounds
    data_w = max(1e-6, max_lng - min_lng)
    data_h = max(1e-6, max_lat - min_lat)
    scale = max(map_w / data_w, map_h / data_h)
    return max(0.1, min(10.0, math.log2(scale) + 1.0))


def _nice_step(span: float, target: int = 5) -> float:
    """Pick a 'nice' round tick step giving roughly `target` ticks across span."""
    if span <= 0:
        return 1.0
    raw = span / target
    mag = 10 ** math.floor(math.log10(raw))
    for cand in (1, 2, 2.5, 5, 10):
        if cand * mag >= raw:
            return cand * mag
    return 10 * mag


def _viewport_extent(viewport) -> tuple[float, float, float, float]:
    """Visible (min_lng, max_lng, min_lat, max_lat) for a Plate Carree viewport."""
    from geoviz_paleo_map.projection import world_to_lnglat
    wleft, wbot, wright, wtop = viewport.world_bbox()
    min_lng = world_to_lnglat(wleft, 0.0)[0]
    max_lng = world_to_lnglat(wright, 0.0)[0]
    min_lat = world_to_lnglat(0.0, wbot)[1]
    max_lat = world_to_lnglat(0.0, wtop)[1]
    return min_lng, max_lng, min_lat, max_lat


def _draw_coordinate_frame(painter, map_rect, viewport, dpi: int) -> None:
    """Publication coordinate frame: neat-line border, faint internal graticule,
    and degree-valued tick labels (e.g. 110°E / 30°N) on all four edges.

    Ticks/labels are placed from the fitted data viewport's visible lng/lat
    extent using an auto-computed nice step, replacing the old fixed 20% ticks.
    """
    map_x, map_y = map_rect.x(), map_rect.y()
    map_w, map_h = map_rect.width(), map_rect.height()

    min_lng, max_lng, min_lat, max_lat = _viewport_extent(viewport)
    mid_lng = (min_lng + max_lng) / 2
    mid_lat = (min_lat + max_lat) / 2
    lng_step = _nice_step(max_lng - min_lng)
    lat_step = _nice_step(max_lat - min_lat)

    def lng_x(lng: float) -> float:
        return map_x + viewport.lnglat_to_screen(lng, mid_lat).x()

    def lat_y(lat: float) -> float:
        return map_y + viewport.lnglat_to_screen(mid_lng, lat).y()

    font_px = max(14, int(round(dpi / 12)))
    painter.setFont(QFont("Sans Serif", font_px))
    fm = painter.fontMetrics()

    # 1. Faint internal graticule
    grid_pen = QPen(QColor(120, 140, 165, 70), 1.0)
    grid_pen.setCosmetic(True)
    painter.setPen(grid_pen)
    lng = math.ceil(min_lng / lng_step) * lng_step
    while lng <= max_lng + 1e-9:
        x = lng_x(lng)
        if map_x <= x <= map_x + map_w:
            painter.drawLine(QPointF(x, map_y), QPointF(x, map_y + map_h))
        lng += lng_step
    lat = math.ceil(min_lat / lat_step) * lat_step
    while lat <= max_lat + 1e-9:
        y = lat_y(lat)
        if map_y <= y <= map_y + map_h:
            painter.drawLine(QPointF(map_x, y), QPointF(map_x + map_w, y))
        lat += lat_step

    # 2. Neat-line border
    border_pen = QPen(QColor("#475569"), 1.5)
    border_pen.setCosmetic(True)
    painter.setPen(border_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(map_rect)

    # 3. Degree tick marks + labels on all four edges (labels sit in the margin)
    tick = max(5, int(round(dpi / 40)))
    label_pen = QPen(QColor("#1a2433"), 0)

    def lng_marks(lng: float) -> None:
        x = lng_x(lng)
        if not (map_x <= x <= map_x + map_w):
            return
        painter.setPen(border_pen)
        painter.drawLine(QPointF(x, map_y), QPointF(x, map_y - tick))
        painter.drawLine(QPointF(x, map_y + map_h), QPointF(x, map_y + map_h + tick))
        painter.setPen(label_pen)
        lbl = f"{lng:g}°E"
        lw = fm.horizontalAdvance(lbl)
        painter.drawText(QPointF(x - lw / 2, map_y - tick - 4), lbl)
        painter.drawText(QPointF(x - lw / 2, map_y + map_h + tick + fm.ascent() + 4), lbl)

    def lat_marks(lat: float) -> None:
        y = lat_y(lat)
        if not (map_y <= y <= map_y + map_h):
            return
        painter.setPen(border_pen)
        painter.drawLine(QPointF(map_x, y), QPointF(map_x - tick, y))
        painter.drawLine(QPointF(map_x + map_w, y), QPointF(map_x + map_w + tick, y))
        painter.setPen(label_pen)
        lbl = f"{lat:g}°N"
        lw = fm.horizontalAdvance(lbl)
        painter.drawText(QPointF(map_x - tick - 5 - lw, y + fm.ascent() / 2 - 1), lbl)
        painter.drawText(QPointF(map_x + map_w + tick + 5, y + fm.ascent() / 2 - 1), lbl)

    lng = math.ceil(min_lng / lng_step) * lng_step
    while lng <= max_lng + 1e-9:
        lng_marks(lng)
        lng += lng_step
    lat = math.ceil(min_lat / lat_step) * lat_step
    while lat <= max_lat + 1e-9:
        lat_marks(lat)
        lat += lat_step


def _numeric_scale_denominator(viewport, dpi: int) -> int:
    """Map-scale denominator N for a '1:N' ratio, from the fitted viewport.

    1 page-pixel = (25.4/dpi) mm on paper = km_per_px km in reality, so
    N = km_per_px * 1e6 mm/km / mm_per_px, rounded to a nice round number.
    """
    min_lng, max_lng, min_lat, max_lat = _viewport_extent(viewport)
    mid_lat = (min_lat + max_lat) / 2
    deg_to_km = 111.32 * math.cos(math.radians(mid_lat))
    span_km = (max_lng - min_lng) * deg_to_km
    if viewport.width <= 0 or span_km <= 0:
        return 0
    km_per_px = span_km / viewport.width
    mm_per_px = 25.4 / dpi
    n = (km_per_px * 1_000_000.0) / mm_per_px
    if n <= 0:
        return 0
    mag = 10 ** math.floor(math.log10(n))
    return int(round(n / mag)) * int(mag)


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

    # Margins (in pixels)
    margin = int(15 / mm_per_px)

    # Map area covers the whole page area within margins as one single canvas
    map_x = margin
    map_y = margin
    map_w = page_w - margin * 2
    map_h = page_h - margin * 2
    map_rect = QRectF(map_x, map_y, map_w, map_h)

    # --- Map Content ---
    # Re-fit the viewport to the data bounds so the map FILLS the export page,
    # matching the on-screen fit. Copying the canvas zoom verbatim would render
    # the map at the widget's pixel scale inside a far larger page, leaving it
    # as a tiny square with huge blank margins and sub-pixel patterns.
    from geoviz_paleo_map.viewport import PaleoMapViewport
    from geoviz_paleo_map.projection import world_to_lnglat

    data_bounds = canvas._viewport.data_bounds
    if data_bounds is None:
        data_bounds = _compute_data_bounds(getattr(canvas, "_loaded_features", []))

    if data_bounds is not None:
        fit_zoom = _fit_zoom_for_bounds(data_bounds, map_w, map_h)
        min_lng, max_lng, min_lat, max_lat = data_bounds
        center_lng = (min_lng + max_lng) / 2
        center_lat = (min_lat + max_lat) / 2
    else:
        # No data to fit — keep the user's current view as-is.
        fit_zoom = canvas._viewport.zoom
        center_lng, center_lat = world_to_lnglat(*canvas._viewport.center_world)

    vp = PaleoMapViewport(
        center_lng=center_lng,
        center_lat=center_lat,
        zoom=fit_zoom,
        width=map_w,
        height=map_h,
    )
    if data_bounds is not None:
        # Enables the same fill-and-clamp behaviour the on-screen canvas uses.
        vp.data_bounds = data_bounds

    # Chrome layers (title/north arrow/scale bar/legend) use fixed pixel sizes
    # tuned for a ~96dpi widget. On a high-resolution page they would render
    # microscopic, so they paint against a widget-sized viewport under a
    # (dpi/96) scale: positions and element sizes then grow proportionally with
    # the page resolution while keeping the on-screen layout.
    chrome_scale = dpi / 96.0
    chrome_vp = PaleoMapViewport(
        center_lng=center_lng,
        center_lat=center_lat,
        zoom=fit_zoom,
        width=max(1, int(map_w / chrome_scale)),
        height=max(1, int(map_h / chrome_scale)),
    )

    painter.save()
    painter.setClipRect(map_rect)
    painter.translate(map_x, map_y)

    from geoviz_paleo_map.layers.legend import LegendLayer
    from geoviz_paleo_map.layers.scale_bar import ScaleBarLayer
    from geoviz_paleo_map.layers.north_arrow import NorthArrowLayer
    from geoviz_paleo_map.layers.title import TitleLayer
    from geoviz_paleo_map.layers.region_labels import RegionLabelsLayer

    # Decoration-priority placement: collect chrome footprints (in chrome_vp
    # coords, scaled into map/label space) and feed them to region-label layers
    # so labels avoid drawing under the legend / north arrow / scale bar.
    chrome_rects = []
    for layer in canvas._layers:
        if not getattr(layer, "is_chrome", False):
            continue
        if not include_legend and isinstance(layer, LegendLayer):
            continue
        if not include_scale_bar and isinstance(layer, ScaleBarLayer):
            continue
        if not include_north_arrow and isinstance(layer, NorthArrowLayer):
            continue
        r = layer.reserved_rect(chrome_vp)
        if r is not None:
            chrome_rects.append(QRectF(
                r.x() * chrome_scale, r.y() * chrome_scale,
                r.width() * chrome_scale, r.height() * chrome_scale,
            ))
    for layer in canvas._layers:
        if isinstance(layer, RegionLabelsLayer):
            layer.chrome_rects = chrome_rects

    for layer in canvas._layers:
        if not include_legend and isinstance(layer, LegendLayer):
            continue
        if not include_scale_bar and isinstance(layer, ScaleBarLayer):
            continue
        if not include_north_arrow and isinstance(layer, NorthArrowLayer):
            continue

        painter.save()
        is_chrome = getattr(layer, "is_chrome", False)
        layer_vp = chrome_vp if is_chrome else vp
        if is_chrome:
            painter.scale(chrome_scale, chrome_scale)
        if isinstance(layer, TitleLayer):
            old_text = layer.text
            layer.set_text(title if title is not None else old_text)
            layer.paint(painter, layer_vp)
            layer.set_text(old_text)
        else:
            layer.paint(painter, layer_vp)
        painter.restore()

    painter.restore()

    # --- Coordinate frame: neat-line + faint graticule + degree labels ---
    if include_grid_frame:
        _draw_coordinate_frame(painter, map_rect, vp, dpi)

    # --- Numeric scale ratio (1:N) in the bottom-left margin ---
    if include_scale_bar:
        denom = _numeric_scale_denominator(vp, dpi)
        if denom > 0:
            font_px = max(14, int(round(dpi / 12)))
            painter.setFont(QFont("Sans Serif", font_px))
            painter.setPen(QPen(QColor("#1a2433"), 0))
            fm = painter.fontMetrics()
            tick = max(5, int(round(dpi / 40)))
            label_y = map_y + map_h + tick + fm.height() + fm.ascent() + 6
            painter.drawText(QPointF(map_x, label_y), f"比例尺 1:{denom:,}")

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
