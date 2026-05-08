# Stratigraphic Flattening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Implement a "Flatten by Marker" feature in the Cross-Well tool to align multiple wells perfectly along a chosen stratigraphic sequence or member by applying dynamic depth offsets.

**Architecture:** A new dropdown in the `CrossWellPage` toolbar will list all available stratigraphic markers (derived from loaded wells). Upon selection, the application will calculate a specific `depth_offset` for each well (e.g., if "ZJ210" is at 1000m in Well A, the offset is -1000m). This offset will be passed to ECharts, shifting the entire `yAxis` so that the selected marker is rendered at Y=0 for all wells.

**Tech Stack:** Python, PySide6, ECharts.

---

### Task 1: UI for Marker Selection

**Files:**
- Modify: `src/pages/cross_well_page.py`

- [x] **Step 1: Add a ComboBox to the CrossWellPage toolbar**

```python
from PySide6.QtWidgets import QComboBox

# In CrossWellPage.__init__ (add after auto_link_btn)
self.flatten_combo = QComboBox()
self.flatten_combo.addItem("按深度 0 对齐 (默认)", userData=None)
self.flatten_combo.currentIndexChanged.connect(self._on_flatten_changed)
self.toolbar.addWidget(QLabel("对齐层位:"))
self.toolbar.addWidget(self.flatten_combo)
```

- [x] **Step 2: Implement marker harvesting when wells are added**

```python
# In CrossWellPage (add a new method)
def _update_flatten_combo(self):
    current_text = self.flatten_combo.currentText()
    
    # Collect all unique sequences/members from loaded wells
    markers = set()
    for engine in self.engines:
        data = self._well_data_cache.get(engine._well_name)
        if not data: continue
        seqs = data.intervals.sequence if data.intervals.sequence else data.intervals.member
        for s in seqs:
            if s.name:
                markers.add(s.name)
                
    self.flatten_combo.blockSignals(True)
    self.flatten_combo.clear()
    self.flatten_combo.addItem("按深度 0 对齐 (默认)", userData=None)
    for m in sorted(markers):
        self.flatten_combo.addItem(f"拉平: {m}", userData=m)
        
    # Try to restore selection
    idx = self.flatten_combo.findText(current_text)
    if idx >= 0:
        self.flatten_combo.setCurrentIndex(idx)
    self.flatten_combo.blockSignals(False)

# Call this at the end of `add_well` and `clear_all`
# self._update_flatten_combo()
```

- [x] **Step 3: Commit**
```bash
git add src/pages/cross_well_page.py
git commit -m "feat(cross-well): add marker selection combobox for flattening"
```

---

### Task 2: Offset Calculation and ECharts Rendering

**Files:**
- Modify: `src/pages/cross_well_page.py`
- Modify: `src-echarts/src/geoviz-echarts-wellog.js`

- [x] **Step 1: Update ECharts renderer to support `depthOffset`**

