from PySide6.QtCore import Qt, QThread, QObject, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QGroupBox, QListWidget, QAbstractItemView, QListWidgetItem,
    QMessageBox, QProgressDialog, QComboBox
)
from src.data.well_registry import get_well_data, list_wells
from geoviz_well_log import (
    ChartEngine, TrackManager, PATTERN_MAP,
    build_tracks_from_data, build_ai_prediction_tracks,
    build_legacy_display_items, LEGACY_DEFAULT_ACTIVE,
)
from geoviz_well_log.export import export_dialog


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
                # Ensure only .xlsx files are appended using openpyxl, fail safely if not
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


class WellLogPage(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Toolbar
        self._toolbar = QWidget()
        self._toolbar.setStyleSheet("background: #f7fafc; border-bottom: 1px solid #e2e8f0;")
        toolbar_layout = QHBoxLayout(self._toolbar)
        toolbar_layout.setContentsMargins(12, 6, 12, 6)

        self._well_name_label = QLabel()
        self._well_name_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #1a202c;")
        toolbar_layout.addWidget(self._well_name_label)

        toolbar_layout.addSpacing(12)

        self._well_combo = QComboBox()
        self._well_combo.setFixedHeight(28)
        self._well_combo.setMinimumWidth(140)
        self._well_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #cbd5e1; border-radius: 4px;
                padding: 0 8px; font-size: 13px; background: white;
            }
            QComboBox:hover { border-color: #3182ce; }
            QComboBox::drop-down { border: none; width: 20px; }
        """)
        self._well_combo.addItem("选择测井...")
        for name in list_wells():
            self._well_combo.addItem(name)
        self._well_combo.currentTextChanged.connect(self._on_well_selected)
        toolbar_layout.addWidget(self._well_combo)

        toolbar_layout.addStretch()

        self._export_btn = QPushButton("导出")
        self._export_btn.setFixedHeight(28)
        self._export_btn.setStyleSheet("""
            QPushButton {
                background: #3182ce; color: white;
                border: none; border-radius: 4px;
                padding: 0 12px; font-size: 13px;
            }
            QPushButton:hover { background: #2b6cb0; }
            QPushButton:pressed { background: #2c5282; }
        """)
        self._export_btn.clicked.connect(self._on_export)
        toolbar_layout.addWidget(self._export_btn)

        self._toolbar.setVisible(True)
        outer.addWidget(self._toolbar)

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
        self._control_panel = QGroupBox("轨道显示与排序")
        self._control_panel.setFixedWidth(240)
        self._control_panel.setStyleSheet("QGroupBox { font-weight: bold; margin-top: 12px; }")
        panel_layout = QVBoxLayout(self._control_panel)
        panel_layout.setContentsMargins(6, 12, 6, 6)

        self._track_list_widget = QListWidget()
        self._track_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._track_list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._track_list_widget.setStyleSheet("""
            QListWidget { border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px; background: #f8fafc; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #f1f5f9; font-size: 12px; }
            QListWidget::item:hover { background: #e2e8f0; }
            QListWidget::item:selected { background: #cbd5e1; color: #000; }
        """)
        self._track_list_widget.model().rowsMoved.connect(self._update_chart)
        self._track_list_widget.itemChanged.connect(self._update_chart)
        panel_layout.addWidget(self._track_list_widget)

        btn_layout = QHBoxLayout()
        self._merge_btn = QPushButton("合并曲线")
        self._merge_btn.clicked.connect(self._on_merge_curves)
        self._split_btn = QPushButton("拆分曲线")
        self._split_btn.clicked.connect(self._on_split_curve)

        btn_style = """
            QPushButton {
                background: #edf2f7; color: #1e293b;
                border: 1px solid #cbd5e1; border-radius: 4px;
                padding: 5px 8px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background: #e2e8f0; }
        """
        self._merge_btn.setStyleSheet(btn_style)
        self._split_btn.setStyleSheet(btn_style)
        btn_layout.addWidget(self._merge_btn)
        btn_layout.addWidget(self._split_btn)
        panel_layout.addLayout(btn_layout)

        self._predict_btn = QPushButton("🤖 AI预测沉积相")
        self._predict_btn.setStyleSheet("""
            QPushButton {
                background: #3182ce; color: white;
                border: none; border-radius: 4px;
                padding: 6px 12px; font-size: 12px; font-weight: bold;
                margin-top: 6px;
            }
            QPushButton:hover { background: #2b6cb0; }
            QPushButton:pressed { background: #2c5282; }
        """)
        self._predict_btn.clicked.connect(self._on_predict_facies)
        panel_layout.addWidget(self._predict_btn)

        self._control_panel.setVisible(False)
        self._content_layout.addWidget(self._control_panel)

        # State
        self._chart_widget: ChartEngine | None = None
        self._current_well: str | None = None
        self._current_xls_path = None
        self._current_data = None
        self._track_mgr: TrackManager | None = None
        self._cached_metadata = {}

    def load_well(self, well_name: str) -> bool:
        if well_name == self._current_well and self._chart_widget:
            return True

        entry = get_well_data(well_name)
        if entry is None:
            return False

        loader_fn, xls_path, config = entry

        if self._chart_widget:
            self._stack.removeWidget(self._chart_widget)
            self._chart_widget.deleteLater()
            self._chart_widget = None

        try:
            data = loader_fn(xls_path, well_name=well_name)
            print(f"[WellLog] Data Loaded. Curves: {[c.name for c in data.curves]}")
        except Exception as e:
            print(f"[WellLog] Failed to load {well_name}: {e}")
            return False

        self._chart_widget = ChartEngine(self)
        self._chart_widget.bridge.svg_received.connect(self._save_svg_to_disk)
        self._stack.addWidget(self._chart_widget)
        self._stack.setCurrentWidget(self._chart_widget)
        self._current_well = well_name
        self._current_xls_path = xls_path
        self._current_data = data

        self._cached_metadata = {
            "wellName": data.well_name,
            "topDepth": data.top_depth,
            "bottomDepth": data.bottom_depth,
        }

        # Sync combo box
        idx = self._well_combo.findText(well_name)
        if idx >= 0:
            self._well_combo.blockSignals(True)
            self._well_combo.setCurrentIndex(idx)
            self._well_combo.blockSignals(False)

        # Build tracks using the package
        if hasattr(data, "custom_tracks") and data.custom_tracks:
            track_pool = {t["name"]: t for t in data.custom_tracks}
            self._track_mgr = TrackManager(track_pool)
            self._populate_list_widget_converted(data.custom_tracks)
        else:
            track_pool = build_tracks_from_data(data)
            self._track_mgr = TrackManager(track_pool)
            display_items = build_legacy_display_items(track_pool)
            self._populate_list_widget_legacy(display_items)

        self._well_name_label.setText(well_name + " 综合测井解释图")
        self._control_panel.setVisible(True)
        self._update_chart()
        return True

    def _populate_list_widget_converted(self, custom_tracks):
        self._track_list_widget.blockSignals(True)
        self._track_list_widget.clear()
        for t in custom_tracks:
            item = QListWidgetItem(t["name"])
            if t.get("type") == "CurveTrack":
                item.setIcon(QIcon("src/resources/icons/curve.svg"))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            name = t["name"]
            is_active = any(
                name == ref or (ref in name and ref not in ("AC", "GR", "RT", "RXO"))
                for ref in LEGACY_DEFAULT_ACTIVE
            )
            item.setCheckState(Qt.CheckState.Checked if is_active else Qt.CheckState.Unchecked)
            self._track_list_widget.addItem(item)
        self._track_list_widget.blockSignals(False)

    def _populate_list_widget_legacy(self, display_items):
        self._track_list_widget.blockSignals(True)
        self._track_list_widget.clear()
        pool = self._track_mgr.pool
        for item_text in display_items:
            item = QListWidgetItem(item_text)
            if (item_text.startswith("曲线: ") or "+" in item_text
                    or (item_text in pool and pool[item_text]["type"] == "CurveTrack")):
                item.setIcon(QIcon("src/resources/icons/curve.svg"))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self._track_list_widget.addItem(item)
        self._track_list_widget.blockSignals(False)

    def _on_well_selected(self, text: str):
        if not text or text == "选择测井...":
            return
        self.load_well(text)

    def _update_chart(self, *_):
        if not self._track_mgr or not self._chart_widget:
            return
        display_items = []
        for i in range(self._track_list_widget.count()):
            item = self._track_list_widget.item(i)
            display_items.append((item.text(), item.checkState() == Qt.CheckState.Checked))
        payload = self._track_mgr.build_payload(self._cached_metadata, display_items)
        self._chart_widget.render_data(payload)

    def _on_merge_curves(self):
        selected_items = self._track_list_widget.selectedItems()
        if len(selected_items) != 2:
            return

        pool = self._track_mgr.pool
        valid = []
        for it in selected_items:
            clean = it.text().replace("曲线: ", "").strip()
            if clean in pool and pool[clean]["type"] == "CurveTrack":
                valid.append(clean)
            elif "+" in clean:
                valid.append(clean)
            elif it.text() in pool and pool[it.text()]["type"] == "CurveTrack":
                valid.append(it.text())

        if len(valid) != 2:
            return

        c1, c2 = valid
        row1 = self._track_list_widget.row(selected_items[0])
        row2 = self._track_list_widget.row(selected_items[1])
        insert_idx = min(row1, row2)

        self._track_list_widget.takeItem(max(row1, row2))
        self._track_list_widget.takeItem(min(row1, row2))

        item = QListWidgetItem(f"{c1} + {c2}")
        item.setIcon(QIcon("src/resources/icons/curve.svg"))
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked)
        self._track_list_widget.insertItem(insert_idx, item)
        self._update_chart()

    def _on_split_curve(self):
        selected_items = self._track_list_widget.selectedItems()
        if len(selected_items) != 1:
            return

        text = selected_items[0].text()
        clean = text.replace("曲线: ", "").strip()
        if "+" not in clean:
            return

        c1, c2 = [c.strip() for c in clean.split("+")]
        row = self._track_list_widget.row(selected_items[0])
        self._track_list_widget.takeItem(row)

        for i, name in enumerate([c1, c2]):
            item = QListWidgetItem(name)
            item.setIcon(QIcon("src/resources/icons/curve.svg"))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self._track_list_widget.insertItem(row + i, item)
        self._update_chart()

    def _on_export(self):
        if not self._chart_widget:
            return
        export_dialog(
            self._chart_widget, parent=self,
            default_name=f"{self._current_well}_well_log",
        )

    def _save_svg_to_disk(self, svg_str):
        export_path = getattr(self._chart_widget, "_export_path", None)
        if not export_path:
            from PySide6.QtWidgets import QFileDialog
            export_path, _ = QFileDialog.getSaveFileName(
                self, "导出测井图", f"{self._current_well}_well_log.svg", "SVG 矢量 (*.svg)"
            )
        if export_path:
            with open(export_path, "w", encoding="utf-8") as f:
                f.write(svg_str)
            if hasattr(self._chart_widget, "_export_path"):
                self._chart_widget._export_path = None

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

        # Auto-convert legacy .xls files to modern .xlsx before prediction to ensure safe appending
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
                
                # Point runtime state to the newly generated .xlsx path
                self._current_xls_path = str(dst_path)
                
                # Update well registry in memory so subsequent references use the .xlsx version
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
        if not records or not self._track_mgr:
            return
        added = build_ai_prediction_tracks(records, self._track_mgr.pool)
        # Add to list widget if not already present
        existing = {
            self._track_list_widget.item(i).text()
            for i in range(self._track_list_widget.count())
        }
        for name in added:
            if name not in existing:
                item = QListWidgetItem(name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                self._track_list_widget.addItem(item)
        self._update_chart()

    def _remove_ai_tracks(self):
        if self._track_mgr:
            self._track_mgr.remove_tracks(["AI预测相", "AI预测置信度"])
        for idx in range(self._track_list_widget.count() - 1, -1, -1):
            item = self._track_list_widget.item(idx)
            if item.text() in ("AI预测相", "AI预测置信度"):
                self._track_list_widget.takeItem(idx)
        self._update_chart()

    def _run_ai_prediction(self):
        self._progress_dialog = QProgressDialog("正在准备预测数据...", "取消", 0, 100, self)
        self._progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress_dialog.show()

        self._thread = QThread()
        self._worker = PredictionWorker(self._current_well, self._current_xls_path, self._current_data)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_prediction_progress)
        self._worker.finished.connect(self._on_prediction_finished)
        self._worker.error.connect(self._on_prediction_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.error.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def _on_prediction_progress(self, val, msg):
        dialog = getattr(self, "_progress_dialog", None)
        if dialog is not None:
            try:
                dialog.setValue(val)
                dialog.setLabelText(msg)
            except RuntimeError:
                pass

    def _on_prediction_finished(self, records):
        dialog = getattr(self, "_progress_dialog", None)
        if dialog is not None:
            try:
                dialog.close()
            except RuntimeError:
                pass
            self._progress_dialog = None
        self._apply_ai_prediction(records)
        QMessageBox.information(self, "AI 预测", "AI 预测完成！已成功渲染并写入 Excel。")

    def _on_prediction_error(self, err_msg):
        dialog = getattr(self, "_progress_dialog", None)
        if dialog is not None:
            try:
                dialog.close()
            except RuntimeError:
                pass
            self._progress_dialog = None
        QMessageBox.critical(self, "AI 预测错误", err_msg)
