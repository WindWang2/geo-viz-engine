from PySide6.QtWidgets import (QWidget, QLabel, QVBoxLayout, QHBoxLayout, QScrollArea, 
                             QPushButton, QMenu, QComboBox, QFileDialog, QMessageBox)
from src.renderers.well_log.chart_engine import ChartEngine
from src.data.well_registry import get_well_data, list_wells
from src.renderers.well_log.sync_manager import SyncManager
import json
from pathlib import Path
from PySide6.QtCore import QEventLoop, QPointF, QTimer

from src.data.models import CorrelationLink
from src.renderers.well_log.connection_overlay import ConnectionOverlay
from src.renderers.well_log.location_map import LocationMapWidget
from src.data.loaders import load_well_coordinates

class CrossWellPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.sync_manager = SyncManager()
        self.links = []
        
        # Toolbar
        self.toolbar = QHBoxLayout()
        self.add_well_btn = QPushButton("添加井")
        self.add_well_btn.clicked.connect(self._show_well_menu)
        self.toolbar.addWidget(self.add_well_btn)
        
        self.auto_link_btn = QPushButton("自动关联")
        self.auto_link_btn.clicked.connect(self._auto_link)
        self.toolbar.addWidget(self.auto_link_btn)

        self.flatten_combo = QComboBox()
        self.flatten_combo.addItem("按深度 0 对齐 (默认)", userData=None)
        self.flatten_combo.currentIndexChanged.connect(self._on_flatten_changed)
        self.toolbar.addWidget(QLabel("对齐层位:"))
        self.toolbar.addWidget(self.flatten_combo)

        self.clear_btn = QPushButton("清除所有")
        self.clear_btn.clicked.connect(self.clear_all)
        self.toolbar.addWidget(self.clear_btn)

        self.export_btn = QPushButton("导出剖面 (SVG)")
        self.export_btn.clicked.connect(self._on_export_section_svg)
        self.toolbar.addWidget(self.export_btn)

        self.toolbar.addStretch()
        layout.addLayout(self.toolbar)
        
        # Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.container.setStyleSheet("background: white;")
        self.well_layout = QHBoxLayout(self.container)
        self.well_layout.setSpacing(150) # Gap for connections
        self.well_layout.setContentsMargins(0, 0, 0, 0)
        self.well_layout.addStretch()
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)
        
        # Connection Overlay
        self.overlay = ConnectionOverlay(self.container, [])
        self.overlay.hide() 

        self.engines = []
        self._well_data_cache = {}

        # Location Map
        self.location_map = LocationMapWidget(self)
        self.location_map.hide()
        
        data_dir = Path(__file__).resolve().parent.parent.parent / "data"
        self._all_coordinates = load_well_coordinates(data_dir / "well_coordinates.json")

    def _show_well_menu(self):
        menu = QMenu(self)
        for well_name in list_wells():
            action = menu.addAction(well_name)
            action.triggered.connect(lambda checked, name=well_name: self.add_well(name))
        menu.exec(self.add_well_btn.mapToGlobal(self.add_well_btn.rect().bottomLeft()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.overlay.setGeometry(self.container.rect())
        self.location_map.move(10, self.height() - self.location_map.height() - 10)
        self.location_map.raise_()

    def _auto_link(self):
        self.links = []
        if len(self.engines) < 2: return
        
        def get_facies_color(fname):
            if not fname: return "#e2e8f0"
            if "三角洲" in fname or "河道" in fname: return "#fef08a" # Yellow
            elif "海" in fname or "浅水" in fname: return "#fed7aa" # Orange
            elif "湖" in fname: return "#bae6fd" # Blue
            elif "扇" in fname or "滩" in fname: return "#bbf7d0" # Green
            return "#e2e8f0"

        for i in range(len(self.engines) - 1):
            w1 = self.engines[i]._well_name
            w2 = self.engines[i+1]._well_name
            d1 = self._well_data_cache.get(w1)
            d2 = self._well_data_cache.get(w2)
            if not d1 or not d2: continue
            
            # Match stratigraphy from most detailed (sequence) to least detailed (formation)
            matches_found = False
            for source_seq, target_seq in [
                (d1.intervals.sequence, d2.intervals.sequence),
                (d1.intervals.member, d2.intervals.member),
                (d1.intervals.formation, d2.intervals.formation)
            ]:
                if not source_seq or not target_seq: continue
                
                # Check for common names, ignoring empty names
                valid_source_names = set(str(s.name).strip() for s in source_seq if str(s.name).strip())
                valid_target_names = set(str(s.name).strip() for s in target_seq if str(s.name).strip())
                common_names = valid_source_names & valid_target_names
                
                if not common_names: continue
                
                matches_found = True
                for s1 in source_seq:
                    s1_name = str(s1.name).strip()
                    if s1_name not in common_names: continue
                    # Find the first matching non-empty name
                    match = next((s for s in target_seq if str(s.name).strip() == s1_name), None)
                    if match:
                        # Determine dominant facies color for this sequence block from Well 1
                        color = "#e2e8f0"
                        if d1.intervals.facies and d1.intervals.facies.phase:
                            mid = (s1.top + s1.bottom) / 2
                            facies = next((f for f in d1.intervals.facies.phase if f.top <= mid <= f.bottom), None)
                            if facies:
                                color = get_facies_color(facies.name)
                                
                        self.links.append(CorrelationLink(
                            source_well=w1, target_well=w2,
                            source_interval_id=f"{s1.top}_{s1.bottom}_{s1_name}",
                            target_interval_id=f"{match.top}_{match.bottom}_{s1_name}",
                            color=color
                        ))
                break # Stop searching coarser levels once we have matches
        
        self.overlay.set_links(self.links)
        self._refresh_overlay_coords()

    def _build_engine_payload(self, data, offset=0.0):
        tracks = []
        ivs = data.intervals

        def get_facies_color(fname):
            if not fname: return "#e2e8f0"
            if "三角洲" in fname or "河道" in fname: return "#fef08a" # Yellow
            elif "海" in fname or "浅水" in fname: return "#fed7aa" # Orange
            elif "湖" in fname: return "#bae6fd" # Blue
            elif "扇" in fname or "滩" in fname: return "#bbf7d0" # Green
            return "#e2e8f0"
        
        facies_bg = []
        if ivs and ivs.facies and ivs.facies.phase:
            facies_bg = [{ "top": i.top + offset, "bottom": i.bottom + offset, "name": "", "color": get_facies_color(i.name) } for i in ivs.facies.phase]
        
        # 1. Stratigraphy (砂层组 or 地层单位)
        if ivs and ivs.sequence:
            tracks.append({
                "type": "IntervalTrack", "name": "砂层组", "width": 8,
                "data": [{ "top": i.top + offset, "bottom": i.bottom + offset, "name": i.name, "color": "#f8fafc" } for i in ivs.sequence]
            })
        if ivs and ivs.member:
            tracks.append({
                "type": "IntervalTrack", "name": "地层单位", "width": 8,
                "data": [{ "top": i.top + offset, "bottom": i.bottom + offset, "name": i.name, "color": "#f8fafc" } for i in ivs.member]
            })
        elif ivs and ivs.formation:
            tracks.append({
                "type": "IntervalTrack", "name": "地层单位", "width": 8,
                "data": [{ "top": i.top + offset, "bottom": i.bottom + offset, "name": i.name, "color": "#f8fafc" } for i in ivs.formation]
            })

        # 2. GR Curve (with Facies background)
        gr_curve = next((c for c in data.curves if "GR" in c.name.upper()), None)
        if gr_curve:
            curve_data = [[d + offset, (v if v == v else None)] for d, v in zip(gr_curve.depth, gr_curve.values)]
            tracks.append({
                "type": "CurveTrack", "name": "GR", "width": 14,
                "series": [{"name": "GR", "color": "#1f2937", "data": curve_data}],
                "bgIntervals": facies_bg
            })

        # 3. Depth
        tracks.append({"type": "DepthTrack", "name": "深度", "width": 6, "depthOffset": offset})

        # 4. Lithology with Facies background colors
        PATTERN_MAP = {
            "砂岩": "sandstone", "泥岩": "mudstone", "灰岩": "limestone",
            "白云岩": "dolomite", "页岩": "shale", "粉砂岩": "siltstone"
        }
        def get_pattern(name):
            if not name: return ""
            for k, v in PATTERN_MAP.items():
                if k in name: return v
            return ""

        litho_track_data = []
        if ivs and ivs.lithology:
            for l in ivs.lithology:
                color = "#e2e8f0" # Default gray
                if ivs.facies and ivs.facies.phase:
                    mid = (l.top + l.bottom) / 2
                    facies = next((f for f in ivs.facies.phase if f.top <= mid <= f.bottom), None)
                    if facies:
                        color = get_facies_color(facies.name)
                
                litho_track_data.append({
                    "top": l.top + offset, "bottom": l.bottom + offset, 
                    "name": l.name, "lithology": get_pattern(l.name), 
                    "color": color
                })
        
        if litho_track_data:
            tracks.append({
                "type": "LithologyTrack", "name": "岩性", "width": 14,
                "data": litho_track_data
            })
        elif facies_bg:
             tracks.append({
                "type": "IntervalTrack", "name": "沉积相", "width": 14,
                "data": [{ "top": i["top"], "bottom": i["bottom"], "name": i["name"], "color": i["color"] } for i in facies_bg]
            })

        return {
            "metadata": { "wellName": data.well_name, "topDepth": data.top_depth + offset, "bottomDepth": data.bottom_depth + offset, "depthOffset": offset },
            "tracks": tracks
        }

    def add_well(self, well_name):
        entry = get_well_data(well_name)
        if not entry: return

        loader_fn, xls_path, config = entry
        data = loader_fn(xls_path, well_name=well_name)
        self._well_data_cache[well_name] = data

        engine = ChartEngine(self)
        engine._well_name = well_name
        engine._flatten_offset = 0.0
        engine.setMinimumWidth(300)
        engine.setMaximumWidth(600)
        
        # Insert before the last stretch
        self.well_layout.insertWidget(self.well_layout.count() - 1, engine)
        self.engines.append(engine)
        self.overlay._engines = self.engines
        self.sync_manager.register_engine(engine)

        payload = self._build_engine_payload(data, 0.0)
        
        engine.bridge.ready.connect(lambda: engine.render_data(json.dumps(payload)))
        engine.bridge.zoom_changed.connect(self._refresh_overlay_coords)
        
        self.overlay.show()
        self.overlay.raise_()
        self._update_flatten_combo()
        self._update_location_map()

    def _update_location_map(self):
        selected_wells = []
        for engine in self.engines:
            w_name = engine._well_name
            coord = next((c for c in self._all_coordinates if c.name == w_name), None)
            if coord:
                selected_wells.append((coord.longitude, coord.latitude, w_name))
        
        if selected_wells:
            self.location_map.set_wells(selected_wells)
            self.location_map.show()
            self.location_map.raise_()
        else:
            self.location_map.hide()

    def _update_overlay_cache(self, engine, depth, y):
        # Round to 2 decimal places to avoid float comparison issues
        rounded_depth = round(float(depth), 2)
        self.overlay.update_depth_cache(engine, rounded_depth, y)

    def _refresh_overlay_coords(self):
        self.overlay.setGeometry(self.container.rect())
        for link in self.links:
            e1 = next((e for e in self.engines if e._well_name == link.source_well), None)
            e2 = next((e for e in self.engines if e._well_name == link.target_well), None)
            if not e1 or not e2: continue
            
            p1_top, p1_bot = float(link.source_interval_id.split('_')[0]), float(link.source_interval_id.split('_')[1])
            p2_top, p2_bot = float(link.target_interval_id.split('_')[0]), float(link.target_interval_id.split('_')[1])
            
            # Execute synchronously-feeling callbacks to update depth cache
            for engine, depth in [(e1, p1_top), (e1, p1_bot), (e2, p2_top), (e2, p2_bot)]:
                rounded_depth = round(depth, 2)
                offset = getattr(engine, '_flatten_offset', 0.0)
                query_depth = depth + offset
                engine.view.page().runJavaScript(
                    f"window.geoviz ? window.geoviz.getDepthY({query_depth}) : 0",
                    lambda y, e=engine, d=rounded_depth: self._update_overlay_cache(e, d, y)
                )

    def _on_flatten_changed(self):
        idx = self.flatten_combo.currentIndex()
        target_marker = self.flatten_combo.itemData(idx)

        import json
        for engine in self.engines:
            data = self._well_data_cache.get(engine._well_name)
            if not data: continue

            offset = 0.0
            if target_marker == "TVDSS":
                offset = -data.datum_elevation
            elif target_marker and data.intervals:
                # Look in sequence, then member, then formation
                lists_to_check = [data.intervals.sequence, data.intervals.member, data.intervals.formation]
                for seq_items in lists_to_check:
                    if seq_items:
                        match = next((item for item in seq_items if item.name == target_marker), None)
                        if match:
                            offset = -match.top
                            break
            
            engine._flatten_offset = offset
            payload = self._build_engine_payload(data, offset)
            engine.render_data(json.dumps(payload))
            
        self._auto_link()

    def _update_flatten_combo(self):
        markers = set()
        for engine in self.engines:
            data = self._well_data_cache.get(engine._well_name)
            if not data or not data.intervals: continue
            
            lists_to_collect = [data.intervals.sequence, data.intervals.member, data.intervals.formation]
            for seq_items in lists_to_collect:
                if seq_items:
                    for item in seq_items:
                        if item.name:
                            markers.add(item.name)
        
        current_text = self.flatten_combo.currentText()
        
        self.flatten_combo.blockSignals(True)
        self.flatten_combo.clear()
        self.flatten_combo.addItem("按深度 0 对齐 (默认)", userData=None)
        self.flatten_combo.addItem("按海拔 (TVDSS) 对齐", userData="TVDSS")
        for m in sorted(markers):
            self.flatten_combo.addItem(f"拉平: {m}", userData=m)
            
        idx = self.flatten_combo.findText(current_text)
        if idx >= 0:
            self.flatten_combo.setCurrentIndex(idx)
        self.flatten_combo.blockSignals(False)

    def _on_export_section_svg(self):
        if not self.engines:
            QMessageBox.warning(self, "导出失败", "请先添加井")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "导出剖面 (SVG)", "", "SVG Files (*.svg)")
        if not file_path:
            return

        # 1. Collect SVGs from all engines
        svg_map = {}
        loop = QEventLoop()
        
        def handle_svg(svg_str, engine=None):
            svg_map[engine] = svg_str
            if len(svg_map) == len(self.engines):
                loop.quit()

        for engine in self.engines:
            # Disconnect previous if any (though unlikely here)
            try: engine.bridge.svg_received.disconnect()
            except: pass
            
            engine.bridge.svg_received.connect(lambda s, e=engine: handle_svg(s, e))
            engine.export_svg()

        # Wait for all SVGs to be collected (with timeout just in case)
        timer = QTimer()
        timer.singleShot(5000, loop.quit) # 5s timeout
        loop.exec()

        if len(svg_map) < len(self.engines):
            QMessageBox.critical(self, "导出错误", "获取部分井的 SVG 失败 (超时)")
            return

        # 2. Stitching
        total_w = self.container.width()
        total_h = self.container.height()
        
        svg_parts = [
            f'<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
            f'<svg width="{total_w}" height="{total_h}" viewBox="0 0 {total_w} {total_h}" xmlns="http://www.w3.org/2000/svg">',
            '<!-- Generated by Geo-Viz Engine Cross-Well Export -->'
        ]

        # Add Wells
        for engine in self.engines:
            rect = engine.geometry()
            well_svg = svg_map.get(engine, "")
            # Ensure we wrap the well SVG in a nested <svg> with correct offset
            # Strip XML declaration if present in well_svg
            if "<?xml" in well_svg:
                well_svg = well_svg.split("?>", 1)[-1]
            
            svg_parts.append(f'<g transform="translate({rect.x()}, {rect.y()})">')
            # Some ECharts SVGs might have width/height as attributes, we should ideally keep them or use nested <svg>
            # Nested <svg> with x,y is very robust.
            svg_parts.append(f'<svg x="0" y="0" width="{rect.width()}" height="{rect.height()}">')
            svg_parts.append(well_svg)
            svg_parts.append('</svg>')
            svg_parts.append('</g>')

        # Add Connections
        if self.links:
            svg_parts.append('<!-- Correlation Polygons -->')
            for link in self.links:
                try:
                    src_engine = next((e for e in self.engines if e._well_name == link.source_well), None)
                    tgt_engine = next((e for e in self.engines if e._well_name == link.target_well), None)
                    if not src_engine or not tgt_engine: continue

                    parts_s = link.source_interval_id.split('_')
                    parts_t = link.target_interval_id.split('_')
                    s_top, s_bot = round(float(parts_s[0]), 2), round(float(parts_s[1]), 2)
                    t_top, t_bot = round(float(parts_t[0]), 2), round(float(parts_t[1]), 2)

                    y_s_top = self.overlay._depth_cache.get((src_engine, s_top))
                    y_s_bot = self.overlay._depth_cache.get((src_engine, s_bot))
                    y_t_top = self.overlay._depth_cache.get((tgt_engine, t_top))
                    y_t_bot = self.overlay._depth_cache.get((tgt_engine, t_bot))

                    if None in (y_s_top, y_s_bot, y_t_top, y_t_bot): continue

                    src_rect = src_engine.geometry()
                    tgt_rect = tgt_engine.geometry()
                    
                    x_s = src_rect.right()
                    x_t = tgt_rect.left()
                    
                    points = [
                        (x_s, src_rect.y() + y_s_top),
                        (x_t, tgt_rect.y() + y_t_top),
                        (x_t, tgt_rect.y() + y_t_bot),
                        (x_s, src_rect.y() + y_s_bot)
                    ]
                    pts_str = " ".join([f"{p[0]},{p[1]}" for p in points])
                    
                    color = link.color
                    svg_parts.append(f'<polygon points="{pts_str}" fill="{color}" fill-opacity="0.5" stroke="{color}" stroke-width="1" />')
                except Exception as e:
                    print(f"Export link error: {e}")

        svg_parts.append('</svg>')

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(svg_parts))
            QMessageBox.information(self, "导出成功", f"剖面已保存至: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"写入文件出错: {str(e)}")

    def clear_all(self):
        for engine in self.engines:
            self.well_layout.removeWidget(engine)
            engine.deleteLater()
        self.engines = []
        self.links = []
        self.overlay.set_links([])
        self.sync_manager = SyncManager()
        self.overlay._engines = []
        self._well_data_cache = {}
        self._update_flatten_combo()
        self.location_map.hide()
