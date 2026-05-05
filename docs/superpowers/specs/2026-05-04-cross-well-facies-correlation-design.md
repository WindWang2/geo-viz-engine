# Cross-Well Facies Correlation Design Spec

## 1. Introduction
The objective is to implement a professional cross-well facies correlation section within the GeoViz Engine. This tool allows geologists to visualize and interpret the lateral continuity of sedimentary facies and stratigraphic units across multiple wells.

## 2. Architecture
The implementation follows a **Modular Component Assembly** approach (Approach 1), reusing the existing high-performance ECharts-based single-well engine.

### 2.1 Multi-Well Container (`CrossWellPage`)
- A new standalone tab in the sidebar navigation, completely independent of the existing "Well Log" (single well) page.
- Uses `QScrollArea` to support horizontal scrolling of multiple wells.
- Maintains a list of `ChartEngine` instances, one per well.
- **Layout**: `QHBoxLayout` with fixed-width "Gaps" (100-150px) between well widgets.

### 2.2 Connection Overlay (`ConnectionOverlay`)
- A transparent `QWidget` layered on top of the entire section.
- Responsibility: Drawing the "correlation polygons" between adjacent wells.
- Technology: Qt `QPainter` or an SVG overlay, updated in real-time as wells scroll or zoom.

### 2.3 Viewport Synchronization (`SyncManager`)
- Orchestrates the synchronization of vertical depth ranges across all embedded `ChartEngine` instances.
- Implementation: Listens for `dataZoom` (scroll/zoom) events from one "master" well via `QWebChannel` and broadcasts the new `startValue/endValue` to all other "slave" wells.

## 3. Data Model & Linking Logic

### 3.1 Correlation Data Structure
```python
class CorrelationLink(BaseModel):
    source_well: str
    target_well: str
    source_interval_id: str  # UID of the facies/formation interval
    target_interval_id: str
    color: str              # Usually inherited from the facies color
    is_manual: bool = False # Whether linked by user or system
```

### 3.2 Linking Algorithms
- **Auto-Suggest**: Matches intervals in adjacent wells based on identical names (e.g., "Delta Front") and overlapping sequence stratigraphic frames.
- **Heuristic Constraints**: Prevents linking if the thickness difference exceeds a certain ratio (e.g., 5x) or if it crosses known seismic horizons.

## 4. User Interaction

### 4.1 Facies Connecting
- **Manual Mode**: Click an interval block in Well A, then click an interval in Well B to create a link.
- **Deletion**: Right-click a correlation polygon to remove it.
- **Validation**: Visual highlighting of the currently selected interval to guide the user.

### 4.2 Display Configuration
- **Default View**: Facies Track + Depth Track + GR Curve.
- **Customization**: Each well has a "Tracks" icon allowing users to toggle any track (Lithology, Description, etc.) independently.
- **Alignment Modes**: 
    - **Top Align**: All wells start at Depth 0.
    - **Marker Align**: All wells aligned by a specific Stratigraphic Top (e.g., "Enping Top").
    - **Structural Align**: All wells aligned by TVDSS (Sea level).

## 5. Implementation Roadmap
1.  **Phase 1**: Layout engine for multiple `ChartEngine` instances with basic vertical sync.
2.  **Phase 2**: `ConnectionOverlay` implementation for drawing static polygons.
3.  **Phase 3**: Interaction layer (Click-to-link) and Persistence of correlation data.
4.  **Phase 4**: Advanced alignment modes (TVDSS).

## 6. Constraints
- **Vertical Accuracy**: Tooltip depth must remain perfectly accurate and synced across all wells.
- **Performance**: Must maintain 60FPS scrolling even with 5+ wells and 100+ connection polygons.
- **SVG Export**: The entire section (Wells + Connections) must be exportable as a single SVG file.
