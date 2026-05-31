import json
import math
import os
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QStackedWidget, QMessageBox, QComboBox,
    QSplitter, QDialog, QRadioButton, QButtonGroup, QDialogButtonBox,
)

from geoviz_paleo_map import PaleoMapCanvas
from geoviz_paleo_map.hierarchy import FaciesHierarchy
from geoviz_paleo_map.shared_chrome_panel import SharedChromePanel

from src.pages.paleo_map.loader import PaleoDataLoader
from src.utils.paths import get_data_dir




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
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self._periods: dict[str, list[dict]] = {}
        self._hierarchies: dict[str, FaciesHierarchy] = {}
        self._multi_file_periods: dict[str, list[str]] = {}  # period -> [file_paths] for sibling discovery
        self._current_period = ""
        self._compare_mode = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        # 1. Empty State
        self.empty_widget = QWidget()
        self.empty_widget.setStyleSheet("background: #f7fafc;")
        empty_layout = QVBoxLayout(self.empty_widget)
        drop_area = QLabel("拖拽古地理 GeoJSON / CSV 文件到此处\n或点击加载")
        drop_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_area.setStyleSheet("""
            QLabel {
                border: 2px dashed #cbd5e1; border-radius: 8px;
                background: #ffffff; color: #64748b;
                font-size: 16px; padding: 40px;
            }
            QLabel:hover { border-color: #3182ce; color: #3182ce; background: #ebf8ff; }
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
        toolbar.setStyleSheet("background: #f8fafc; border-bottom: 1px solid #e2e8f0;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(10, 6, 10, 6)

        load_btn = QPushButton("加载")
        load_btn.setToolTip("加载 GeoJSON 或 CSV 文件 (支持拖拽)")
        load_btn.setStyleSheet("QPushButton{background:#f1f5f9;color:#334155;border:1px solid #cbd5e1;border-radius:4px;padding:6px 12px;}QPushButton:hover{background:#e2e8f0;}QPushButton:pressed{background:#cbd5e1;}")
        load_btn.clicked.connect(self._on_load_clicked)

        self._period_combo = QComboBox()
        self._period_combo.setToolTip("选择地质时期")
        self._period_combo.setStyleSheet("QComboBox{padding:4px 8px;border:1px solid #cbd5e1;border-radius:4px;}")
        self._period_combo.currentTextChanged.connect(self._on_period_changed)

        self._compare_btn = QPushButton("对比")
        self._compare_btn.setToolTip("并排对比两个时期（需至少2个时期数据）")
        self._compare_btn.setCheckable(True)
        self._compare_btn.setStyleSheet("QPushButton{background:#f1f5f9;color:#334155;border:1px solid #cbd5e1;border-radius:4px;padding:6px 12px;}QPushButton:hover{background:#e2e8f0;}QPushButton:checked{background:#dbeafe;color:#1d4ed8;}QPushButton:pressed{background:#cbd5e1;}")
        self._compare_btn.clicked.connect(self._toggle_compare)

        export_btn = QPushButton("导出")
        export_btn.setToolTip("导出为 SVG / PDF / PNG")
        export_btn.setStyleSheet("QPushButton{background:#2563eb;color:#fff;border:none;border-radius:4px;padding:6px 14px;font-weight:600;}QPushButton:hover{background:#1d4ed8;}QPushButton:pressed{background:#1e40af;}")
        export_btn.clicked.connect(self._on_export_clicked)

        tb_layout.addWidget(load_btn)
        tb_layout.addWidget(QLabel("时期:"))
        tb_layout.addWidget(self._period_combo)
        tb_layout.addWidget(self._compare_btn)

        self._edit_btn = QPushButton("编辑模式")
        self._edit_btn.setCheckable(True)
        self._edit_btn.setToolTip("切换编辑模式 (E)")
        self._edit_btn.setStyleSheet(
            "QPushButton{background:#f1f5f9;color:#334155;border:1px solid #cbd5e1;"
            "border-radius:4px;padding:6px 12px;}"
            "QPushButton:hover{background:#e2e8f0;}"
            "QPushButton:checked{background:#dbeafe;color:#1d4ed8;border-color:#93c5fd;}"
        )
        self._edit_btn.clicked.connect(self._toggle_edit_mode)

        self._save_btn = QPushButton("保存")
        self._save_btn.setToolTip("保存编辑 (Ctrl+S)")
        self._save_btn.setStyleSheet(
            "QPushButton{background:#059669;color:#fff;border:none;border-radius:4px;"
            "padding:6px 14px;font-weight:600;}"
            "QPushButton:hover{background:#047857;}"
        )
        self._save_btn.clicked.connect(self._on_save_clicked)
        self._save_btn.setVisible(False)

        tb_layout.addWidget(self._edit_btn)
        tb_layout.addWidget(self._save_btn)

        tb_layout.addStretch()
        tb_layout.addWidget(export_btn)

        map_layout.addWidget(toolbar)

        # Map view area (single or split)
        self._map_layout = QVBoxLayout()
        self._map_layout.setContentsMargins(0, 0, 0, 0)
        self.map_view = PaleoMapCanvas(parent=self)
        self._map_layout.addWidget(self.map_view)
        self.map_view.edit_mode_changed.connect(self._on_edit_mode_changed)
        self.map_view.selection_changed.connect(self._on_selection_changed)
        map_layout.addLayout(self._map_layout, 1)

        self.stack.addWidget(self.map_container)
        self.stack.setCurrentWidget(self.empty_widget)



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


        if self._compare_mode and hasattr(self, 'map_view_b'):
            other_periods = [p for p in self._periods if p != period_name]
            if other_periods:
                other = other_periods[0]
                features_b = self._periods.get(other)
                if features_b is not None:
                    hierarchy_b = self._hierarchies.get(other)
                    if hierarchy_b is not None:
                        self.map_view_b.load_hierarchy(hierarchy_b,
                                                       period_name=other,
                                                       wells=_load_well_markers())
                    else:
                        self.map_view_b.load_features(features_b,
                                                      period_name=other,
                                                      wells=_load_well_markers())

    # --- Compare Mode ---

    def _toggle_compare(self, checked: bool):
        if checked and len(self._periods) < 2:
            self._compare_btn.setChecked(False)
            QMessageBox.information(self, "提示", "对比模式需要至少加载2个时期的数据。")
            return
        self._compare_mode = checked
        if checked:
            self._start_compare()
        else:
            self._stop_compare()

    def _start_compare(self):
        old_view = self.map_view
        compare_host = QWidget()
        h_layout = QHBoxLayout(compare_host)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)
        self.map_view = PaleoMapCanvas(parent=self, show_chrome=False)
        self.map_view_b = PaleoMapCanvas(parent=self, show_chrome=False)
        self._shared_chrome = SharedChromePanel(self.map_view, self.map_view_b,
                                                parent=compare_host)
        h_layout.addWidget(self.map_view, 1)
        h_layout.addWidget(self._shared_chrome)
        h_layout.addWidget(self.map_view_b, 1)
        self._compare_host = compare_host
        self._map_layout.addWidget(compare_host)
        old_view.deleteLater()
        self._on_period_changed(self._current_period)

    def _stop_compare(self):
        if hasattr(self, 'map_view_b'):
            try:
                self.map_view_b.deleteLater()
            except RuntimeError:
                pass
            del self.map_view_b
        if hasattr(self, '_shared_chrome'):
            del self._shared_chrome
        if hasattr(self, '_compare_host'):
            self._compare_host.setParent(None)
            del self._compare_host
        if hasattr(self, '_splitter'):
            self._splitter.setParent(None)
            del self._splitter
        self.map_view = PaleoMapCanvas(parent=self)
        self._map_layout.addWidget(self.map_view)
        self._on_period_changed(self._current_period)

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
