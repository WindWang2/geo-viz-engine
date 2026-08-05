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

        # Placement controller for free graphics (Task 7).
        from geoviz_paleo_map.cartography.placement import PlacementController
        self._placement = PlacementController(self._scene, parent_window=self)
        self._tool_mode = "select"
        self._build_free_toolbar()
        # Route view mouse/key events to the placement controller. The
        # viewport receives the raw widget mouse events (QGraphicsView
        # converts them to scene events internally); filtering both keeps
        # placement working regardless of which event flavour Qt delivers.
        self._view.installEventFilter(self)
        self._view.viewport().installEventFilter(self)

        # Property panel in the sidebar (Task 8).
        from geoviz_paleo_map.cartography.properties import PropertyPanel
        self._property_panel = PropertyPanel()
        # Insert into the existing sidebar (built by _build_sidebar), before
        # the trailing stretch.
        sidebar_layout: QVBoxLayout = self._sidebar_layout
        sidebar_layout.insertWidget(sidebar_layout.count() - 1, self._property_panel)
        self._scene.selectionChanged.connect(self._on_selection_changed)

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
        self._sidebar_layout = s_layout
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

    def scene(self):
        """Public accessor replacing ``window._scene`` private access."""
        return self._scene

    def view(self):
        """Public accessor replacing ``win._view`` private access."""
        return self._view

    def figure_panels(self) -> list[FigurePanelGraphicsItem]:
        """Return all FigurePanelGraphicsItem instances on the paper."""
        return [
            item
            for item in self._scene.items()
            if isinstance(item, FigurePanelGraphicsItem)
        ]

    # -- free-graphics public API (spec §3.6, Task 9) ------------------

    def add_free_graphic(self, record: dict) -> str | None:
        """Validate ``record`` and add the item to the scene.

        Returns the item id on success, None when the record is unknown /
        malformed (host counts and reports these). Unknown kinds are
        silently skipped — the host reports a count to the user.
        """
        from geoviz_paleo_map.cartography.items.free import item_from_record
        item = item_from_record(record)
        if item is None:
            return None
        self._scene.addItem(item)
        return item.id

    def free_graphics(self) -> list[dict]:
        """Return ``to_record()`` dicts for every free graphic on the paper."""
        from geoviz_paleo_map.cartography.items.free.base import FreeGraphicsItem
        return [
            it.to_record()
            for it in self._scene.items()
            if isinstance(it, FreeGraphicsItem)
        ]

    def remove_free_graphic(self, item_id: str) -> bool:
        """Remove the free graphic with ``item_id``; True when found."""
        from geoviz_paleo_map.cartography.items.free.base import FreeGraphicsItem
        for it in list(self._scene.items()):
            if isinstance(it, FreeGraphicsItem) and it.id == item_id:
                self._scene.removeItem(it)
                return True
        return False

    def panels(self) -> list[dict]:
        """Read back panel geometry as plain dicts for host persistence.

        Each dict: ``{plot_id, slot, source_plot_type, rect_mm, render_mode}``.
        """
        result = []
        for panel in self.figure_panels():
            r = panel.rect()
            p = panel.pos()
            result.append({
                "plot_id": panel.source_plot_id,
                "slot": "main",
                "source_plot_type": panel.source_plot_type,
                "rect_mm": [
                    round(p.x() + r.x(), 2),
                    round(p.y() + r.y(), 2),
                    round(r.width(), 2),
                    round(r.height(), 2),
                ],
                "render_mode": panel.render_mode,
            })
        return result

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

    # -- free-graphics tool bar + placement (Task 7) -------------------

    _TOOL_MODES = (
        ("select", "选择"),
        ("text", "文本"),
        ("arrow", "箭头"),
        ("rect", "矩形"),
        ("ellipse", "椭圆"),
        ("polygon", "多边形"),
        ("freehand", "手绘"),
        ("image", "图片"),
        ("north_arrow", "指北针"),
        ("scale_bar", "比例尺"),
    )

    def _build_free_toolbar(self) -> None:
        tb = self.addToolBar("Free Graphics")
        tb.addWidget(QLabel(" 工具："))
        self._tool_combo = QComboBox()
        for mode_id, label in self._TOOL_MODES:
            self._tool_combo.addItem(label, mode_id)
        self._tool_combo.currentIndexChanged.connect(self._on_tool_changed)
        tb.addWidget(self._tool_combo)

    def _on_tool_changed(self) -> None:
        mode = self._tool_combo.currentData()
        self.set_tool_mode(mode)

    def current_tool_mode(self) -> str:
        return self._tool_mode

    def set_tool_mode(self, mode: str) -> None:
        self._tool_mode = mode
        self._placement.set_mode(mode)
        idx = next(
            (i for i, (m, _) in enumerate(self._TOOL_MODES) if m == mode), 0
        )
        self._tool_combo.blockSignals(True)
        self._tool_combo.setCurrentIndex(idx)
        self._tool_combo.blockSignals(False)
        # In placement mode the view must not steal clicks for selection.
        for item in self._scene.items():
            item.setFlag(
                item.GraphicsItemFlag.ItemIsMovable, mode == "select"
            )

    def _pick_image_path(self) -> str:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", "Images (*.png *.jpg *.jpeg *.bmp *.svg)"
        )
        return path or ""

    def _scene_pos_from_event(self, event) -> QPointF | None:
        """Scene-coordinate position of a mouse event.

        PySide6: ``QGraphicsSceneMouseEvent`` carries ``scenePos()`` directly
        (its ``pos()`` is item-relative), while raw widget mouse events must
        be mapped through the view.
        """
        scene_pos = getattr(event, "scenePos", None)
        if scene_pos is not None:
            return scene_pos()
        pos = getattr(event, "pos", None)
        if pos is not None:
            return self._view.mapToScene(pos())
        return None

    def eventFilter(self, obj, event) -> bool:
        from PySide6.QtCore import QEvent
        if obj is not self._view and obj is not self._view.viewport():
            return False
        et = event.type()
        ctrl = self._placement
        if ctrl.mode == "select":
            return False
        if et in (QEvent.Type.GraphicsSceneMousePress, QEvent.Type.MouseButtonPress):
            button = event.button() if hasattr(event, "button") else Qt.MouseButton.NoButton
            if button != Qt.MouseButton.LeftButton:
                return False  # right-click keeps the item context menu
            pos = self._scene_pos_from_event(event)
            if pos is not None:
                ctrl.begin_click(pos)
                return True
        elif et in (QEvent.Type.GraphicsSceneMouseMove, QEvent.Type.MouseMove):
            pos = self._scene_pos_from_event(event)
            if pos is not None:
                ctrl.add_point(pos)
                return True
        elif et in (QEvent.Type.GraphicsSceneMouseRelease, QEvent.Type.MouseButtonRelease):
            pos = self._scene_pos_from_event(event)
            if pos is not None:
                ctrl.end_click(pos)
                return True
        elif et in (QEvent.Type.GraphicsSceneMouseDoubleClick, QEvent.Type.MouseButtonDblClick):
            ctrl.finish_polygon()
            return True
        return False

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._placement.cancel()
            self.set_tool_mode("select")
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._placement.finish_polygon()
            return
        if event.key() == Qt.Key.Key_Delete:
            for it in list(self._scene.selectedItems()):
                self._scene.removeItem(it)
            return
        super().keyPressEvent(event)

    # -- property panel selection sync (Task 8) ------------------------

    def _on_selection_changed(self) -> None:
        # Guard against the scene's C++ object being destroyed while the
        # window is being torn down (shiboken would raise RuntimeError on a
        # deleted wrapper when selectionChanged fires during destruction).
        import shiboken6
        if not shiboken6.isValid(self._scene):
            return
        from geoviz_paleo_map.cartography.items.free.base import FreeGraphicsItem
        free_items = [
            it for it in self._scene.selectedItems()
            if isinstance(it, FreeGraphicsItem)
        ]
        self._property_panel.set_item(free_items[0] if free_items else None)
