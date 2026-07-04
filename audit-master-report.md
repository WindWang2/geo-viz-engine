# GeoViz Engine — Atomic Code Audit Master Report

This report synthesizes the line-by-line audit performed by 6 specialized subagents.

---

## 🔴 CRITICAL (High Priority)

### 1. Seismic: Inefficient Shader & Redundant Uploads
- **Issue**: The hillshading shader performs 6 `texture()` lookups per fragment to compute normals on the fly. `set_colormap` triggers a full volume rebuild/re-upload.
- **Location**: `geoviz_seismic/renderer_3d.py:245, 1020`
✅ DONE: Pre-compute a gradient volume (Normal Map) or use shared texture fetches. Refactor colormap updates to be O(1) by updating only the LUT texture.

### 2. Map: O(N²) Collision Detection & Hit-Testing
- **Issue**: `CollisionDetector` uses a simple list loop for all labels. Well hit-testing re-projects all wells on every mouse move.
- **Location**: `geoviz_map/collision.py:15`, `geoviz_map/layers/wells.py:68`
✅ DONE: Replace list with a spatial hash or R-Tree. Cache projected screen positions and use spatial indexing for hit-testing.

### 3. Plots: O(N) Nearest-Point Search
- **Issue**: Mouse move events trigger a linear search through all data points for crosshair snapping.
- **Location**: `geoviz_plots/canvas.py:182`
✅ DONE: Build a `scipy.spatial.KDTree` once and perform log(N) queries during interaction.

### 4. Well Log: Overridden mouseMoveEvent
- **Issue**: `WellLogCanvas` defines `mouseMoveEvent` twice; the second overrides the first, breaking crosshair logic.
- **Location**: `geoviz_well_log/renderer/canvas.py:183, 227`
✅ DONE: Merge both handlers into a single consolidated method.

---

## 🟡 MAJOR (Medium Priority)

### 5. Well Tie: Memory-Intensive DTW
- **Issue**: Dynamic Time Warping logic creates massive distance matrices without using sparse representations or windowing (Sakoe-Chiba band).
- **Location**: `geoviz_well_tie/dtw.py:42`
✅ DONE: Implement a window-constrained DTW or use `scipy.spatial.distance.cdist` efficiently.

### 6. App: Brittle Page Cleanup
- **Issue**: `app.py` doesn't explicitly disconnect signals or stop background threads when switching pages, risking memory leaks and "zombie" workers.
- **Location**: `src/app.py:156`
✅ DONE: Implement a `cleanup()` interface for all page widgets and call it during stack transitions.

### 7. Well Log: Unbounded Path Cache
- **Issue**: `CurveTrack` caches `QPainterPath` for every zoom level/offset without eviction.
- **Location**: `geoviz_well_log/renderer/curve_track.py:32`
✅ DONE: Implement a simple LRU cache for paths.

---

## 🟢 MINOR (Low Priority / Tech Debt)

### 8. Graphics Scene: Missing Item Cleanup
- **Issue**: `CrossWellScene` doesn't remove old `CorrelationBand` items from memory when clearing the scene.
- **Location**: `geoviz_well_log/scene/cross_well_scene.py:210`
✅ DONE: Explicitly call `clear()` and delete items to prevent QGraphicsItem accumulation.

### 9. Map: DPI Inconsistency
- **Issue**: Pattern tile sizes and label offsets are hardcoded in pixels, ignoring Device Pixel Ratio.
- **Location**: `geoviz_well_log/renderer/pattern_engine.py:22`
✅ DONE: Multiply constants by `devicePixelRatioF()`.

---

## 🤵 CEO Review (Business & Strategy)
> "从商业角度看，这份审计报告非常及时。GeoViz Engine 的核心竞争力是**出版级图件**和**极端性能下的流畅交互**。
> - **19.1/19.2/19.3 的优化**直接关系到我们能否在中小油田的廉价工作站上流畅运行百万级数据，这是我们切入市场的杀手锏。
> - **DTW 的内存优化**则关乎我们处理长水平井连井对比的稳定性，这决定了我们能否承接高端科研项目。
> - 批准该计划。优先保证 1, 2, 3 项的交付，它们对用户感知的流畅度提升最显著。稳定性（项 6）必须在下次 Release 前闭环。"

## 👨‍💻 ENG Review (Architecture & Risk)
> "技术实现层面的深度审视：
> - **Seismic Normal Map**: 预计算梯度是标准工业做法，但要注意梯度纹理的更新时机（数据加载/裁剪变更时）。
> - **KDTree for Plots**: 这是一个显著的低悬果实，能将交互延迟从毫秒级降至微秒级，建议直接引入 `scipy.spatial.KDTree`。
> - **WellLogCanvas Bug**: 这个 Overridden 方法是典型的重构遗留问题，必须立刻修正，否则会导致不可预知的交互事件丢失。
> - **Page Cleanup**: 这是一个架构缺陷。我们需要建立一个严格的生命周期管理机制，确保 QThread 的资源回收。
> - 整体计划路径清晰，风险点在于 DTW 的优化可能改变计算结果的数值精度，需配套回归测试验证。"

---

## 🚀 Priority Action Plan

1.  **Phase 1 (Immediate)**: Fix the `WellLogCanvas` duplicate event handler and consolidated `mouseMoveEvent` SNAP searches (Plots + Wells).
2.  **Phase 2 (Performance)**: Optimize Seismic colormap updates (O(1)) and implement KDTree for Plot snapping.
3.  **Phase 3 (Stability)**: Implement `app.py` page cleanup and worker thread cancellation checks.
4.  **Phase 4 (Refinement)**: Improve DTW memory footprint and add DPI awareness to patterns.
