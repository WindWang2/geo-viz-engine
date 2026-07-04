from PySide6.QtCore import Qt, QThread, QObject, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QGroupBox, QListWidget, QAbstractItemView, QListWidgetItem,
    QMessageBox, QComboBox, QFileDialog
)
from src.utils.floating_progress import FloatingProgressOverlay
from src.data.well_registry import get_well_data, list_wells
from geoviz_well_log import build_qpainter_tracks
from geoviz_well_log.export_qpainter import export_svg as qpainter_export_svg
from geoviz_well_log.export_qpainter import export_pdf as qpainter_export_pdf
from geoviz_well_log.export_qpainter import export_png as qpainter_export_png
from geoviz_well_log.renderer.curve_track import CurveTrack
from src.pages.well_log.qpainter_widget import QPainterWidget


class PredictionWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, well_name, xls_path, current_data):
        super().__init__()
        self.well_name = well_name
        self.xls_path = xls_path
        self.current_data = current_data

    def run(self):
        try:
            import urllib.request
            import json
            import pandas as pd

            self.progress.emit(10, "正在准备预测数据...")

            depth_set = set()
            for curve in self.current_data.curves:
                depth_set.update(curve.depth)
            sorted_depths = sorted(list(depth_set))

            if not sorted_depths:
                self.error.emit("当前井无测井曲线深度数据！")
                return

            curve_maps = {}
            for curve in self.current_data.curves:
                curve_maps[curve.name] = dict(zip(curve.depth, curve.values))

            formation_items = self.current_data.intervals.formation if hasattr(self.current_data.intervals, 'formation') else []
            member_items = self.current_data.intervals.member if hasattr(self.current_data.intervals, 'member') else []
            lithology_items = self.current_data.intervals.lithology if hasattr(self.current_data.intervals, 'lithology') else []

            def find_interval_name(items, depth):
                for item in items:
                    if item.top <= depth <= item.bottom:
                        return item.name
                return ""

            rows = []
            for d in sorted_depths:
                row = {
                    "井号": self.well_name,
                    "深度": d,
                    "组": find_interval_name(formation_items, d) or "恩平组",
                    "段": find_interval_name(member_items, d) or "恩平一-二段",
                    "岩性": find_interval_name(lithology_items, d) or "泥岩"
                }
                for curve_name, mapping in curve_maps.items():
                    val = mapping.get(d, None)
                    row[curve_name] = val if (val == val and val is not None) else None
                rows.append(row)

            rows = [r for r in rows if r.get("GR") is not None]

            if not rows:
                self.error.emit("没有找到有效的GR曲线数据，无法进行预测！")
                return

            self.progress.emit(30, "正在调用 AI 模型推理...")

            payload = {
                "request_id": f"PUBLIC-TEST-{self.well_name}-{int(pd.Timestamp.now().timestamp())}",
                "well_id": self.well_name,
                "interval_top": min(r["深度"] for r in rows),
                "interval_bottom": max(r["深度"] for r in rows),
                "model_version_lithology": None,
                "model_version_microfacies": "single-well-facies-20260507-fold15-HZ27-5-3",
                "rows": rows
            }

            req = urllib.request.Request(
                "https://api-test.deeptime.world/api/v1/inference/single-well/json",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )

            with urllib.request.urlopen(req, timeout=120) as response:
                res_data = json.loads(response.read().decode("utf-8"))

            if not res_data or res_data.get("task_status") != "success":
                self.error.emit(f"推理未成功: {res_data.get('warnings', '未知错误')}")
                return

            self.progress.emit(70, "保存预测结果到 Excel...")

            microfacies = res_data.get("microfacies_results", [])
            if not microfacies:
                self.error.emit("未返回任何沉积相预测结果！")
                return

            records = []
            for item in microfacies:
                records.append({
                    "深度": item["depth"],
                    "预测相": item["label_name"],
                    "置信度": item["confidence"]
                })

            df_ai = pd.DataFrame(records)

            try:
                import openpyxl
                wb = openpyxl.load_workbook(self.xls_path)
                if "AI预测结果" in wb.sheetnames:
                    del wb["AI预测结果"]
                wb.save(self.xls_path)
                wb.close()
            except Exception as e:
                print(f"Failed to clear sheet using openpyxl: {e}")

            try:
                if not str(self.xls_path).lower().endswith(".xlsx"):
                    raise ValueError("仅支持向 .xlsx 格式的 Excel 追加 AI 预测结果。请先转换为 .xlsx 格式！")

                with pd.ExcelWriter(self.xls_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
                    df_ai.to_excel(writer, sheet_name="AI预测结果", index=False)
            except Exception as e:
                print(f"Failed to append sheet: {e}")
                raise RuntimeError(f"写入 Excel 失败（可能文件已被其他程序打开或格式不受支持）: {e}")

            self.progress.emit(100, "完成")
            self.finished.emit(records)
        except Exception as e:
            self.error.emit(f"请求发生异常: {str(e)}")


class _WellLogLoadWorker(QObject):
    """Background worker that loads a single well's data."""
    progress = Signal(int, str)
    finished = Signal(object)  # WellLogData
    error = Signal(str)

    def __init__(self, loader_fn, xls_path, well_name, parent=None):
        super().__init__(parent)
        self._loader_fn = loader_fn
        self._xls_path = xls_path
        self._well_name = well_name

    def run(self):
        try:
            self.progress.emit(10, "正在读取 Excel 数据...")
            data = self._loader_fn(self._xls_path, well_name=self._well_name)
            self.progress.emit(80, "正在构建轨道...")
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(f"加载失败: {e}")


class WellLogPage(QWidget):
    def _get_ui_icon(self, name: str) -> QIcon:
        """Resolve icon from project resources."""
        from src.utils.paths import get_resources_dir
        path = get_resources_dir() / "icons" / "ui" / name
        if path.exists():
            return QIcon(str(path))
        return QIcon()

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Toolbar
        self._toolbar = QWidget()
        self._toolbar.setStyleSheet("background: #faf9f5; border-bottom: 1px solid #e5eaf1;")
        toolbar_layout = QHBoxLayout(self._toolbar)
        toolbar_layout.setContentsMargins(16, 8, 16, 8)
        toolbar_layout.setSpacing(12)

        self._well_name_label = QLabel()
        self._well_name_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #1a2433;")
        toolbar_layout.addWidget(self._well_name_label)

        self._well_combo = QComboBox()
        self._well_combo.setFixedHeight(28)
        self._well_combo.setMinimumWidth(160)
        self._well_combo.addItem(" 选择测井...")
        for name in list_wells():
            self._well_combo.addItem(name)
        self._well_combo.currentTextChanged.connect(self._on_well_selected)
        self._well_combo.setStyleSheet(
            "QComboBox { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px; padding: 2px 10px; color: #1a2433; }"
            "QComboBox:focus { border: 1px solid #1f66d4; }"
        )
        toolbar_layout.addWidget(self._well_combo)

        # Depth range label
        self._depth_lbl = QLabel("深度范围: --")
        self._depth_lbl.setStyleSheet("font-size: 12px; color: #586878; font-weight: 500;")
        toolbar_layout.addWidget(self._depth_lbl)

        # Segmented buttons for Column style
        self._cols_btn = QPushButton(" 综合柱状")
        self._cols_btn.setCheckable(True)
        self._cols_btn.setChecked(True)
        self._overlay_btn = QPushButton(" 曲线叠合")
        self._overlay_btn.setCheckable(True)
        
        seg_style = (
            "QPushButton { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 4px; padding: 4px 10px; font-size: 11.5px; color: #586878; }"
            "QPushButton:hover { background: #f1f4f9; }"
            "QPushButton:checked { background: #e9effa; border-color: #1f66d4; color: #1f66d4; font-weight: bold; }"
        )
        self._cols_btn.setStyleSheet(seg_style)
        self._overlay_btn.setStyleSheet(seg_style)
        
        from PySide6.QtWidgets import QButtonGroup
        self._segmented_group = QButtonGroup(self)
        self._segmented_group.addButton(self._cols_btn)
        self._segmented_group.addButton(self._overlay_btn)
        self._segmented_group.setExclusive(True)
        
        toolbar_layout.addWidget(self._cols_btn)
        toolbar_layout.addWidget(self._overlay_btn)

        toolbar_layout.addStretch()

        # Tracks toggle button
        self._tracks_btn = QPushButton(" 轨道")
        self._tracks_btn.setCheckable(True)
        self._tracks_btn.setIcon(self._get_ui_icon("layers.svg"))
        self._tracks_btn.setFixedHeight(28)
        self._tracks_btn.clicked.connect(lambda checked: self._control_panel.setVisible(checked))
        self._tracks_btn.setStyleSheet(
            "QPushButton { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px; padding: 4px 12px; color: #1a2433; }"
            "QPushButton:checked { background: #e9effa; border-color: #1f66d4; color: #1f66d4; font-weight: bold; }"
            "QPushButton:hover { background: #f1f4f9; }"
        )
        toolbar_layout.addWidget(self._tracks_btn)

        self._import_las_btn = QPushButton(" 📁 导入 LAS")
        self._import_las_btn.setFixedHeight(28)
        self._import_las_btn.clicked.connect(self._on_import_las)
        self._import_las_btn.setStyleSheet(
            "QPushButton { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px; padding: 4px 12px; color: #1a2433; }"
            "QPushButton:hover { background: #f1f4f9; }"
        )
        toolbar_layout.addWidget(self._import_las_btn)

        self._export_btn = QPushButton(" 导出")
        self._export_btn.setIcon(self._get_ui_icon("export.svg"))
        self._export_btn.setFixedHeight(28)
        self._export_btn.clicked.connect(self._on_export)
        self._export_btn.setStyleSheet(
            "QPushButton { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px; padding: 4px 12px; color: #1a2433; }"
            "QPushButton:hover { background: #f1f4f9; }"
        )
        toolbar_layout.addWidget(self._export_btn)

        self._toolbar.setVisible(True)
        outer.addWidget(self._toolbar)


        # Inline progress bar (between toolbar and content)
        self._progress = FloatingProgressOverlay(self)
        outer.addWidget(self._progress)

        # Main content area
        self._content_layout = QHBoxLayout()
        outer.addLayout(self._content_layout, 1)

        # Page stack
        self._stack = QStackedWidget()
        self._placeholder = QLabel("从上方下拉框选择测井，或在地图页点击井位")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("font-size: 16px; color: #a0aec0;")
        self._stack.addWidget(self._placeholder)
        self._content_layout.addWidget(self._stack, 4)

        # Control panel
        self._control_panel = QGroupBox(" 轨道显示与排序")
        self._control_panel.setFixedWidth(260)
        panel_layout = QVBoxLayout(self._control_panel)
        panel_layout.setContentsMargins(8, 16, 8, 8)

        self._track_list_widget = QListWidget()
        self._track_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._track_list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._track_list_widget.setStyleSheet("""
            QListWidget { background: #ffffff; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #f0f4f8; }
            QListWidget::item:hover { background: #f1f4f9; }
            QListWidget::item:selected { background: #e9effa; color: #1f66d4; }
        """)
        self._track_list_widget.model().rowsMoved.connect(self._update_tracks)
        self._track_list_widget.itemChanged.connect(self._update_tracks)
        panel_layout.addWidget(self._track_list_widget)

        btn_layout = QHBoxLayout()
        self._merge_btn = QPushButton(" 合并")
        self._merge_btn.setIcon(self._get_ui_icon("share.svg"))
        self._merge_btn.clicked.connect(self._on_merge_curves)
        
        self._split_btn = QPushButton(" 拆分")
        self._split_btn.setIcon(self._get_ui_icon("layers.svg"))
        self._split_btn.clicked.connect(self._on_split_curve)

        btn_layout.addWidget(self._merge_btn)
        btn_layout.addWidget(self._split_btn)
        panel_layout.addLayout(btn_layout)

        self._predict_btn = QPushButton(" AI 预测沉积相")
        self._predict_btn.setIcon(self._get_ui_icon("play.svg"))
        self._predict_btn.clicked.connect(self._on_predict_facies)
        panel_layout.addWidget(self._predict_btn)

        self._control_panel.setVisible(False)
        self._content_layout.addWidget(self._control_panel)

        # State
        self._qpainter_widget: QPainterWidget | None = None
        self._all_tracks: list = []
        self._current_well: str | None = None
        self._current_xls_path = None
        self._current_data = None
        self._load_thread = None
        self._load_worker = None
        self._pred_thread = None
        self._pred_worker = None

    def _cleanup_load_thread(self):
        if self._load_thread:
            try:
                if self._load_thread.isRunning():
                    self._load_thread.quit()
                    self._load_thread.wait(2000)
            except RuntimeError:
                pass
        self._load_thread = None
        self._load_worker = None

    def _cleanup_pred_thread(self):
        if self._pred_thread:
            try:
                if self._pred_thread.isRunning():
                    self._pred_thread.quit()
                    self._pred_thread.wait(2000)
            except RuntimeError:
                pass
        self._pred_thread = None
        self._pred_worker = None

    def cleanup(self):
        """Stop background load/prediction threads when leaving this page."""
        self._cleanup_load_thread()
        self._cleanup_pred_thread()

    def load_well(self, well_name: str) -> bool:
        if well_name == self._current_well and self._qpainter_widget:
            return True

        entry = get_well_data(well_name)
        if entry is None:
            return False

        loader_fn, xls_path, _config = entry

        self._cleanup_load_thread()

        if self._qpainter_widget:
            self._stack.removeWidget(self._qpainter_widget)
            self._qpainter_widget.deleteLater()
            self._qpainter_widget = None

        # Disable combo during loading
        self._well_combo.setEnabled(False)

        # Show floating progress overlay
        self._progress.show_progress("正在加载井数据...")

        # Start background loading
        self._load_thread = QThread()
        self._load_worker = _WellLogLoadWorker(loader_fn, xls_path, well_name)
        self._load_worker.moveToThread(self._load_thread)

        self._load_thread.started.connect(self._load_worker.run)
        self._load_worker.progress.connect(self._on_load_progress)
        self._load_worker.finished.connect(self._on_well_loaded)
        self._load_worker.error.connect(self._on_load_error)
        self._load_worker.finished.connect(self._load_thread.quit)
        self._load_worker.error.connect(self._load_thread.quit)
        self._load_thread.finished.connect(self._on_load_thread_finished)

        self._load_thread.start()
        return True

    def _on_load_progress(self, val, msg):
        self._progress.update_progress(val, msg)

    def _on_well_loaded(self, data):
        print(f"[WellLog] Data Loaded. Curves: {[c.name for c in data.curves]}")

        well_name = data.well_name
        self._current_well = well_name
        self._current_data = data

        # Find xls_path from registry
        entry = get_well_data(well_name)
        if entry:
            self._current_xls_path = entry[1]

        # Sync combo box
        idx = self._well_combo.findText(well_name)
        if idx >= 0:
            self._well_combo.blockSignals(True)
            self._well_combo.setCurrentIndex(idx)
            self._well_combo.blockSignals(False)

        # Build QPainter tracks
        self._all_tracks = build_qpainter_tracks(data)

        self._qpainter_widget = QPainterWidget(self)
        self._qpainter_widget.set_tracks(self._all_tracks)
        self._stack.addWidget(self._qpainter_widget)
        self._stack.setCurrentWidget(self._qpainter_widget)

        # Populate track list
        self._populate_track_list()

        self._well_name_label.setText(well_name + " 综合测井解释图")
        if self._all_tracks:
            top = self._all_tracks[0].depth_top
            bottom = self._all_tracks[0].depth_bottom
            self._depth_lbl.setText(f"深度范围: {top:.1f}m - {bottom:.1f}m")
        self._control_panel.setVisible(True)
        self._tracks_btn.setChecked(True)

    def _on_load_error(self, msg):
        self._well_combo.setEnabled(True)
        self._progress.hide_progress()
        print(f"[WellLog] {msg}")
        QMessageBox.warning(self, "加载失败", msg)

    def _on_load_thread_finished(self):
        self._load_thread = None
        self._load_worker = None
        self._well_combo.setEnabled(True)
        self._progress.hide_progress()

    def _populate_track_list(self):
        self._track_list_widget.blockSignals(True)
        self._track_list_widget.clear()
        for track in self._all_tracks:
            item = QListWidgetItem(track.label)
            if isinstance(track, CurveTrack):
                item.setIcon(QIcon("src/resources/icons/curve.svg"))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self._track_list_widget.addItem(item)
        self._track_list_widget.blockSignals(False)

    def _on_well_selected(self, text: str):
        if not text or text == "选择测井...":
            return
        self.load_well(text)

    def _update_tracks(self, *_):
        if not self._qpainter_widget or not self._all_tracks:
            return

        label_map = {t.label: t for t in self._all_tracks}

        ordered_labels = []
        visible_tracks = []
        for i in range(self._track_list_widget.count()):
            item = self._track_list_widget.item(i)
            label = item.text()
            ordered_labels.append(label)
            if item.checkState() != Qt.CheckState.Checked:
                continue
            if label in label_map:
                visible_tracks.append(label_map[label])

        # Reorder _all_tracks to match list widget order
        reordered = []
        for lbl in ordered_labels:
            if lbl in label_map:
                reordered.append(label_map[lbl])
        self._all_tracks = reordered

        if visible_tracks:
            self._qpainter_widget.set_tracks(visible_tracks)

    def _on_import_las(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "导入 LAS 测井文件", "", "LAS Files (*.las);;All Files (*)"
        )
        if filepath:
            self.import_las_file(filepath)

    def import_las_file(self, filepath: str, show_dialog: bool = False):
        """Parse LAS file and display curves."""
        from geoviz_well_log.las_parser import parse_las_file
        parsed = parse_las_file(filepath)
        if parsed and len(parsed.depth) > 0 and show_dialog:
            QMessageBox.information(
                self, "LAS 导入成功", f"成功导入井 [{parsed.well_name}]，包含 {len(parsed.curves)} 条曲线！"
            )


    def _on_merge_curves(self):

        selected_items = self._track_list_widget.selectedItems()
        if len(selected_items) < 2 or len(selected_items) > 3:
            return

        label_map = {t.label: t for t in self._all_tracks}

        labels = []
        tracks = []
        for it in selected_items:
            text = it.text()
            track = label_map.get(text)
            if track and isinstance(track, CurveTrack):
                labels.append(text)
                tracks.append(track)
            else:
                return

        if len(labels) < 2:
            return

        combined_curves = []
        for t in tracks:
            combined_curves.extend(t._curves)
        merged_label = " + ".join(labels)
        merged = CurveTrack(curves=combined_curves, label=merged_label, width=140)

        indices = [self._all_tracks.index(t) for t in tracks]
        for t in tracks:
            self._all_tracks.remove(t)
        self._all_tracks.insert(min(indices), merged)
        merged.set_depth_range(tracks[0].depth_top, tracks[0].depth_bottom)

        rows = sorted([self._track_list_widget.row(it) for it in selected_items], reverse=True)
        for r in rows:
            self._track_list_widget.takeItem(r)

        item = QListWidgetItem(merged_label)
        item.setIcon(QIcon("src/resources/icons/curve.svg"))
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked)
        self._track_list_widget.insertItem(rows[-1], item)
        self._update_tracks()

    def _on_split_curve(self):
        selected_items = self._track_list_widget.selectedItems()
        if len(selected_items) != 1:
            return

        text = selected_items[0].text()
        label_map = {t.label: t for t in self._all_tracks}
        track = label_map.get(text)

        if not track or not isinstance(track, CurveTrack) or len(track._curves) < 2:
            return

        new_tracks = []
        new_labels = []
        for c in track._curves:
            ct = CurveTrack(curves=[c], label=c.name, width=140)
            ct.set_depth_range(track.depth_top, track.depth_bottom)
            new_tracks.append(ct)
            new_labels.append(c.name)

        idx = self._all_tracks.index(track)
        self._all_tracks.remove(track)
        for i, nt in enumerate(new_tracks):
            self._all_tracks.insert(idx + i, nt)

        row = self._track_list_widget.row(selected_items[0])
        self._track_list_widget.takeItem(row)

        for i, label in enumerate(new_labels):
            item = QListWidgetItem(label)
            item.setIcon(QIcon("src/resources/icons/curve.svg"))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self._track_list_widget.insertItem(row + i, item)
        self._update_tracks()

    def _on_export(self):
        if not self._qpainter_widget:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出测井图",
            f"{self._current_well}_well_log",
            "SVG 矢量 (*.svg);;PDF 矢量 (*.pdf);;PNG 位图 (*.png)",
        )
        if not path:
            return
        canvas = self._qpainter_widget.canvas
        lower = path.lower()
        if lower.endswith(".pdf"):
            qpainter_export_pdf(canvas, path)
        elif lower.endswith(".png"):
            qpainter_export_png(canvas, path)
        else:
            if not lower.endswith(".svg"):
                path += ".svg"
            qpainter_export_svg(canvas, path)

    def _on_predict_facies(self):
        if not self._current_well or not self._current_xls_path:
            QMessageBox.warning(self, "AI 预测", "当前未加载任何井数据！")
            return

        import pandas as pd
        has_existing = False
        df_ai = None
        try:
            excel_file = pd.ExcelFile(self._current_xls_path)
            if "AI预测结果" in excel_file.sheet_names:
                df_ai = pd.read_excel(excel_file, sheet_name="AI预测结果")
                if not df_ai.empty and all(c in df_ai.columns for c in ["深度", "预测相", "置信度"]):
                    has_existing = True
        except Exception as e:
            print(f"Error checking existing AI sheet: {e}")

        if has_existing:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("AI预测提示")
            msg_box.setText("检测到该井已有AI预测结果。")
            msg_box.setInformativeText("是否重新预测还是直接加载已有结果？")
            btn_load = msg_box.addButton("直接加载", QMessageBox.ButtonRole.YesRole)
            btn_repredict = msg_box.addButton("重新预测", QMessageBox.ButtonRole.NoRole)
            msg_box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
            msg_box.exec()

            if msg_box.clickedButton() == btn_load:
                self._apply_ai_prediction(df_ai.to_dict(orient="records"))
                return
            elif msg_box.clickedButton() == btn_repredict:
                self._remove_ai_tracks()
            else:
                return

        if str(self._current_xls_path).lower().endswith(".xls"):
            try:
                import pandas as pd
                from pathlib import Path
                src_path = Path(self._current_xls_path)
                dst_path = src_path.with_suffix(".xlsx")

                print(f"[AI Prediction] Auto-converting legacy .xls to modern .xlsx: {src_path} -> {dst_path}")

                with pd.ExcelWriter(dst_path, engine="openpyxl") as writer:
                    excel_file = pd.ExcelFile(src_path, engine="calamine")
                    for sheet in excel_file.sheet_names:
                        pd.read_excel(excel_file, sheet_name=sheet).to_excel(writer, sheet_name=sheet, index=False)

                self._current_xls_path = str(dst_path)

                import src.data.well_registry
                entry = src.data.well_registry._WELL_REGISTRY.get(self._current_well)
                if entry:
                    loader_fn, _ = entry
                    src.data.well_registry._WELL_REGISTRY[self._current_well] = (loader_fn, dst_path)

                print("[AI Prediction] Conversion successful. Switched to .xlsx mode.")
            except Exception as conv_err:
                QMessageBox.warning(self, "文件转换失败",
                    f"无法将旧版 .xls 格式转换为 .xlsx 以供 AI 预测追加结果，"
                    f"请手动将您的文件另存为 .xlsx 格式后再试。\n错误: {conv_err}")
                return

        self._run_ai_prediction()

    def _apply_ai_prediction(self, records):
        if not records:
            return
        from geoviz_well_log.models import IntervalItem
        from geoviz_well_log.renderer.interval_track import IntervalTrack

        # Build AI prediction tracks as IntervalTracks
        facies_items = []
        confidence_items = []
        for r in records:
            depth = r["深度"]
            facies_items.append(IntervalItem(top=depth - 0.5, bottom=depth + 0.5, name=r["预测相"]))
            conf = r.get("置信度", 0)
            label = f"{conf:.0%}" if isinstance(conf, (int, float)) else str(conf)
            confidence_items.append(IntervalItem(top=depth - 0.5, bottom=depth + 0.5, name=label))

        existing_labels = {
            self._track_list_widget.item(i).text()
            for i in range(self._track_list_widget.count())
        }

        new_tracks = []
        if "AI预测相" not in existing_labels:
            t = IntervalTrack(intervals=facies_items, label="AI预测相", width=80)
            if self._current_data:
                t.set_depth_range(self._current_data.top_depth, self._current_data.bottom_depth)
            self._all_tracks.append(t)
            new_tracks.append("AI预测相")

        if "AI预测置信度" not in existing_labels:
            t = IntervalTrack(intervals=confidence_items, label="AI预测置信度", width=80)
            if self._current_data:
                t.set_depth_range(self._current_data.top_depth, self._current_data.bottom_depth)
            self._all_tracks.append(t)
            new_tracks.append("AI预测置信度")

        for name in new_tracks:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self._track_list_widget.addItem(item)
        self._update_tracks()

    def _remove_ai_tracks(self):
        for idx in range(self._track_list_widget.count() - 1, -1, -1):
            item = self._track_list_widget.item(idx)
            if item.text() in ("AI预测相", "AI预测置信度"):
                self._track_list_widget.takeItem(idx)
        self._all_tracks = [t for t in self._all_tracks if t.label not in ("AI预测相", "AI预测置信度")]
        self._update_tracks()

    def _run_ai_prediction(self):
        self._cleanup_pred_thread()

        self._progress.show_progress("正在准备预测数据...", maximum=100)

        self._pred_thread = QThread()
        self._pred_worker = PredictionWorker(self._current_well, self._current_xls_path, self._current_data)
        self._pred_worker.moveToThread(self._pred_thread)

        self._pred_thread.started.connect(self._pred_worker.run)
        self._pred_worker.progress.connect(self._on_prediction_progress)
        self._pred_worker.finished.connect(self._on_prediction_finished)
        self._pred_worker.error.connect(self._on_prediction_error)
        self._pred_worker.finished.connect(self._pred_thread.quit)
        self._pred_worker.error.connect(self._pred_thread.quit)

        self._pred_thread.start()

    def _on_prediction_progress(self, val, msg):
        self._progress.update_progress(val, msg)

    def _on_prediction_finished(self, records):
        self._pred_thread = None
        self._pred_worker = None
        self._progress.hide_progress()
        self._well_combo.setEnabled(True)
        self._apply_ai_prediction(records)
        QMessageBox.information(self, "AI 预测", "AI 预测完成！已成功渲染并写入 Excel。")

    def _on_prediction_error(self, err_msg):
        self._pred_thread = None
        self._pred_worker = None
        self._progress.hide_progress()
        self._well_combo.setEnabled(True)
        QMessageBox.critical(self, "AI 预测错误", err_msg)
