from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QPageLayout, QPageSize
from PySide6.QtWidgets import QFileDialog, QWidget


def export_svg(engine, parent: QWidget | None = None, default_name: str = "well_log") -> str | None:
    """Trigger SVG export from ECharts. Returns the chosen file path or None.

    SVG is produced by ECharts' built-in getDataURL({type:'svg'}), which renders
    from the same SVG renderer used for display — guaranteeing vector fidelity.
    The result is delivered asynchronously via engine.bridge.svg_received signal.
    """
    path, _ = QFileDialog.getSaveFileName(
        parent, "导出测井图", f"{default_name}.svg", "SVG 矢量 (*.svg)"
    )
    if not path:
        return None
    if not path.lower().endswith(".svg"):
        path += ".svg"
    engine._export_path = path
    engine.export_svg()
    return path


def export_pdf(engine, parent: QWidget | None = None, default_name: str = "well_log") -> str | None:
    """Export as PDF via QWebEngineView printToPdf (vector output).

    The web page renders with ECharts SVG renderer, so printToPdf produces
    vector output identical to the displayed chart.
    """
    path, _ = QFileDialog.getSaveFileName(
        parent, "导出测井图", f"{default_name}.pdf", "PDF 文件 (*.pdf)"
    )
    if not path:
        return None
    # A3 Landscape with zero margins avoids clipping wide multi-track content
    page_layout = QPageLayout(
        QPageSize(QPageSize.PageSizeId.A3),
        QPageLayout.Orientation.Landscape,
        QMarginsF(0, 0, 0, 0),
    )
    engine.view.page().printToPdf(path, page_layout)
    return path


def export_png(engine, parent: QWidget | None = None, default_name: str = "well_log") -> str | None:
    """Export as PNG via widget grab (raster fallback for bitmap use cases).

    Note: PNG is raster and may differ slightly from the vector display at high zoom.
    For pixel-perfect output, prefer SVG or PDF export.
    """
    path, _ = QFileDialog.getSaveFileName(
        parent, "导出测井图", f"{default_name}.png", "PNG 图片 (*.png)"
    )
    if not path:
        return None
    pixmap = engine.view.grab()
    pixmap.save(path, "PNG")
    return path


def export_dialog(engine, parent: QWidget | None = None, default_name: str = "well_log") -> str | None:
    """Show a unified export dialog with format selection.

    SVG and PDF produce vector output identical to display.
    PNG is raster (for convenience only).
    """
    path, _ = QFileDialog.getSaveFileName(
        parent, "导出测井图", default_name,
        "SVG 矢量 (*.svg);;PDF 文件 (*.pdf);;PNG 图片 (*.png)"
    )
    if not path:
        return None

    if path.lower().endswith(".pdf"):
        page_layout = QPageLayout(
            QPageSize(QPageSize.PageSizeId.A3),
            QPageLayout.Orientation.Landscape,
            QMarginsF(0, 0, 0, 0),
        )
        engine.view.page().printToPdf(path, page_layout)
        return path

    if path.lower().endswith(".png"):
        pixmap = engine.view.grab()
        pixmap.save(path, "PNG")
        return path

    # Default: SVG
    if not path.lower().endswith(".svg"):
        path += ".svg"
    engine._export_path = path
    engine.export_svg()
    return path
