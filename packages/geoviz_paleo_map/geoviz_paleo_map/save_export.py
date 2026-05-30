"""Save topology to GeoJSON and export canvas as SVG/PDF/PNG."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QPainter, QPixmap

from geoviz_paleo_map.topology import TopologyModel


def save_geojson(model: TopologyModel, file_path: str | Path) -> None:
    """Save the topology model to a GeoJSON file."""
    data = model.to_geojson()
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    model.is_dirty = False


def save_hierarchy_geojson(model: TopologyModel, source_files: dict[str, str]) -> None:
    """Save features back to their respective source files by level.

    Args:
        model: The topology model containing all features.
        source_files: Mapping of level name → file path.
    """
    features_by_file: dict[str, list[dict]] = {}
    data = model.to_geojson()

    for feat in data.get("features", []):
        props = feat.get("properties", {})
        level = props.get("level", "facies")
        file_path = source_files.get(level)
        if file_path:
            features_by_file.setdefault(file_path, []).append(feat)

    for file_path, features in features_by_file.items():
        collection = {"type": "FeatureCollection", "features": features}
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(collection, f, ensure_ascii=False, indent=2)

    model.is_dirty = False


def export_png(widget, file_path: str | Path) -> None:
    """Export the canvas widget as PNG."""
    pixmap = widget.grab()
    pixmap.save(str(file_path), "PNG")


def export_pdf(widget, file_path: str | Path) -> None:
    """Export the canvas widget as PDF."""
    from PySide6.QtGui import QPageSize, QPageLayout
    from PySide6.QtPrintSupport import QPrinter

    pixmap = widget.grab()
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFileName(str(file_path))
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    painter = QPainter(printer)
    page_rect = printer.pageRect(QPrinter.DevicePixel)
    scaled = pixmap.scaled(page_rect.size(), Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
    x = (page_rect.width() - scaled.width()) // 2
    y = (page_rect.height() - scaled.height()) // 2
    painter.drawPixmap(x, y, scaled)
    painter.end()


def export_svg(widget, file_path: str | Path) -> None:
    """Export the canvas widget as SVG (raster embedded in SVG wrapper)."""
    import base64
    import io

    pixmap = widget.grab()
    buffer = io.BytesIO()
    pixmap.save(buffer, "PNG")
    b64 = base64.b64encode(buffer.getvalue()).decode()
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{pixmap.width()}" height="{pixmap.height()}">'
        f'<image href="data:image/png;base64,{b64}" '
        f'width="{pixmap.width()}" height="{pixmap.height()}"/>'
        f'</svg>'
    )
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(svg)


def export_vector_svg(canvas, file_path: str | Path, target_rect: QRectF | None = None) -> None:
    """Export the canvas as a true vector SVG using QSvgGenerator.

    All layer paint() methods render through QSvgGenerator's QPainter,
    producing SVG <path>, <text>, and <image> elements.

    Args:
        canvas: The PaleoMapCanvas to export.
        file_path: Output SVG file path.
        target_rect: Target rectangle in canvas coordinates. If None, uses the
            full canvas size.
    """
    from PySide6.QtSvg import QSvgGenerator

    file_path = Path(file_path)
    rect = target_rect or QRectF(0, 0, canvas.width(), canvas.height())

    generator = QSvgGenerator()
    generator.setFileName(str(file_path))
    generator.setSize(QSize(int(rect.width()), int(rect.height())))
    generator.setViewBox(rect)

    painter = QPainter(generator)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # Paint each layer directly through the generator's painter
    for layer in canvas._layers:
        painter.save()
        layer.paint(painter, canvas._viewport)
        painter.restore()

    painter.end()
