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

class CartographyLayoutWindow(QMainWindow):
    """WYSIWYG Cartography Layout Window for publishing figures."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("出版级图件排版编辑器 — GeoViz Cartography Engine")
        self.resize(1100, 750)

        self._scene = PaperGraphicsScene(page_size="A4", orientation="landscape")
        apply_template_preset(self._scene, "GB_EXPLORATION_SPEC")

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
        msg = QLabel("在画布中点击拖拽图元（责任表、图例等）可自由排版。导出支持 300 DPI 矢量 PDF 与 SVG。")
        msg.setWordWrap(True)
        msg.setStyleSheet("font-size: 11px; color: #586878;")
        b_layout.addWidget(msg)
        s_layout.addWidget(box)

        s_layout.addStretch()
        return sidebar

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
