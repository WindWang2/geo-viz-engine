from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton, QMenu, QComboBox
from src.renderers.well_log.chart_engine import ChartEngine
from src.data.well_registry import get_well_data, list_wells
from src.renderers.well_log.sync_manager import SyncManager
import json
from pathlib import Path

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
            
            # Match sequences (砂层组) or member (段) for stratigraphic correlation
            seq1 = d1.intervals.sequence if d1.intervals.sequence else d1.intervals.member
            seq2 = d2.intervals.sequence if d2.intervals.sequence else d2.intervals.member
            
            for s1 in seq1:
                match = next((s for s in seq2 if s.name == s1.name), None)
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
                        source_interval_id=f"{s1.top}_{s1.bottom}_{s1.name}",
                        target_interval_id=f"{match.top}_{match.bottom}_{match.name}",
                        color=color
                    ))
        
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
