import json
import math
from PySide6.QtCore import Qt, QThread, QObject, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QFileDialog, QGroupBox, QListWidget, QAbstractItemView, QListWidgetItem,
    QMessageBox, QProgressDialog
)
from src.data.well_registry import get_well_data
from src.utils.constants import PATTERN_MAP
from geoviz_well_log import ChartEngine


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
            
            # Unique depths from curves
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

            # Filter out rows where GR is None or NaN
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

            # Send request
            req = urllib.request.Request(
                "http://api-test.deeptime.world/api/v1/inference/single-well/json",
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

            # Prepare records for saving
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
                with pd.ExcelWriter(self.xls_path, engine="openpyxl", mode="a") as writer:
                    df_ai.to_excel(writer, sheet_name="AI预测结果", index=False)
            except Exception as e:
                print(f"Failed to append sheet: {e}")
                df_ai.to_excel(self.xls_path, sheet_name="AI预测结果", index=False)

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

        # Toolbar (hidden until a chart is loaded)
        self._toolbar = QWidget()
        self._toolbar.setStyleSheet("background: #f7fafc; border-bottom: 1px solid #e2e8f0;")
        toolbar_layout = QHBoxLayout(self._toolbar)
        toolbar_layout.setContentsMargins(12, 6, 12, 6)

        self._well_name_label = QLabel()
        self._well_name_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #1a202c;")
        toolbar_layout.addWidget(self._well_name_label)
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

        self._toolbar.setVisible(False)
        outer.addWidget(self._toolbar)

        # Main content area containing stack (chart) + control panel (reordering)
        self._content_layout = QHBoxLayout()
        outer.addLayout(self._content_layout, 1)

        # Page stack (fills remaining space)
        self._stack = QStackedWidget()

        self._placeholder = QLabel("点击地图上的井位查看测井图")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("font-size: 16px; color: #a0aec0;")
        self._stack.addWidget(self._placeholder)

        self._content_layout.addWidget(self._stack, 4)

        # Control panel for draggable reordering
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
        self._track_list_widget.model().rowsMoved.connect(self._update_chart_order)
        self._track_list_widget.itemChanged.connect(self._update_chart_order)
        panel_layout.addWidget(self._track_list_widget)


        # Buttons for merging and splitting curve tracks
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

        self._chart_widget: ChartEngine | None = None
        self._current_well: str | None = None
        self._current_xls_path = None
        self._current_data = None
        self._track_pool = {}
        self._cached_metadata = {}

    def load_well(self, well_name: str) -> bool:
        """Load and display well log data for the given well name."""
        if well_name == self._current_well and self._chart_widget:
            return True

        entry = get_well_data(well_name)
        if entry is None: return False

        loader_fn, xls_path, config = entry

        # Remove previous chart
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
        
        self._cached_metadata = { "wellName": data.well_name, "topDepth": data.top_depth, "bottomDepth": data.bottom_depth }

        if hasattr(data, "custom_tracks") and data.custom_tracks:
            self._track_pool = {t["name"]: t for t in data.custom_tracks}

            # Laolong default active tracks
            default_active = {
                "系", "统", "组", "地层系统", 
                "AC", "GR", 
                "深度", 
                "岩性", "岩性剖面", 
                "RT", "RXO",
                "岩性描述", 
                "微相", "亚相", "相", 
                "体系域", "层序"
            }

            # Populate ListWidget for track ordering
            self._track_list_widget.blockSignals(True)
            self._track_list_widget.clear()
            for t in data.custom_tracks:
                item = QListWidgetItem(t["name"])
                if t.get("type") == "CurveTrack":
                    item.setIcon(QIcon("src/resources/icons/curve.svg"))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                
                # Set checked state based on default active list
                name = t["name"]
                is_active = False
                for ref in default_active:
                    if name == ref or (ref in name and ref not in ("AC", "GR", "RT", "RXO")):
                        is_active = True
                        break
                
                item.setCheckState(Qt.CheckState.Checked if is_active else Qt.CheckState.Unchecked)
                self._track_list_widget.addItem(item)
            self._track_list_widget.blockSignals(False)

            self._well_name_label.setText(well_name + " 综合测井解释图")
            self._toolbar.setVisible(True)
            self._control_panel.setVisible(True)

            self._update_chart_order()
            return True


        # 1. Curve Configuration
        CURVE_META = {
            "AC": {"color": "#1d4ed8", "style": "dashed", "range": "40 - 80"},
            "GR": {"color": "#15803d", "style": "solid", "range": "0 - 150"},
            "RT": {"color": "#b91c1c", "style": "solid", "range": "0.1 - 1000"},
            "RXO": {"color": "#ea580c", "style": "dashed", "range": "0.1 - 1000"},
        }

        def get_pattern_id(name):
            if not name: return ""
            for k in sorted(PATTERN_MAP.keys(), key=len, reverse=True):
                if k in name: return PATTERN_MAP[k]
            return ""

        def create_curve_track(curve_names, label, width=15):
            curves_to_add = [c for c in data.curves if c.name in curve_names]
            if not curves_to_add: return None
            series = []
            for curve in curves_to_add:
                meta = CURVE_META.get(curve.name, {"color": curve.color, "style": "solid", "range": ""})
                curve_data = [[d, (v if not math.isnan(v) else None)] for d, v in zip(curve.depth, curve.values)]
                series.append({"name": curve.name, "color": meta["color"], "lineStyle": meta["style"], "rangeLabel": meta["range"], "data": curve_data})
            return { "type": "CurveTrack", "name": label, "width": width, "series": series }

        def create_interval_track(items, name, width=8, color="#ffffff", parent=None, vertical=False, apply_pattern=False):
            if not items: return None
            return {
                "type": "IntervalTrack", "name": name, "width": width, "parentGroup": parent,
                "textOrientation": "vertical" if vertical else "horizontal",
                "data": [{ "top": i.top, "bottom": i.bottom, "name": i.name, "color": color, "lithology": get_pattern_id(i.name) if apply_pattern else "" } for i in items]
            }

        self._track_pool = {}
        ivs = data.intervals

        # 1. Stratigraphy
        if ivs:
            for f, l in [("system", "系"), ("series", "统"), ("formation", "组")]:
                t = create_interval_track(getattr(ivs, f), l, width=4, parent="地层系统", vertical=True)
                if t: self._track_pool[l] = t

        # 2. Individual atomic curves
        for c_name in ["AC", "GR", "RT", "RXO"]:
            t = create_curve_track([c_name], c_name, width=14)
            if t: self._track_pool[c_name] = t

        # 3. Depth
        self._track_pool["深度"] = {"type": "DepthTrack", "name": "深度\n(m)", "width": 6}

        # 4. Lithology
        l_data = []
        if hasattr(data, 'lithology') and data.lithology: l_data.extend(data.lithology)
        if ivs and ivs.lithology: l_data.extend(ivs.lithology)
        if l_data:
            self._track_pool["岩性"] = {
                "type": "LithologyTrack", "name": "岩性", "width": 9,
                "data": [{ "top": i.top, "bottom": i.bottom, "lithology": get_pattern_id(i.name), "name": i.name, "color": "#cbd5e0" } for i in l_data]
            }

        # 6. Description
        if ivs and ivs.lithology_desc:
            t = create_interval_track(ivs.lithology_desc, "岩性描述", width=22, vertical=False)
            if t: self._track_pool["岩性描述"] = t

        # 7. Facies
        if ivs and ivs.facies:
            for f, l in [("micro_phase", "微相"), ("sub_phase", "亚相"), ("phase", "相")]:
                t = create_interval_track(getattr(ivs.facies, f), l, width=8, parent="沉积相", color="#ecfeff", apply_pattern=True)
                if t: self._track_pool[l] = t

        # 8. Systems Tract
        if ivs and ivs.systems_tract:
            self._track_pool["体系域"] = {
                "type": "IntervalTrack", "name": "体系域", "width": 7,
                "data": [{ "top": i.top, "bottom": i.bottom, "name": i.name, "shape": "triangle-up" if "TST" in i.name.upper() else "triangle-down" if "HST" in i.name.upper() else "rect", "color": "#93c5fd" if "TST" in i.name.upper() else "#fde047" if "HST" in i.name.upper() else "#f8fafc" } for i in ivs.systems_tract]
            }

        # 9. Sequence
        if ivs and ivs.sequence:
            t = create_interval_track(ivs.sequence, "层序", width=4, vertical=True)
            if t: self._track_pool["层序"] = t

        # Populate ListWidget for track ordering
        self._track_list_widget.blockSignals(True)
        self._track_list_widget.clear()

        initial_order = []
        if any(k in self._track_pool for k in ["系", "统", "组"]):
            initial_order.append("地层系统 (系/统/组)")
        
        if "AC" in self._track_pool and "GR" in self._track_pool:
            initial_order.append("曲线: AC + GR")
        elif "AC" in self._track_pool:
            initial_order.append("曲线: AC")
        elif "GR" in self._track_pool:
            initial_order.append("曲线: GR")
        
        if "深度" in self._track_pool: initial_order.append("深度 (m)")
        if "岩性" in self._track_pool: initial_order.append("岩性")

        if "RT" in self._track_pool and "RXO" in self._track_pool:
            initial_order.append("曲线: RT + RXO")
        elif "RT" in self._track_pool:
            initial_order.append("曲线: RT")
        elif "RXO" in self._track_pool:
            initial_order.append("曲线: RXO")

        if "岩性描述" in self._track_pool: initial_order.append("岩性描述")
        if any(k in self._track_pool for k in ["微相", "亚相", "相"]): initial_order.append("沉积相 (微相/亚相/相)")
        if "体系域" in self._track_pool: initial_order.append("体系域")
        if "层序" in self._track_pool: initial_order.append("层序")

        for item_text in initial_order:
            item = QListWidgetItem(item_text)
            if item_text.startswith("曲线: ") or "+" in item_text or (item_text in self._track_pool and self._track_pool[item_text]["type"] == "CurveTrack"):
                item.setIcon(QIcon("src/resources/icons/curve.svg"))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self._track_list_widget.addItem(item)

        self._track_list_widget.blockSignals(False)

        self._well_name_label.setText(well_name + " 综合测井解释图")
        self._toolbar.setVisible(True)
        self._control_panel.setVisible(True)

        self._update_chart_order()
        return True

    def _update_chart_order(self, *args):
        """Immediately rebuild and render tracks based on list display order."""
        sorted_tracks = []
        for i in range(self._track_list_widget.count()):
            item = self._track_list_widget.item(i)
            if item.checkState() != Qt.CheckState.Checked:
                continue
            text = item.text()
            if text in self._track_pool:
                sorted_tracks.append(self._track_pool[text])
            elif "地层系统" in text:
                for k in ["系", "统", "组"]:
                    if k in self._track_pool: sorted_tracks.append(self._track_pool[k])
            elif "沉积相" in text:
                for k in ["微相", "亚相", "相"]:
                    if k in self._track_pool: sorted_tracks.append(self._track_pool[k])
            elif "+" in text:
                curve_names = [c.strip() for c in text.split("+")]
                if len(curve_names) == 2:
                    c1, c2 = curve_names
                    if c1 in self._track_pool and c2 in self._track_pool:
                        merged = self._create_merged_curve_track([c1, c2])
                        sorted_tracks.append(merged)
            elif text.startswith("曲线: "):
                curves_part = text.replace("曲线: ", "")
                curve_names = [c.strip() for c in curves_part.split("+")]
                if len(curve_names) == 1:
                    c_name = curve_names[0]
                    if c_name in self._track_pool: sorted_tracks.append(self._track_pool[c_name])
                elif len(curve_names) == 2:
                    c1, c2 = curve_names
                    if c1 in self._track_pool and c2 in self._track_pool:
                        merged = self._create_merged_curve_track([c1, c2])
                        sorted_tracks.append(merged)
            elif "深度" in text:
                if "深度" in self._track_pool: sorted_tracks.append(self._track_pool["深度"])
            else:
                for k in self._track_pool:
                    if k in text and self._track_pool[k] not in sorted_tracks:
                        sorted_tracks.append(self._track_pool[k])

        payload = { "metadata": self._cached_metadata, "tracks": sorted_tracks }
        if self._chart_widget:
            self._chart_widget.render_data(json.dumps(payload))


    def _create_merged_curve_track(self, curve_names):
        import copy
        series = []
        # Predefined distinct colors for merged curves
        palette = ["#1d4ed8", "#dc2626", "#15803d", "#ea580c", "#8b5cf6"]
        
        for idx, name in enumerate(curve_names):
            t = self._track_pool.get(name)
            if t and "series" in t:
                for s in copy.deepcopy(t["series"]):
                    s["color"] = palette[idx % len(palette)]
                    series.append(s)
        return {
            "type": "CurveTrack",
            "name": "/".join(curve_names),
            "width": 14,
            "series": series
        }

    def _on_merge_curves(self):
        selected_items = self._track_list_widget.selectedItems()
        if len(selected_items) != 2:
            return
        
        texts = [i.text() for i in selected_items]
        valid_curve_tracks = []
        for text in texts:
            clean_text = text.replace("曲线: ", "").strip()
            if clean_text in self._track_pool and self._track_pool[clean_text]["type"] == "CurveTrack":
                valid_curve_tracks.append(clean_text)
            elif "+" in clean_text:
                valid_curve_tracks.append(clean_text)
            elif text in self._track_pool and self._track_pool[text]["type"] == "CurveTrack":
                valid_curve_tracks.append(text)
                
        if len(valid_curve_tracks) != 2:
            return
            
        c1, c2 = valid_curve_tracks
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
        self._update_chart_order()

    def _on_split_curve(self):
        selected_items = self._track_list_widget.selectedItems()
        if len(selected_items) != 1:
            return
        
        text = selected_items[0].text()
        clean_text = text.replace("曲线: ", "").strip()
        if "+" not in clean_text:
            return
        
        c1, c2 = [c.strip() for c in clean_text.split("+")]
        row = self._track_list_widget.row(selected_items[0])
        self._track_list_widget.takeItem(row)
        
        item1 = QListWidgetItem(c1)
        item1.setIcon(QIcon("src/resources/icons/curve.svg"))
        item1.setFlags(item1.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item1.setCheckState(Qt.CheckState.Checked)
        self._track_list_widget.insertItem(row, item1)
        
        item2 = QListWidgetItem(c2)
        item2.setIcon(QIcon("src/resources/icons/curve.svg"))
        item2.setFlags(item2.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item2.setCheckState(Qt.CheckState.Checked)
        self._track_list_widget.insertItem(row + 1, item2)
        self._update_chart_order()


    def _on_export(self):
        if not self._chart_widget: return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出测井图", f"{self._current_well}_well_log",
            "SVG 矢量 (*.svg);;PDF 文件 (*.pdf);;PNG 图片 (*.png)"
        )
        if not path:
            return

        if path.lower().endswith(".pdf"):
            from PySide6.QtGui import QPageLayout, QPageSize
            from PySide6.QtCore import QMarginsF
            # A3 Landscape with 0 margins avoids cutting off wide content horizontally
            page_layout = QPageLayout(
                QPageSize(QPageSize.PageSizeId.A3),
                QPageLayout.Orientation.Landscape,
                QMarginsF(0, 0, 0, 0)
            )
            self._chart_widget.view.page().printToPdf(path, page_layout)
        elif path.lower().endswith(".png"):
            pixmap = self._chart_widget.view.grab()
            pixmap.save(path, "PNG")
        else:
            if not path.lower().endswith(".svg"):
                path += ".svg"
            self._export_path = path
            self._chart_widget.export_svg()

    def _save_svg_to_disk(self, svg_str):
        export_path = getattr(self, "_export_path", None)
        if not export_path:
            export_path, _ = QFileDialog.getSaveFileName(self, "导出测井图", f"{self._current_well}_well_log.svg", "SVG 矢量 (*.svg)")
        if export_path:
            with open(export_path, "w", encoding="utf-8") as f:
                f.write(svg_str)
            self._export_path = None

    def _on_predict_facies(self):
        if not self._current_well or not self._current_xls_path:
            QMessageBox.warning(self, "AI 预测", "当前未加载任何井数据！")
            return

        # Check existing
        import pandas as pd
        has_existing = False
        df_ai = None
        try:
            excel_file = pd.ExcelFile(self._current_xls_path)
            if "AI预测结果" in excel_file.sheet_names:
                df_ai = pd.read_excel(excel_file, sheet_name="AI预测结果")
                if not df_ai.empty and "深度" in df_ai.columns and "预测相" in df_ai.columns and "置信度" in df_ai.columns:
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
                self._load_existing_ai_prediction(df_ai)
                return
            elif msg_box.clickedButton() == btn_repredict:
                # Delete previous tracks from pool and widget
                if "AI预测相" in self._track_pool:
                    del self._track_pool["AI预测相"]
                if "AI预测置信度" in self._track_pool:
                    del self._track_pool["AI预测置信度"]

                for idx in range(self._track_list_widget.count() - 1, -1, -1):
                    item = self._track_list_widget.item(idx)
                    if item.text() in ("AI预测相", "AI预测置信度"):
                        self._track_list_widget.takeItem(idx)

                self._update_chart_order()
            else:
                return

        self._run_ai_prediction()

    def _load_existing_ai_prediction(self, df_ai):
        records = df_ai.to_dict(orient="records")
        if not records:
            return
        self._apply_ai_tracks(records)

    def _apply_ai_tracks(self, records):
        # First, calculate bottom for each raw record
        data_len = len(records)
        for i in range(data_len):
            depth = records[i]["深度"]
            if i < data_len - 1:
                records[i]["bottom"] = records[i+1]["深度"]
            else:
                records[i]["bottom"] = depth + 0.125

        # Merge contiguous records for AI预测相 (Facies) ONLY when '预测相' is identical
        merged_facies_records = []
        if records:
            group_top = records[0]["深度"]
            group_bottom = records[0]["bottom"]
            group_facies = records[0]["预测相"]

            for i in range(1, data_len):
                r = records[i]
                r_facies = r["预测相"]
                if r_facies == group_facies:
                    group_bottom = r["bottom"]
                else:
                    merged_facies_records.append({
                        "top": group_top,
                        "bottom": group_bottom,
                        "预测相": group_facies
                    })
                    group_top = r["深度"]
                    group_bottom = r["bottom"]
                    group_facies = r_facies

            merged_facies_records.append({
                "top": group_top,
                "bottom": group_bottom,
                "预测相": group_facies
            })

        def get_facies_color(facies_name):
            colors = {
                "1": "#2563eb", "2": "#3b82f6", "3": "#60a5fa",
                "砂岩": "#fef08a", "泥岩": "#94a3b8", "灰岩": "#fca5a5"
            }
            return colors.get(str(facies_name), "#cbd5e1")

        def get_confidence_color(val):
            try:
                val = max(0.0, min(1.0, float(val)))
            except (ValueError, TypeError):
                val = 0.5
            
            # Smooth transition: Blue -> Cyan -> Green -> Yellow -> Red (Scientific Jet/Rainbow colormap)
            if val < 0.25:
                r = 0
                g = int(val * 4.0 * 255)
                b = 255
            elif val < 0.5:
                r = 0
                g = 255
                b = int((0.5 - val) * 4.0 * 255)
            elif val < 0.75:
                r = int((val - 0.5) * 4.0 * 255)
                g = 255
                b = 0
            else:
                r = 255
                g = int((1.0 - val) * 4.0 * 255)
                b = 0
            return f"#{r:02x}{g:02x}{b:02x}"

        track_facies = {
            "type": "IntervalTrack",
            "name": "AI预测相",
            "width": 8,
            "textOrientation": "vertical",
            "data": [
                {
                    "top": r["top"],
                    "bottom": r["bottom"],
                    "name": str(r["预测相"]),
                    "color": get_facies_color(r["预测相"]),
                    "lithology": ""
                }
                for r in merged_facies_records
            ]
        }

        # Build confidence data
        conf_data = []

        # 1. Raw unthinned lookup items (transparent, no rendering, but matched first by tooltip .find())
        for r in records:
            conf_data.append({
                "top": r["深度"],
                "bottom": r["bottom"],
                "name": f"{float(r.get('置信度', 0.5))*100:.1f}%",
                "color": "transparent",
                "lithology": ""
            })

        # 2. Display items: merge adjacent records whose confidence is within 1% difference (abs(val1 - val2) <= 0.01)
        # This keeps the color transitions extremely smooth and continuous without discrete segment lines!
        if records:
            group_top = records[0]["深度"]
            group_bottom = records[0]["bottom"]
            group_conf = records[0].get("置信度", 0.5)

            for r in records[1:]:
                r_conf = r.get("置信度", 0.5)
                if abs(r_conf - group_conf) <= 0.01:
                    group_bottom = r["bottom"]
                else:
                    conf_data.append({
                        "top": group_top,
                        "bottom": group_bottom,
                        "name": "",  # Empty name so it is ignored by tooltip lookup
                        "color": get_confidence_color(group_conf),
                        "lithology": ""
                    })
                    group_top = r["深度"]
                    group_bottom = r["bottom"]
                    group_conf = r_conf

            conf_data.append({
                "top": group_top,
                "bottom": group_bottom,
                "name": "",
                "color": get_confidence_color(group_conf),
                "lithology": ""
            })

        track_confidence = {
            "type": "IntervalTrack",
            "name": "AI预测置信度",
            "width": 8,
            "textOrientation": "horizontal",
            "data": conf_data
        }

        self._track_pool["AI预测相"] = track_facies
        self._track_pool["AI预测置信度"] = track_confidence

        # Add to the track list widget if not already present
        found_facies = False
        found_conf = False
        for i in range(self._track_list_widget.count()):
            txt = self._track_list_widget.item(i).text()
            if txt == "AI预测相": found_facies = True
            if txt == "AI预测置信度": found_conf = True

        if not found_facies:
            item = QListWidgetItem("AI预测相")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self._track_list_widget.addItem(item)
        if not found_conf:
            item = QListWidgetItem("AI预测置信度")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self._track_list_widget.addItem(item)

        self._update_chart_order()

    def _run_ai_prediction(self):
        # Create progress dialog
        self._progress_dialog = QProgressDialog("正在准备预测数据...", "取消", 0, 100, self)
        self._progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress_dialog.show()

        # Create worker & thread
        self._thread = QThread()
        self._worker = PredictionWorker(self._current_well, self._current_xls_path, self._current_data)
        self._worker.moveToThread(self._thread)

        # Connect signals
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_prediction_progress)
        self._worker.finished.connect(self._on_prediction_finished)
        self._worker.error.connect(self._on_prediction_error)
        
        # Cleanup
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.error.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def _on_prediction_progress(self, val, msg):
        if hasattr(self, "_progress_dialog") and self._progress_dialog:
            self._progress_dialog.setValue(val)
            self._progress_dialog.setLabelText(msg)

    def _on_prediction_finished(self, records):
        if hasattr(self, "_progress_dialog") and self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None
        self._apply_ai_tracks(records)
        QMessageBox.information(self, "AI 预测", "AI 预测完成！已成功渲染并写入 Excel。")

    def _on_prediction_error(self, err_msg):
        if hasattr(self, "_progress_dialog") and self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None
        QMessageBox.critical(self, "AI 预测错误", err_msg)
