import json
import os
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QStackedWidget, QMessageBox, QComboBox,
    QSplitter, QDialog, QRadioButton, QButtonGroup, QDialogButtonBox,
    QSpinBox,
)
from PySide6.QtCore import QUrl

from src.renderers.paleo_map_renderer import PaleoMapRenderer
from src.data.paleo_loader import PaleoDataLoader


class PaleoMapPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self._periods: dict[str, list[dict]] = {}
        self._period_geojson_files: dict[str, str] = {}
        self._current_period = ""
        self._compare_mode = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

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
        load_btn.setStyleSheet("QPushButton{background:#f1f5f9;color:#334155;border:1px solid #cbd5e1;border-radius:4px;padding:6px 12px;}QPushButton:hover{background:#e2e8f0;}")
        load_btn.clicked.connect(self._on_load_clicked)

        self._period_combo = QComboBox()
        self._period_combo.setToolTip("选择地质时期")
        self._period_combo.setStyleSheet("QComboBox{padding:4px 8px;border:1px solid #cbd5e1;border-radius:4px;}")
        self._period_combo.currentTextChanged.connect(self._on_period_changed)

        self._compare_btn = QPushButton("对比")
        self._compare_btn.setToolTip("并排对比两个时期（需至少2个时期数据）")
        self._compare_btn.setCheckable(True)
        self._compare_btn.setStyleSheet("QPushButton{background:#f1f5f9;color:#334155;border:1px solid #cbd5e1;border-radius:4px;padding:6px 12px;}QPushButton:checked{background:#dbeafe;color:#1d4ed8;}")
        self._compare_btn.clicked.connect(self._toggle_compare)

        export_btn = QPushButton("导出")
        export_btn.setToolTip("导出为 SVG / PDF / PNG")
        export_btn.setStyleSheet("QPushButton{background:#2563eb;color:#fff;border:none;border-radius:4px;padding:6px 14px;font-weight:600;}QPushButton:hover{background:#1d4ed8;}")
        export_btn.clicked.connect(self._on_export_clicked)

        tb_layout.addWidget(load_btn)
        tb_layout.addWidget(QLabel("时期:"))
        tb_layout.addWidget(self._period_combo)
        tb_layout.addWidget(self._compare_btn)
        tb_layout.addStretch()
        tb_layout.addWidget(export_btn)

        map_layout.addWidget(toolbar)

        # Map view area (single or split)
        self._map_layout = QVBoxLayout()
        self._map_layout.setContentsMargins(0, 0, 0, 0)
        self.map_view = PaleoMapRenderer(self)
        self._map_layout.addWidget(self.map_view)
        map_layout.addLayout(self._map_layout)

        self.stack.addWidget(self.map_container)
        self.stack.setCurrentWidget(self.empty_widget)

    # --- Period Management ---

    def _add_periods(self, periods: dict[str, list[dict]], geojson_files: dict[str, str]):
        # Clean up stale temp files from previous loads
        for name, path in list(self._period_geojson_files.items()):
            if name not in periods:
                try: os.unlink(path)
                except OSError: pass
                del self._period_geojson_files[name]

        for name, features in periods.items():
            self._periods[name] = features
            if name in geojson_files:
                self._period_geojson_files[name] = geojson_files[name]

        self._period_combo.blockSignals(True)
        self._period_combo.clear()
        for name in self._periods:
            self._period_combo.addItem(name)
        self._period_combo.blockSignals(False)

        if self._current_period not in self._periods and self._period_combo.count() > 0:
            self._period_combo.setCurrentIndex(0)
            self._on_period_changed(self._period_combo.currentText())

    def _on_period_changed(self, period_name: str):
        if not period_name or period_name not in self._periods:
            return
        self._current_period = period_name

        geojson_path = self._period_geojson_files.get(period_name)
        if geojson_path:
            self.map_view.load_geojson(geojson_path, period_name=period_name)

        if self._compare_mode and hasattr(self, 'map_view_b'):
            other_periods = [p for p in self._periods if p != period_name]
            if other_periods:
                other = other_periods[0]
                path_b = self._period_geojson_files.get(other)
                if path_b:
                    self.map_view_b.load_geojson(path_b, period_name=other)

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
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self.map_view = PaleoMapRenderer(self)
        self.map_view_b = PaleoMapRenderer(self)
        self._splitter.addWidget(self.map_view)
        self._splitter.addWidget(self.map_view_b)
        self._map_layout.addWidget(self._splitter)
        old_view.deleteLater()
        self._on_period_changed(self._current_period)

    def _stop_compare(self):
        if hasattr(self, 'map_view_b'):
            try:
                self.map_view_b.deleteLater()
            except RuntimeError:
                pass  # C++ object already deleted by Qt parent cleanup
            del self.map_view_b
        if hasattr(self, '_splitter'):
            self._splitter.setParent(None)
            del self._splitter
        self.map_view = PaleoMapRenderer(self)
        self._map_layout.addWidget(self.map_view)
        self._on_period_changed(self._current_period)

    # --- File Loading ---

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith(('.json', '.geojson', '.csv', '.xlsx')):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            self._load_file(urls[0].toLocalFile())

    def _on_load_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择古地理数据文件", "",
            "数据文件 (*.json *.geojson *.csv *.xlsx)"
        )
        if file_path:
            self._load_file(file_path)

    def _load_file(self, file_path: str):
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "错误", "文件不存在！")
            return

        from PySide6.QtGui import QCursor
        self.setCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            fmt = PaleoDataLoader.detect_format(file_path)
            if fmt == "csv":
                loader = PaleoDataLoader(file_path)
                periods = loader.load()
                geojson_files = self._write_period_geojsons(periods, file_path)
                self._add_periods(periods, geojson_files)
            elif fmt == "geojson":
                loader = PaleoDataLoader(file_path)
                periods = loader.load()
                geojson_files = self._write_period_geojsons(periods, file_path)
                self._add_periods(periods, geojson_files)
            else:
                QMessageBox.critical(self, "格式错误", "不支持的文件格式。请使用 GeoJSON 或 CSV 文件。")
                return

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

    def _write_period_geojsons(self, periods: dict, source_path: str) -> dict[str, str]:
        import tempfile
        result = {}
        for name, features in periods.items():
            geojson = {"type": "FeatureCollection", "features": features}
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".geojson", delete=False, encoding="utf-8",
                prefix=f"paleo_{name}_"
            )
            json.dump(geojson, tmp, ensure_ascii=False)
            tmp.close()
            result[name] = tmp.name
        return result

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

        pixmap = self.map_view.grab()
        import io
        buffer = io.BytesIO()
        pixmap.save(buffer, "PNG")
        import base64
        b64 = base64.b64encode(buffer.getvalue()).decode()
        svg_content = f'<svg xmlns="http://www.w3.org/2000/svg" width="{pixmap.width()}" height="{pixmap.height()}">'
        svg_content += f'<image href="data:image/png;base64,{b64}" width="{pixmap.width()}" height="{pixmap.height()}"/>'
        svg_content += '</svg>'
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg_content)

    def _export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出 PDF", "paleomap.pdf", "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        from PySide6.QtGui import QPageSize, QPageLayout
        from PySide6.QtPrintSupport import QPrinter
        pixmap = self.map_view.grab()
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFileName(path)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        page_size = QPageSize(QPageSize.PageSizeId.A4)
        printer.setPageSize(page_size)
        from PySide6.QtGui import QPainter
        painter = QPainter(printer)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()

    def _export_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出 PNG", "paleomap.png", "PNG (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        pixmap = self.map_view.grab()
        pixmap.save(path, "PNG")
