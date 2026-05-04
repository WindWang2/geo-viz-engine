import json
import math
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QFileDialog, QGroupBox, QListWidget, QAbstractItemView, QListWidgetItem
)
from src.data.well_registry import get_well_data
from src.renderers.well_log.chart_engine import ChartEngine


class WellLogPage(QWidget):
    PATTERN_MAP = {
        "砂岩": "sandstone",
        "泥岩": "mudstone",
        "灰岩": "limestone",
        "白云岩": "dolomite",
        "页岩": "shale",
        "粉砂岩": "siltstone",
        "砂坪": "sand-flat",
        "泥坪": "mud-flat",
        "云质坪": "dolomitic-flat",
        "混积潮坪": "dolomitic-flat",
        "碎屑岩潮坪": "tidal-flat",
        "潮坪": "tidal-flat",
        "泥质陆棚": "muddy-shelf",
        "砂质陆棚": "sandy-shelf",
        "砂泥质陆棚": "sand-mud-shelf",
        "碎屑岩浅水陆棚": "clastic-shelf",
        "混积浅水陆棚": "mixed",
        "陆棚": "shelf",
        "混积": "mixed",
        "三角洲": "delta",
    }

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

        self._control_panel.setVisible(False)
        self._content_layout.addWidget(self._control_panel)

        self._chart_widget: ChartEngine | None = None
        self._current_well: str | None = None
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
        
        self._cached_metadata = { "wellName": data.well_name, "topDepth": data.top_depth, "bottomDepth": data.bottom_depth }

        if hasattr(data, "custom_tracks") and data.custom_tracks:
            self._track_pool = {t["name"]: t for t in data.custom_tracks}

            # Populate ListWidget for track ordering
            self._track_list_widget.blockSignals(True)
            self._track_list_widget.clear()
            for t in data.custom_tracks:
                item = QListWidgetItem(t["name"])
                if t.get("type") == "CurveTrack":
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


        # 1. Curve Configuration
        CURVE_META = {
            "AC": {"color": "#1d4ed8", "style": "dashed", "range": "40 - 80"},
            "GR": {"color": "#15803d", "style": "solid", "range": "0 - 150"},
            "RT": {"color": "#b91c1c", "style": "solid", "range": "0.1 - 1000"},
            "RXO": {"color": "#ea580c", "style": "dashed", "range": "0.1 - 1000"},
        }

        def get_pattern_id(name):
            if not name: return ""
            for k in sorted(self.PATTERN_MAP.keys(), key=len, reverse=True):
                if k in name: return self.PATTERN_MAP[k]
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
        series = []
        for name in curve_names:
            t = self._track_pool.get(name)
            if t and "series" in t:
                series.extend(t["series"])
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
