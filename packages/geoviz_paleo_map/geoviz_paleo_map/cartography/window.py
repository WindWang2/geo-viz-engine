# packages/geoviz_paleo_map/geoviz_paleo_map/cartography/window.py
"""Cartography Print Layout Window with PDF/SVG vector export."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPageSize, QPageLayout
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGraphicsView,
    QPushButton, QComboBox, QLabel, QFileDialog, QToolBar, QMessageBox, QGroupBox
)

from .scene import PaperGraphicsScene, get_paper_size_mm
from .templates import apply_template_preset
from .items.figure_panel_item import FigurePanelGraphicsItem

class CartographyLayoutWindow(QMainWindow):
    """WYSIWYG Cartography Layout Window for publishing figures."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("出版级图件排版编辑器 — GeoViz Cartography Engine")
        self.resize(1100, 750)

        self._scene = PaperGraphicsScene(page_size="A4", orientation="landscape")
        apply_template_preset(self._scene, "GB_EXPLORATION_SPEC")
        # Source plot ids the host (Workstation) populates for panel palette.
        self._plot_sources: list[str] = []

        # Main Layout
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # 1. Canvas View (Center)
        self._view = QGraphicsView(self._scene)
        self._view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self._view.setStyleSheet("background: #e2e8f0; border: 1px solid #cbd5e1;")
        main_layout.addWidget(self._view, 1)

        # 2. Right Sidebar (Property Inspector & Controls)
        sidebar = self._build_sidebar()
        main_layout.addWidget(sidebar)

        # Build Toolbar
        self._build_toolbar()
        self._view.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _build_toolbar(self):
        tb = self.addToolBar("Layout Controls")

        tb.addWidget(QLabel(" 预设模板："))
        self._preset_combo = QComboBox()
        self._preset_combo.addItems(["GB_EXPLORATION_SPEC", "ACADEMIC_JOURNAL"])
        self._preset_combo.currentTextChanged.connect(self._on_preset_changed)
        tb.addWidget(self._preset_combo)

        tb.addSeparator()
        tb.addWidget(QLabel(" 纸张："))
        self._paper_combo = QComboBox()
        self._paper_combo.addItems(["A4", "A3", "A2"])
        self._paper_combo.currentTextChanged.connect(self._on_paper_changed)
        tb.addWidget(self._paper_combo)

        self._orient_combo = QComboBox()
        self._orient_combo.addItems(["landscape", "portrait"])
        self._orient_combo.currentTextChanged.connect(self._on_paper_changed)
        tb.addWidget(self._orient_combo)

        tb.addSeparator()
        pdf_btn = QPushButton(" 导出高精 PDF")
        pdf_btn.clicked.connect(self.export_pdf)
        tb.addWidget(pdf_btn)

        svg_btn = QPushButton(" 导出矢量 SVG")
        svg_btn.clicked.connect(self.export_svg)
        tb.addWidget(svg_btn)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet("background: #ffffff; border-left: 1px solid #e2e8f0;")
        s_layout = QVBoxLayout(sidebar)
        s_layout.setContentsMargins(12, 12, 12, 12)
        s_layout.setSpacing(12)

        lbl = QLabel("排版元素属性")
        lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #1a2433;")
        s_layout.addWidget(lbl)

        box = QGroupBox("说明")
        b_layout = QVBoxLayout(box)
        msg = QLabel("在画布中点击拖拽图元（责任表、图例、图件面板等）可自由排版。导出支持 300 DPI 矢量 PDF 与 SVG。")
        msg.setWordWrap(True)
        msg.setStyleSheet("font-size: 11px; color: #586878;")
        b_layout.addWidget(msg)
        s_layout.addWidget(box)

        # 图件面板 palette (Phase-2 T7 / #251): the host (Workstation)
        # populates source plot ids; the user picks one + a slot and clicks
        # 添加面板 to drop a FigurePanelGraphicsItem on the paper.
        panel_box = QGroupBox("图件面板")
        panel_layout = QVBoxLayout(panel_box)
        self._panel_source_combo = QComboBox()
        self._panel_source_combo.addItem("（无图件来源）")
        self._panel_source_combo.setToolTip("选择要嵌入的来源图件（来自工区 plots）")
        panel_layout.addWidget(self._panel_source_combo)
        self._panel_slot_combo = QComboBox()
        self._panel_slot_combo.addItems(["main", "left", "right", "top", "bottom"])
        panel_layout.addWidget(self._panel_slot_combo)
        self._panel_render_combo = QComboBox()
        self._panel_render_combo.addItems(["live", "snapshot"])
        self._panel_render_combo.setToolTip(
            "live = 非 GL 图件嵌入代理控件；snapshot = GL/引擎图件用像素快照"
        )
        panel_layout.addWidget(self._panel_render_combo)
        add_btn = QPushButton("添加图件面板")
        add_btn.setObjectName("Button_AddFigurePanel")
        add_btn.clicked.connect(self._on_add_figure_panel)
        panel_layout.addWidget(add_btn)
        s_layout.addWidget(panel_box)

        s_layout.addStretch()
        return sidebar

    def set_plot_sources(self, plot_ids: list[str]) -> None:
        """Populate the panel palette with source plot ids.

        The host (Workstation) calls this with ``workspace.plots`` ids so the
        user can drop any existing plot onto the paper. No engine→workstation
        dependency: ids are opaque strings here.
        """
        self._plot_sources = list(plot_ids)
        combo = self._panel_source_combo
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("（无图件来源）")
        combo.addItems(self._plot_sources)
        combo.blockSignals(False)

    def plot_sources(self) -> list[str]:
        return list(self._plot_sources)

    def add_figure_panel(
        self,
        source_plot_id: str,
        source_plot_type: str = "single_well",
        render_mode: str = "live",
        rect_mm: QRectF | None = None,
    ) -> FigurePanelGraphicsItem:
        """Create and add a FigurePanelGraphicsItem to the paper scene.

        Default rect: a half-page panel in the printable area, positioned at
        the current count offset so multiple panels do not overlap exactly.
        """
        if rect_mm is None:
            printable = self._scene.printable_rect()
            count = len(self.figure_panels())
            w = printable.width() * 0.5
            h = printable.height() * 0.5
            x = printable.x() + (count % 2) * w
            y = printable.y() + (count // 2) * h
            rect_mm = QRectF(x, y, w, h)
        item = FigurePanelGraphicsItem(
            rect_mm,
            source_plot_id=source_plot_id,
            source_plot_type=source_plot_type,  # type: ignore[arg-type]
            render_mode=render_mode,  # type: ignore[arg-type]
        )
        self._scene.addItem(item)
        return item

    def figure_panels(self) -> list[FigurePanelGraphicsItem]:
        """Return all FigurePanelGraphicsItem instances on the paper."""
        return [
            item
            for item in self._scene.items()
            if isinstance(item, FigurePanelGraphicsItem)
        ]

    def _on_add_figure_panel(self) -> None:
        source = self._panel_source_combo.currentText()
        if not source or source == "（无图件来源）":
            QMessageBox.information(self, "图件面板", "请先选择来源图件")
            return
        render_mode = self._panel_render_combo.currentText()
        self.add_figure_panel(source, render_mode=render_mode)
        self._view.fitInView(
            self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
        )

    def _on_preset_changed(self, preset_name: str):
        apply_template_preset(self._scene, preset_name)
        self._view.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _on_paper_changed(self):
        page_size = self._paper_combo.currentText()
        orient = self._orient_combo.currentText()
        self._scene.set_paper_size(page_size, orient)
        self._view.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def export_pdf(self, file_path: str | None = None) -> str | None:
        if not file_path:
            file_path, _ = QFileDialog.getSaveFileName(self, "导出高精 PDF", "geoviz_layout.pdf", "PDF Files (*.pdf)")
        if not file_path:
            return None

        w_mm, h_mm = get_paper_size_mm(self._paper_combo.currentText(), self._orient_combo.currentText())

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        
        # Select page size
        ps_map = {"A4": QPageSize.PageSizeId.A4, "A3": QPageSize.PageSizeId.A3, "A2": QPageSize.PageSizeId.A2}
        printer.setPageSize(QPageSize(ps_map.get(self._paper_combo.currentText(), QPageSize.PageSizeId.A4)))
        
        if self._orient_combo.currentText() == "portrait":
            printer.setPageOrientation(QPageLayout.Orientation.Portrait)
        else:
            printer.setPageOrientation(QPageLayout.Orientation.Landscape)

        printer.setOutputFileName(file_path)

        painter = QPainter(printer)
        self._scene.render(painter, QRectF(), self._scene.paper_rect())
        painter.end()

        return file_path

    def export_svg(self, file_path: str | None = None) -> str | None:
        if not file_path:
            file_path, _ = QFileDialog.getSaveFileName(self, "导出矢量 SVG", "geoviz_layout.svg", "SVG Files (*.svg)")
        if not file_path:
            return None

        w_mm, h_mm = get_paper_size_mm(self._paper_combo.currentText(), self._orient_combo.currentText())

        generator = QSvgGenerator()
        generator.setFileName(file_path)
        generator.setSize(QSize(int(w_mm * 11.8), int(h_mm * 11.8)))  # ~300 DPI scaling
        generator.setViewBox(QRectF(0, 0, w_mm, h_mm))
        generator.setResolution(300)

        painter = QPainter(generator)
        self._scene.render(painter, QRectF(), self._scene.paper_rect())
        painter.end()

        return file_path
