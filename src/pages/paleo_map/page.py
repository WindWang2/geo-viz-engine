import json
import math
import os
from PySide6.QtCore import QPointF, QRectF, Qt, Signal, QSize
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QStackedWidget, QMessageBox, QComboBox,
    QSplitter, QDialog, QRadioButton, QButtonGroup, QDialogButtonBox,
    QFrame, QCheckBox, QScrollArea, QAbstractButton
)

from geoviz_paleo_map import PaleoMapCanvas
from geoviz_paleo_map.hierarchy import FaciesHierarchy

from src.pages.paleo_map.loader import PaleoDataLoader
from src.utils.paths import get_data_dir, get_resources_dir


class ToggleSwitch(QAbstractButton):
    """Azurite-style toggle switch (white track / accent thumb)."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._label = text
        self._track_w = 30
        self._track_h = 16
        self._gap = 8
        self.setMinimumHeight(22)

    def sizeHint(self) -> QSize:
        fm = self.fontMetrics()
        return QSize(self._track_w + self._gap + fm.horizontalAdvance(self._label) + 4, max(22, self._track_h + 4))

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Track
        track_x = 0
        track_y = (self.height() - self._track_h) // 2
        track_rect = QRectF(track_x, track_y, self._track_w, self._track_h)
        if self.isChecked():
            p.setBrush(QBrush(QColor("#1f66d4")))
            p.setPen(QPen(QColor("#1f66d4"), 1))
        else:
            p.setBrush(QBrush(QColor("#ffffff")))
            p.setPen(QPen(QColor("#d3dbe6"), 1))
        p.drawRoundedRect(track_rect, self._track_h / 2, self._track_h / 2)

        # Thumb
        thumb_d = self._track_h - 4
        thumb_y = track_y + 2
        thumb_x = track_x + (self._track_w - thumb_d - 2) if self.isChecked() else track_x + 2
        if self.isChecked():
            p.setBrush(QBrush(QColor("#ffffff")))
            p.setPen(Qt.PenStyle.NoPen)
        else:
            p.setBrush(QBrush(QColor("#92a0b0")))
            p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(thumb_x, thumb_y, thumb_d, thumb_d))

        # Label
        if self._label:
            p.setPen(QColor("#586878"))
            font = self.font()
            font.setPointSizeF(9.5)
            p.setFont(font)
            text_rect = QRectF(self._track_w + self._gap, 0, self.width() - self._track_w - self._gap, self.height())
            p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._label)


def _load_well_markers() -> list[dict]:
    """Load wells in {name, lng, lat} format for PaleoMapCanvas."""
    try:
        path = get_data_dir() / "well_coordinates.json"
        if not path.exists():
            return []
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return [
            {"name": w["well_name"], "lng": w["longitude"], "lat": w["latitude"]}
            for w in data.get("wells", [])
        ]
    except (OSError, KeyError, json.JSONDecodeError):
        return []


class PaleoMapPage(QWidget):
    def _get_ui_icon(self, name: str) -> QIcon:
        """Resolve icon from project resources."""
        path = get_resources_dir() / "icons" / "ui" / name
        if path.exists():
            return QIcon(str(path))
        return QIcon()

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self._periods: dict[str, list[dict]] = {}
        self._hierarchies: dict[str, FaciesHierarchy] = {}
        self._multi_file_periods: dict[str, list[str]] = {}  # period -> [file_paths] for sibling discovery
        self._current_period = ""
        self._coord_format = "DD"  # "DD" or "DMS"

        # Subscribe to global coordinate format changes
        from src.utils.preferences import get_preference_bus
        get_preference_bus().coordinate_format_changed.connect(self._apply_coordinate_format)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        # 1. Empty State
        self.empty_widget = QWidget()
        self.empty_widget.setStyleSheet("background: #f4f7fb;")
        empty_layout = QVBoxLayout(self.empty_widget)
        drop_area = QLabel("拖拽古地理 GeoJSON / CSV 文件到此处\n或点击加载")
        drop_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_area.setStyleSheet("""
            QLabel {
                border: 2px dashed #cbd5e1; border-radius: 12px;
                background: #ffffff; color: #586878;
                font-size: 16px; padding: 40px;
            }
            QLabel:hover { border-color: #1f66d4; color: #1f66d4; background: #e9effa; }
        """)
        drop_area.mousePressEvent = lambda e: self._on_load_clicked()
        empty_layout.addStretch()
        empty_layout.addWidget(drop_area, 0, Qt.AlignmentFlag.AlignCenter)
        empty_layout.addStretch()
        self.stack.addWidget(self.empty_widget)

        # 2. Map State
        self.map_container = QWidget()
        map_layout = QVBoxLayout(self.map_container)
        map_layout.setContentsMargins(0, 0, 0, 0)
        map_layout.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setStyleSheet("background: #ffffff; border-bottom: 1px solid #e5eaf1;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(16, 8, 16, 8)
        tb_layout.setSpacing(12)

        load_btn = QPushButton(" 加载")
        load_btn.setIcon(self._get_ui_icon("upload.svg"))
        load_btn.setToolTip("加载 GeoJSON 或 CSV 文件 (支持拖拽)")
        load_btn.clicked.connect(self._on_load_clicked)
        load_btn.setStyleSheet(
            "QPushButton { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px; padding: 5px 12px; color: #1a2433; }"
            "QPushButton:hover { background: #f1f4f9; }"
        )

        self._period_combo = QComboBox()
        self._period_combo.setToolTip("选择地质时期")
        self._period_combo.currentTextChanged.connect(self._on_period_changed)
        self._period_combo.setStyleSheet(
            "QComboBox { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px; padding: 4px 10px; color: #1a2433; min-width: 120px; }"
            "QComboBox:focus { border: 1px solid #1f66d4; }"
        )

        tb_layout.addWidget(load_btn)
        tb_layout.addWidget(QLabel("时期:"))
        tb_layout.addWidget(self._period_combo)

        # Add a Level Lock dropdown
        tb_layout.addWidget(QLabel("层级锁定:"))
        self._level_lock_combo = QComboBox()
        self._level_lock_combo.setToolTip("锁定地图图层级别（自动表示根据比例尺切换）")
        self._level_lock_combo.addItems(["自动", "相", "亚相", "微相"])
        self._level_lock_combo.currentTextChanged.connect(self._on_level_lock_changed)
        self._level_lock_combo.setStyleSheet(
            "QComboBox { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px; padding: 4px 10px; color: #1a2433; min-width: 80px; }"
        )
        tb_layout.addWidget(self._level_lock_combo)

        self._edit_btn = QPushButton(" 编辑模式")
        self._edit_btn.setCheckable(True)
        self._edit_btn.setIcon(self._get_ui_icon("palette.svg"))
        self._edit_btn.setToolTip("切换编辑模式 (E)")
        self._edit_btn.clicked.connect(self._toggle_edit_mode)
        self._edit_btn.setStyleSheet(
            "QPushButton { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px; padding: 5px 12px; color: #1a2433; }"
            "QPushButton:hover { background: #f1f4f9; }"
            "QPushButton:checked { background: #e9effa; border-color: #1f66d4; color: #1f66d4; font-weight: bold; }"
        )

        self._save_btn = QPushButton(" 保存")
        self._save_btn.setIcon(self._get_ui_icon("check.svg"))
        self._save_btn.setToolTip("保存编辑 (Ctrl+S)")
        self._save_btn.clicked.connect(self._on_save_clicked)
        self._save_btn.setVisible(False)
        self._save_btn.setStyleSheet(
            "QPushButton { background: #1f66d4; color: #ffffff; border: none; border-radius: 6px; padding: 5px 12px; font-weight: bold; }"
            "QPushButton:hover { background: #1a54b2; }"
        )

        tb_layout.addWidget(self._edit_btn)
        tb_layout.addWidget(self._save_btn)
        tb_layout.addStretch()

        map_layout.addWidget(toolbar)

        # High-Fidelity Split Layout: Canvas (left) and Sidebar (right)
        self.map_content_area = QWidget()
        content_layout = QHBoxLayout(self.map_content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Left area container
        self.map_view_container = QWidget()
        map_view_layout = QVBoxLayout(self.map_view_container)
        map_view_layout.setContentsMargins(0, 0, 0, 0)
        map_view_layout.setSpacing(0)

        self.map_view = PaleoMapCanvas(parent=self)
        self.map_view.edit_mode_changed.connect(self._on_edit_mode_changed)
        self.map_view.selection_changed.connect(self._on_selection_changed)
        map_view_layout.addWidget(self.map_view)
        content_layout.addWidget(self.map_view_container, 1)

        # Floating Toolbar Overlay (top-right of canvas container)
        self.float_tb = QFrame(self.map_view_container)
        self.float_tb.setStyleSheet(
            "QFrame { background: rgba(255, 255, 255, 0.95); border: 1px solid #e5eaf1; border-radius: 8px; }"
        )
        tb_layout_float = QVBoxLayout(self.float_tb)
        tb_layout_float.setContentsMargins(6, 6, 6, 6)
        tb_layout_float.setSpacing(6)

        self.btn_zoom_in = QPushButton("＋")
        self.btn_zoom_out = QPushButton("－")
        self.btn_fit = QPushButton("⛶")
        
        tb_btn_style = (
            "QPushButton { border: none; background: transparent; color: #586878; font-size: 14px; min-width: 28px; min-height: 28px; border-radius: 4px; }"
            "QPushButton:hover { background: #f1f4f9; color: #1f66d4; }"
        )
        for btn in [self.btn_zoom_in, self.btn_zoom_out, self.btn_fit]:
            btn.setStyleSheet(tb_btn_style)
            tb_layout_float.addWidget(btn)

        # Wire floating actions
        self.btn_zoom_in.clicked.connect(lambda: self.map_view.set_zoom(self.map_view.zoom * 1.2))
        self.btn_zoom_out.clicked.connect(lambda: self.map_view.set_zoom(self.map_view.zoom / 1.2))
        self.btn_fit.clicked.connect(lambda: self.map_view.fit_viewport_to_data())

        # 3. Right Sidebar Frame (230px wide)
        self.right_sidebar = QFrame()
        self.right_sidebar.setFixedWidth(230)
        self.right_sidebar.setStyleSheet(
            "QFrame { background: #ffffff; border-left: 1px solid #e5eaf1; }"
        )
        sidebar_layout = QVBoxLayout(self.right_sidebar)
        sidebar_layout.setContentsMargins(16, 16, 16, 16)
        sidebar_layout.setSpacing(16)

        # Section 1: Legend Title
        self.legend_title = QLabel("沉积相图例")
        self.legend_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #1a2433; border: none;")
        sidebar_layout.addWidget(self.legend_title)

        # Facies Color Swatch List inside QScrollArea
        self.legend_scroll = QScrollArea()
        self.legend_scroll.setWidgetResizable(True)
        self.legend_scroll.setStyleSheet("QScrollArea { border: none; background: #ffffff; }")
        self.legend_content = QWidget()
        self.legend_content.setStyleSheet("background: #ffffff;")
        self.legend_layout = QVBoxLayout(self.legend_content)
        self.legend_layout.setContentsMargins(0, 0, 0, 0)
        self.legend_layout.setSpacing(8)
        self.legend_layout.addStretch()
        self.legend_scroll.setWidget(self.legend_content)
        sidebar_layout.addWidget(self.legend_scroll, 1)

        # Section 2: Layer Controls Title
        self.layer_controls_title = QLabel("图层控制")
        self.layer_controls_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #1a2433; border: none; margin-top: 12px;")
        sidebar_layout.addWidget(self.layer_controls_title)

        # Custom Switches (White/transparent Azurite Toggle Switch)
        self.toggle_wells = ToggleSwitch("显示井位标定")
        self.toggle_wells.setChecked(True)
        sidebar_layout.addWidget(self.toggle_wells)

        self.toggle_labels = ToggleSwitch("显示沉积相标注")
        self.toggle_labels.setChecked(True)
        sidebar_layout.addWidget(self.toggle_labels)

        # Wire layer toggles
        self.toggle_wells.toggled.connect(self._on_layer_toggled)
        self.toggle_labels.toggled.connect(self._on_layer_toggled)

        # Section 3: Bottom "导出图件" Button
        self.export_map_btn = QPushButton("导出图件")
        self.export_map_btn.setIcon(self._get_ui_icon("export.svg"))
        self.export_map_btn.setStyleSheet(
            "QPushButton { background: #ffffff; border: 1px solid #1f66d4; color: #1f66d4; font-weight: bold; border-radius: 6px; padding: 8px 12px; }"
            "QPushButton:hover { background: #e9effa; }"
        )
        self.export_map_btn.clicked.connect(self._on_export_clicked)
        sidebar_layout.addWidget(self.export_map_btn)

        content_layout.addWidget(self.right_sidebar)
        map_layout.addWidget(self.map_content_area, 1)

        self.stack.addWidget(self.map_container)
        self.stack.setCurrentWidget(self.empty_widget)

    def _on_layer_toggled(self):
        show_wells = self.toggle_wells.isChecked()
        show_labels = self.toggle_labels.isChecked()
        # Find active layers in PaleoMapCanvas and show/hide them accordingly
        for layer in self.map_view.layers:
            cls_name = layer.__class__.__name__
            if "Well" in cls_name:
                layer.visible = show_wells
            elif "Label" in cls_name:
                layer.visible = show_labels
        self.map_view.update()

    def _apply_coordinate_format(self, fmt: str):
        """Receive global coordinate-format broadcasts and refresh display."""
        if fmt not in ("DD", "DMS"):
            return
        self._coord_format = fmt
        # Trigger repaint so any coord-aware layer can refresh
        if hasattr(self, "map_view"):
            self.map_view.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Position floating toolbar in top-right corner of map canvas area
        if hasattr(self, "float_tb") and self.map_view.width() > 100:
            self.float_tb.setGeometry(
                self.map_view_container.width() - 44 - 16,
                16,
                44,
                112
            )

    # --- Period Management ---

    def _add_periods(self, periods: dict[str, list[dict]]):
        for name, features in periods.items():
            self._periods.setdefault(name, []).extend(features)

        self._period_combo.blockSignals(True)
        self._period_combo.clear()
        for name in self._periods:
            self._period_combo.addItem(name)

        if self._current_period not in self._periods and self._period_combo.count() > 0:
            self._period_combo.setCurrentIndex(0)
        self._period_combo.blockSignals(False)

        if self._period_combo.count() > 0:
            self._on_period_changed(self._period_combo.currentText())

    def _on_period_changed(self, period_name: str):
        if not period_name or period_name not in self._periods:
            return
        self._current_period = period_name

        features = self._periods.get(period_name)
        if features is not None:
            hierarchy = self._hierarchies.get(period_name)
            if hierarchy is not None:
                self.map_view.load_hierarchy(hierarchy,
                                             period_name=period_name,
                                             wells=_load_well_markers())
            else:
                self.map_view.load_features(features,
                                            period_name=period_name,
                                            wells=_load_well_markers())
            # Dynamically update right sidebar facies color swatches
            self._update_facies_legend()

    def _update_facies_legend(self):
        # Clear existing legend swatches
        while self.legend_layout.count() > 0:
            item = self.legend_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # Query colors and names from active model or facies colors
        model = self.map_view.topology_model
        if not model:
            return
        
        # Build swatches
        facies_set = set()
        for ref in model.all_features().values():
            facies = ref.properties.get("facies")
            if facies:
                facies_set.add(facies)

        for facies in sorted(facies_set):
            color = "#cbd5e1"
            if hasattr(self.map_view, "_resolver"):
                try:
                    color = self.map_view._resolver.resolve(facies).base_color.name()
                except Exception:
                    pass
            
            row = QFrame()
            row.setStyleSheet("QFrame { background: #ffffff; border: none; }")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(4, 4, 4, 4)
            row_layout.setSpacing(10)
            
            swatch = QFrame()
            swatch.setFixedSize(14, 14)
            swatch.setStyleSheet(f"border-radius: 3px; background: {color}; border: 1px solid #cbd5e1;")
            
            lbl = QLabel(facies)
            lbl.setStyleSheet("color: #1a2433; font-size: 11.5px; border: none;")
            
            row_layout.addWidget(swatch)
            row_layout.addWidget(lbl)
            row_layout.addStretch()
            
            self.legend_layout.addWidget(row)
        
        self.legend_layout.addStretch()

    def _on_level_lock_changed(self, text: str):
        level_map = {
            "自动": "",
            "相": "facies",
            "亚相": "sub_facies",
            "微相": "micro_facies"
        }
        level = level_map.get(text, "")
        self.map_view.set_locked_level(level)

    # --- Edit Mode ---

    def _toggle_edit_mode(self, checked: bool) -> None:
        self.map_view.edit_mode = checked
        self._save_btn.setVisible(checked)

    def _on_save_clicked(self) -> None:
        model = self.map_view.topology_model
        if model is None:
            return
        self._save_as(model)

    def _save_as(self, model) -> None:
        from geoviz_paleo_map.save_export import save_geojson
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 GeoJSON", "paleo_edited.geojson", "GeoJSON (*.geojson *.json)")
        if path:
            save_geojson(model, path)
            QMessageBox.information(self, "保存成功", f"已保存到: {path}")

    def _on_edit_mode_changed(self, active: bool) -> None:
        self._edit_btn.setChecked(active)

    def _on_selection_changed(self, feature_id: str) -> None:
        pass  # Future: update properties panel

    # --- File Loading ---

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(u.toLocalFile().lower().endswith(('.json', '.geojson', '.csv', '.xlsx')) for u in urls):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            paths = [u.toLocalFile() for u in urls
                     if u.toLocalFile().lower().endswith(('.json', '.geojson', '.csv', '.xlsx'))]
            if paths:
                self._load_files(paths)

    def _on_load_clicked(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择古地理数据文件", "",
            "数据文件 (*.json *.geojson *.csv *.xlsx)"
        )
        if file_paths:
            self._load_files(file_paths)

    def _load_files(self, file_paths: list[str]):
        for fp in file_paths:
            if not os.path.exists(fp):
                QMessageBox.warning(self, "错误", f"文件不存在：{fp}")
                return

        from PySide6.QtGui import QCursor
        self.setCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            if len(file_paths) == 1:
                # Single file: use auto-discovery for siblings
                periods = self._load_single_file(file_paths[0])
            else:
                # Multiple files: load all, merge by period, build hierarchy
                periods = self._load_multi_files(file_paths)

            if not periods or all(len(f) == 0 for f in periods.values()):
                QMessageBox.information(self, "提示",
                    "文件中没有有效的地理数据。\n\n"
                    "GeoJSON 需包含 FeatureCollection 且 features 非空。\n"
                    "CSV 需含 period, facies 列及 geometry (WKT) 或 lon_min/lon_max/lat_min/lat_max 列。")
                return

            self.stack.setCurrentWidget(self.map_container)
        except Exception as e:
            QMessageBox.critical(self, "加载失败", f"无法加载数据:\n{e}")
        finally:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def _load_single_file(self, file_path: str) -> dict[str, list[dict]]:
        """Load one file, auto-discover siblings for hierarchy."""
        fmt = PaleoDataLoader.detect_format(file_path)
        if fmt is None:
            QMessageBox.critical(self, "格式错误", "不支持的文件格式。请使用 GeoJSON 或 CSV 文件。")
            return {}

        siblings = PaleoDataLoader.discover_sibling_levels(file_path)
        if len(siblings) > 1:
            return self._load_multi_files(list(siblings.values()))

        loader = PaleoDataLoader(file_path)
        periods = loader.load()
        self._add_periods(periods)
        return periods

    def _load_multi_files(self, file_paths: list[str]) -> dict[str, list[dict]]:
        """Load multiple files, merge by period, build hierarchy."""
        merged: dict[str, list[dict]] = {}
        for fp in file_paths:
            fmt = PaleoDataLoader.detect_format(fp)
            if fmt is None:
                continue
            loader = PaleoDataLoader(fp)
            for period_name, features in loader.load().items():
                merged.setdefault(period_name, []).extend(features)
        for period_name, feats in merged.items():
            self._hierarchies[period_name] = FaciesHierarchy.from_features(feats)
        self._add_periods(merged)
        return merged

    # --- Export ---

    def _on_export_clicked(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("导出地图")
        layout = QVBoxLayout(dialog)

        group = QButtonGroup(dialog)
        rb_svg = QRadioButton("SVG (嵌入栅格)")
        rb_pdf = QRadioButton("PDF (矢量)")
        rb_png = QRadioButton("PNG (栅格)")
        rb_png.setChecked(True)
        group.addButton(rb_svg)
        group.addButton(rb_pdf)
        group.addButton(rb_png)
        layout.addWidget(rb_svg)
        layout.addWidget(rb_pdf)
        layout.addWidget(rb_png)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        if rb_svg.isChecked():
            self._export_svg()
        elif rb_pdf.isChecked():
            self._export_pdf()
        else:
            self._export_png()

    def _export_svg(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出 SVG", "paleomap.svg", "SVG (*.svg)")
        if not path:
            return
        if not path.lower().endswith(".svg"):
            path += ".svg"
        from geoviz_paleo_map.export_professional import export_professional_figure
        try:
            export_professional_figure(
                self.map_view, path, "svg",
                title=self._figure_title(),
            )
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"SVG 导出失败:\n{e}")

    def _export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出 PDF", "paleomap.pdf", "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        from geoviz_paleo_map.export_professional import export_professional_figure
        try:
            export_professional_figure(
                self.map_view, path, "pdf",
                title=self._figure_title(),
            )
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"PDF 导出失败:\n{e}")

    def _export_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出 PNG", "paleomap.png", "PNG (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        from geoviz_paleo_map.export_professional import export_professional_figure
        try:
            export_professional_figure(
                self.map_view, path, "png",
                title=self._figure_title(),
            )
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"PNG 导出失败:\n{e}")

    def _figure_title(self) -> str:
        period = self._current_period or "古地理图"
        return f"{period} 古地理相图"