```javascript
// In src-echarts/src/geoviz-echarts-wellog.js, around line 550, update _doRender

const depthOffset = data.metadata.depthOffset || 0;

// Update yAxis generation
function getYAxis(commonY) {
    return {
        ...commonY,
        min: data.metadata.topDepth + depthOffset,
        max: data.metadata.bottomDepth + depthOffset
    };
}
// NOTE: For data series, the Y coordinate must ALSO be offset.
// BUT since we use the Y-axis min/max natively, if we shift the axis boundaries, the data stays at absolute depth.
// We MUST shift the data coordinates to match the new "relative" 0.

// Alternatively, keep the Y-axis absolute, but change the dataZoom window to match the offset!
// NO! If we want them aligned horizontally on the screen, the Y-axis scale itself must be offset.
// Better approach: Shift all data points by depthOffset.

// Let's modify the custom series renderItems and getSeries methods:
// 1. CurveTrack data: `data: (s.data || []).map(p => [p[1], p[0] + depthOffset])`
// 2. IntervalTrack data: `data: items.map(i => [0.5, i.top + depthOffset, i.bottom + depthOffset])`
// 3. DepthTrack label formatter: `axisLabel: { formatter: function(val) { return (val - depthOffset).toFixed(0); } }`
```
*(Wait, shifting data in JS is brittle. It's safer to shift data in Python before sending the payload!)*

- [x] **Step 2: Implement Depth Shifting in Python `_on_flatten_changed`**

```python
# In src/pages/cross_well_page.py
def _on_flatten_changed(self):
    marker_name = self.flatten_combo.currentData()
    
    import json
    import copy
    
    for engine in self.engines:
        data = self._well_data_cache.get(engine._well_name)
        if not data: continue
        
        offset = 0.0
        if marker_name:
            seqs = data.intervals.sequence if data.intervals.sequence else data.intervals.member
            match = next((s for s in seqs if s.name == marker_name), None)
            if match:
                offset = -match.top # Shift the top of the marker to exactly 0
        
        # We need to re-generate the tracks payload but with offset applied to all tops/bottoms/depths.
        # Alternatively, we can just send the 'depthOffset' flag in metadata and let JS handle the visual shift.
        # Let's send the offset and let JS shift the Y-axis min/max and DataZoom, keeping data absolute?
        # NO: ECharts grids are fixed. To align them, the easiest way is to let Python physically offset the data sent to this specific cross-well chart engine.
        
        # Re-build tracks exactly as in add_well, but apply `offset` to all depth values.
        # (See next step for the unified payload builder)
```

- [x] **Step 3: Extract a `_build_payload(data, offset)` method**

```python
# In src/pages/cross_well_page.py
def _build_engine_payload(self, data, offset=0.0):
    tracks = []
    ivs = data.intervals
    
    def get_facies_color(fname):
        if not fname: return "#e2e8f0"
        if "三角洲" in fname or "河道" in fname: return "#fef08a"
        elif "海" in fname or "浅水" in fname: return "#fed7aa"
        elif "湖" in fname: return "#bae6fd"
        elif "扇" in fname or "滩" in fname: return "#bbf7d0"
        return "#e2e8f0"
        
    facies_bg = []
    if ivs and ivs.facies and ivs.facies.phase:
        facies_bg = [{ "top": i.top + offset, "bottom": i.bottom + offset, "name": "", "color": get_facies_color(i.name) } for i in ivs.facies.phase]
        
    seq_items = ivs.sequence if ivs and ivs.sequence else ivs.member
    if seq_items:
        tracks.append({
            "type": "IntervalTrack", "name": "层位", "width": 6,
            "data": [{ "top": i.top + offset, "bottom": i.bottom + offset, "name": i.name, "color": "#f8fafc" } for i in seq_items]
        })

    gr_curve = next((c for c in data.curves if "GR" in c.name.upper()), None)
    if gr_curve:
        curve_data = [[d + offset, (v if v == v else None)] for d, v in zip(gr_curve.depth, gr_curve.values)]
        tracks.append({
            "type": "CurveTrack", "name": "GR", "width": 14,
            "series": [{"name": "GR", "color": "#1f2937", "data": curve_data}],
            "bgIntervals": facies_bg
        })

    # Depth track needs to know the offset to format labels back to real absolute depth
    tracks.append({"type": "DepthTrack", "name": "深度", "width": 6, "depthOffset": offset})

    litho_track_data = []
    if ivs and ivs.lithology:
        for l in ivs.lithology:
            color = "#e2e8f0"
            if ivs.facies and ivs.facies.phase:
                mid = (l.top + l.bottom) / 2
                facies = next((f for f in ivs.facies.phase if f.top <= mid <= f.bottom), None)
                if facies: color = get_facies_color(facies.name)
            
            # Simple pattern map
            litho_track_data.append({
                "top": l.top + offset, "bottom": l.bottom + offset, 
                "name": l.name, "lithology": "sandstone" if "砂" in l.name else "mudstone" if "泥" in l.name else "", 
                "color": color
            })
            
    if litho_track_data:
        tracks.append({
            "type": "LithologyTrack", "name": "岩性", "width": 14,
            "data": litho_track_data
        })
        
    return {
        "metadata": { "wellName": data.well_name, "topDepth": data.top_depth + offset, "bottomDepth": data.bottom_depth + offset },
        "tracks": tracks
    }
```

- [x] **Step 4: Call `_build_payload` in `add_well` and `_on_flatten_changed`**

```python
# Replace the inline track building in add_well with:
# payload = self._build_engine_payload(data, 0.0)

# Implement _on_flatten_changed full loop:
def _on_flatten_changed(self):
    marker_name = self.flatten_combo.currentData()
    for engine in self.engines:
        data = self._well_data_cache.get(engine._well_name)
        if not data: continue
        offset = 0.0
        if marker_name:
            seqs = data.intervals.sequence if data.intervals.sequence else data.intervals.member
            match = next((s for s in seqs if s.name == marker_name), None)
            if match:
                offset = -match.top
        
        payload = self._build_engine_payload(data, offset)
        engine.render_data(json.dumps(payload))
        
    # Re-run auto link if needed to fix overlay
    if self.links:
        self._auto_link()
```

- [x] **Step 5: Modify `DepthTrack` in ECharts to format absolute labels**

```javascript
// In src-echarts/src/geoviz-echarts-wellog.js -> DepthTrack.getYAxis
class DepthTrack extends Track {
    // ...
    getYAxis(commonY) {
        const offset = this.data.depthOffset || 0;
        return {
            ...commonY, gridIndex: this.index, show: true, position: 'left',
            offset: -(this.layout.w / 2),
            axisLine: { show: false },
            axisLabel: { 
                show: true, fontWeight: 'bold', fontSize: 11, align: 'center', margin: 0, verticalAlign: 'middle',
                formatter: function (value) { return (value - offset).toFixed(0); }
            },
            axisTick: { show: false }
        };
    }
}

// In tooltipFormatter
let absoluteDepth = depth - (t.depthOffset || 0); // Need to adjust the exactMouseDepth reporting too!
```

- [x] **Step 6: Commit**
```bash
git add src/pages/cross_well_page.py src-echarts/src/geoviz-echarts-wellog.js
git commit -m "feat(cross-well): implement python-side depth shifting for stratigraphic flattening"
```
