# Progress Log — GeoViz Engine

## Project Status: Phase 1–11 COMPLETE, Refactor COMPLETE, Phase 11.8 COMPLETE

### Session: 2026-06-01 (Phase 11.8 — Level Lock & Overlaps)

#### Implementation Completed
- **11.8-A (Level Lock)**: Added `层级锁定` combobox in `src/pages/paleo_map/page.py` toolbar. Connected to `canvas.set_locked_level(level)`. `PaleoMapCanvas._resolve_level_name` now returns `_locked_level` when locked, ensuring the map renders the exact locked facies level at all zoom display scales.
- **11.8-B (Legend Overlap)**: Shifted facies swatches drawing start `y` coordinate in `packages/geoviz_paleo_map/geoviz_paleo_map/layers/legend.py` from `y0 + PADDING + ROW_H + 4` to `y0 + PADDING + ROW_H + 12`, adding 8 pixels of vertical spacing between "图例" title and the first legend element.
- **11.8-C (Scale Slider Overlap)**: Completely removed the overlapping transition labels (`相→亚相`, etc.) from the slider bar. Implemented a spacing guard `if tx - last_x >= 45.0:` in `packages/geoviz_paleo_map/geoviz_paleo_map/floating_slider.py` to ensure tick labels under the slider always have at least 45 pixels of horizontal spacing.
- **Verification**: Ran the full test suite. 684 passed, 4 skipped.

### Session: 2026-05-30 (Phase 8 + Legacy)

#### Reviews Completed
- CEO Review: CLEAN — 6/6 proposals accepted, Well-Seismic Tie Visualization selected (SELECTIVE EXPANSION mode)
- Eng Review (Run 3): 22 findings — 7 critical, 8 high, 7 medium

#### Sub-phase 1: Core Library + Spatial Reference + Overlay API (DONE ✅)
- 8 files modified across geoviz-well-tie and geoviz-seismic packages
- 44 new tests, all green → 572 total
- Key additions: generate_synthetic_twt, resample_to_seismic_grid, BinGridGeometry, auto_tie, ProfileVD overlay API, read_trace

#### Sub-phase 2: WellTiePanel + SeismicView Integration (DONE ✅)
- `well_tie_panel.py` — WellTiePanel widget with wavelet controls, auto-tie, export
- `seismic_view.py` — toolbar toggle button + lazy panel creation
- 17 new tests, all green → 589 total

#### Phase 8 Shipped (DONE ✅)
- Committed: `75988c04` + `5af8ec15` (docs)
- Pushed to origin/main

#### A7: CheckshotTable / WellTieCalibration Dedup (DONE ✅)
- `CheckshotTable` refactored: delegates to `WellTieCalibration` instead of own `np.interp`
- New: `CheckshotTable.calibration` property exposes underlying `WellTieCalibration`
- Side benefit: `interpolate_twt` / `interpolate_depth` now support array inputs
- TDD: 4 red → all green + 5 regression = 9 new tests
- Dependency: cross-well now depends on well-tie (pure NumPy, zero Qt)

#### Phase 2 Legacy: DTW Ghost Picks + Dual-Axis (DONE ✅)
- `_handle_pick_click`: left-click on DTW ghost pick now calls `accept_dtw_pick()` (source → manual)
- `_paint_twt_axis`: PickingOverlay renders TWT scale labels when domain="TWT" and seismic_tie loaded
- 8 new tests (DTW accept model 4 + dual-axis 4), all green
- 43 cross-well tests total, 589 full suite

## Test Results History
| Date | Tests | Status |
|------|-------|--------|
| 2026-05-29 (Phase 4) | 490 passed | ✅ |
| 2026-05-29 (Phase 5) | 497 passed | ✅ |
| 2026-05-29 (Phase 6) | 512 passed | ✅ |
| 2026-05-30 (Phase 7) | 528 passed | ✅ |
| 2026-05-30 (Phase 8.1) | 572 passed | ✅ |
| 2026-05-30 (Phase 8.2) | 589 passed | ✅ |
| 2026-05-30 (A7 dedup) | 589 passed | ✅ |
| 2026-05-30 (Phase 9) | 600 passed | ✅ |
| 2026-05-30 (Phase 9b) | 601 passed | ✅ |
| 2026-05-31 (Phase 10) | 617 passed | ✅ |
| 2026-05-31 (Refactor) | 617 passed | ✅ |
| 2026-05-31 (Phase 11) | 636 passed | ✅ |
| 2026-05-31 (Phase 11.5-A) | 636 passed | ✅ |
| 2026-05-31 (Phase 11.5-B + D) | 668 passed | ✅ |
| 2026-05-31 (Phase 11.6-A + C partial) | 668 passed | ✅ |
| 2026-05-31 (Phase 11.6-B chrome bypass) | 669 passed | ✅ |
| 2026-05-31 (Phase 11.6-C publishing export) | 674 passed | ✅ |
| 2026-05-31 (Phase 11.6-H toolbar 2 rows) | 674 passed, 4 skipped | ✅ |
| 2026-05-31 (Phase 11.6-F DTW wire-up + ref_idx fix) | 674 passed, 4 skipped (global) + 46 passed (cross-well pkg, +3) | ✅ |
| 2026-05-31 (Phase 11.6-G manual pick UX) | 680 passed, 4 skipped | ✅ |

## 5-Question Reboot Check
| Question | Answer |
|----------|--------|
| Where am I? | Phase 11 COMPLETE — Curvature (dip/azimuth + 6 kinds) shipped, 636 tests green |
| Where am I going? | Awaiting user direction — Phase 12 (3D dual-volume rendering) candidate |
| What's the goal? | Maintain 636 green tests; pick next phase |
| What have I learned? | PatternEngine composite brush pipeline; QSvgGenerator limitations (raster patterns); spec has 16 facies types (not 24); CMYK mapping viable for small palettes; PaintScheduler needs RuntimeError guard on deleted widgets; GPU coherence offload pattern (CuPy per-chunk) |
| What have I done? | A7 dedup + Phase 2 legacy + Phase 9 Coherence + Phase 9b GPU + Phase 10 PaleoMap + Refactor — 617 green, all pushed |

### Session: 2026-05-31 (Phase 11 — Curvature)

#### Design Approved
- **Algorithm:** Direct second-derivative method (Sobel gradient → dip → curvature)
- **API:** `compute_dip`, `compute_azimuth`, `compute_curvature` in `attributes.py`
- **Curvature types:** Gaussian, Mean, Maximum, Minimum, Dip, Strike
- **GPU support:** CuPy per-chunk offload (reuse Phase 9b pattern)
- **UI integration:** `_attr_combo` 新增 6 项 (倾角/方位角/4种曲率)
- **Tests:** ~15 new tests target

#### Commits
- TBD (Phase 11 implementation pending commit)

#### Implementation Completed
- `compute_dip(data)` — central differences of seismic amplitude → atan(grad_spatial/grad_t); supports 2D and 3D
- `compute_azimuth(dip_il, dip_xl)` — atan2 → [0, 2π) radians
- `compute_curvature(data, kind=...)` — 6 kinds (gaussian/mean/max/min/dip/strike); slope-gradient method with uniform-filter smoothing
- `_compute_slope` helper — returns linear slope (no atan) for correct second-derivative behavior
- UI: `_attr_combo` extended to 14 items (6 new curvature/dip/azimuth entries at idx 8-13)
- `_apply_attr` dispatches curvature for idx ≥ 8
- 19 new tests (`tests/test_curvature.py`): shape, value range, synthetic dome/syncline sign-flip, edge handling, GPU consistency
- Full suite: **636 passed, 3 skipped**

### Session: 2026-05-31 (Refactor — seismic_view.py split)

#### Refactor Completed
- `seismic_view.py`: 1471 → 1283 lines (-188)
- New `workers.py`: SyntheticWorker + SegyLoadWorker + generate_synthetic
- New `colorbar_widget.py`: ColorbarWidget standalone
- New `dialogs/crossplot.py`: CrossplotDialog + CrossplotCanvas
- New `dialogs/horizon_manager.py`: HorizonManagerDialog
- Removed unused Qt imports (QPainter, QColor, QLinearGradient, QThread, Signal)
- 617 tests passed, 3 skipped

#### Commits
- `3e3b5ce6` — refactor: split seismic_view.py into focused modules
- `de3f09c1` — docs: sync planning files after seismic_view.py refactor

#### Phase 9: Coherence (C3 eigenstructure) (DONE ✅)
- `compute_coherence_c3` — C3 eigenstructure coherence via power iteration
- 11 tests (shape, value range, window params, edge handling), all green
- Adaptive chunking for memory efficiency (~100 MB target per chunk)
- 600 total tests passed

#### Phase 9b: GPU Acceleration for Coherence (DONE ✅)
- Added `use_gpu` parameter to `compute_coherence_c3`
- CuPy power-iteration offload per-chunk with automatic fallback to CPU
- GPU path numerically identical to CPU (max diff ~1.2e-06, float32)
- Benchmark speedup: ~1.5-1.9x on RTX 4090 (15 GB)
  - (50, 50, 200): 4.0s → 2.1s (1.9x)
  - (100, 100, 300): 25.9s → 16.8s (1.5x)
  - (200, 200, 400): 136.3s → 87.3s (1.6x)
- 12 coherence tests (including new `TestCoherenceC3GpuConsistency`)
- Full suite: 601 passed

### Session: 2026-05-30 (Phase 10 — PaleoMap Texture + Export Design)

#### Design Completed
- Reviewed Q/HS 1011-2016 spec (Appendix O 沉积相图式, Appendix M 岩石图式)
- Explored existing PatternEngine, FaciesStyleResolver, FaciesPolygonsLayer, save_export.py
- Presented 2-3 approaches for both subsystems; user approved
- Design spec written: `docs/superpowers/specs/2026-05-30-paleo-map-texture-export-design.md`
- Spec self-reviewed and fixed (pattern count 24→16, existing patterns not moved)
- Committed: `fee0051d`

#### Design Decisions
- Extend PatternEngine with `get_facies_brush()` + new `facies/` SVG subdir
- QSvgGenerator for true vector SVG export
- Professional figure wrapper with standardized frame (title, scale bar, north arrow, legend, grid)
- CMYK via lookup table (small known palette)
- Directional patterns (物源方向) deferred to Phase 2

#### Implementation Plan Completed
- Plan written: `docs/superpowers/plans/2026-05-30-paleo-map-texture-export.md`
- 10 tasks, 50+ steps covering: pattern SVGs (13 files), PatternEngine extension, style resolver, vector SVG export, professional figure export, comprehensive tests (target 620+)
- Plan self-reviewed: spec coverage complete, no placeholders, types consistent
- Committed: `24d5710e`

### Session: 2026-05-31 (Phase 10 — Implementation Complete)

#### Implementation Completed
- 13 facies pattern SVGs created (`packages/geoviz_well_log/assets/patterns/facies/`)
- `PatternEngine.get_facies_brush()` + `get_composite_brush()` extensions
- `FaciesStyleResolver` updated with `FACIES_PATTERNS` mapping (16 facies → pattern_id)
- `export_vector_svg()` — true vector SVG via `QSvgGenerator`
- `export_professional_figure()` — publishing-grade figure with standardized frame
- 16 new tests (`test_export_vector.py`, `test_export_professional.py`, `test_facies_patterns.py`)
- Full suite: **617 passed, 3 skipped**

#### Bugfix
- `PaintScheduler._do_update()` now catches `RuntimeError` when widget is destroyed (test teardown safety)

#### Commits
- `8ca37621` — feat: export new public APIs (export_vector_svg, export_professional_figure)

## Pending Items
- Phase 11.6 (用户回归测试): 6 项剩余 (B/C/D/E/F/G)

### Session: 2026-05-31 (Phase 11.6 — 用户回归测试)

#### 用户测试发现 8 项问题（已记入 task_plan Phase 11.6）
1. 11.6-A **地图：点井无响应** — ✅ FIXED
2. 11.6-B **古地理图：图例/指南针/比例尺消失** — ✅ FIXED
3. 11.6-C **古地理图：PDF 导出空白** — ✅ FIXED（委托 export_professional_figure）
4. 11.6-D 古地理图：缩放后文字模糊 — TODO
5. 11.6-E 连井：自动连井太慢 — TODO
6. 11.6-F 连井：自动连井位置不对 — ✅ FIXED（DTW 引擎 ref_depth 修复 + 接入 producer，UI 接线 pending）
7. 11.6-G 连井：手动拾取交互体验差 — TODO
8. 11.6-H 地震：toolbar 显示不完整 — TODO

#### 11.6-A Fix (commit 12a60273)
- **根因**：`WellsLayer._screen_positions` 存的是 LayerPixmapCache 2× buffer 的内部坐标，不是实际屏幕坐标；`hit_test` 复用它 → 永远 miss
- **修复**：`packages/geoviz_map/geoviz_map/layers/wells.py` `hit_test` 始终用 live viewport 重投影
- **教训**：pixmap cache 只能存像素，命中检测必须现算坐标
- 125 map+wells 相关测试 green

#### 11.6-C Partial Fix (commit 12a60273)
- `src/pages/paleo_map/page.py:424` `printer.pageRect(QPrinter.DevicePixel).toRect()` 修复 QSizeF → QSize 类型错误
- 仍待补 publishing-grade frame（图名/比例尺/指南针/图例）

#### 11.6-B Fix（commit pending）
- **根因**：与 11.6-A 同源 — `LayerPixmapCache._rerender` 用 `buf_w = vp.width * 2`、`buf_h = vp.height * 2` 创建一个 2× 的 `buf_vp` 给 layer 绘制；chrome layer（北针/比例尺/图例/标题）锚定到 `viewport.width` / `viewport.height` 时，锚点（如 `viewport.width - 46`）实际落在 `2 * vp.width - 46`，blit 回真实 viewport 时早已偏离屏幕外
- **修复**：
  - `PaleoLayer` 基类加 `is_chrome: bool = False`
  - `TitleLayer` / `NorthArrowLayer` / `ScaleBarLayer` / `LegendLayer` 标记 `is_chrome = True`
  - `PaleoMapCanvas._rebuild_layer_caches`：chrome layer 对应位置存 `None`，跳过 LayerPixmapCache
  - `paintEvent`：`cache is None` 时直接 `layer.paint(painter, self._viewport)`
  - `_rebuild_topology_paths` mark_dirty 跳过 `None` cache
- **回归测试**：`test_chrome_layers_bypass_pixmap_cache` 断言 chrome 类对应 cache 为 None，数据层（FaciesPolygonsLayer）仍有 cache
- **教训**：LayerPixmapCache 的 2× buffer 模式只适合 world-coord 内容；任何锚定到 viewport edge 的 chrome 必须直绘 — 这是与 11.6-A "pixmap cache 只能存像素" 同根的第二个表现
- 669 tests passed（+1），3 skipped

#### 11.6-C Full Fix（commit pending）
- **修复**：`src/pages/paleo_map/page.py` 的 `_export_pdf` / `_export_svg` / `_export_png` 全部改为委托 `geoviz_paleo_map.export_professional.export_professional_figure`
- 自动获得 title（用 current period）/ 网格边框 / 刻度 / 比例尺 / 指南针 / 图例 — publishing-grade
- 新增 `_figure_title()` helper：`{period} 古地理相图`，period 为空时退到 "古地理图"
- 5 个新测试 `test_paleo_map_page_export.py`：3 个 mock 化路径调用断言，1 个 fallback title，1 个真实 export 出 >1KB PDF
- 674 tests passed（+5），3 skipped
- **教训**：图层级独立 package 已经把 publishing 能力做好了；page 层不该自己撸 QPainter on QPrinter — 这是 11.6-C "导出 PDF 空白" 看起来像 crash 实则是 missing frame 的根本原因

#### 11.6-H Fix（commit pending）
- **修复**：`packages/geoviz_seismic/geoviz_seismic/seismic_view.py` `_build_toolbar` 现返回一个 `QWidget` 容器，内含两个 `QToolBar` 垂直堆叠
- **Row 1（主操作）**：加载/Demo/层位/层位管理 ‖ 拾取/清除/导出/标注 ‖ 切片信息+读出 ‖ 井震标定
- **Row 2（视图与属性）**：3D模式/透明度/剖面/显示/色标 ‖ 裁剪/属性/RGB(R/G/B)/交叉图 ‖ IL/XL/T 滑块
- 新增 `_toolbar_row1` / `_toolbar_row2` 字段供测试和外部布局调整
- **回归测试**：`test_seismic_view_toolbar_split_into_two_rows` 断言两个 QToolBar 都存在且关键控件分布正确（pick_btn/well_tie_btn → row1；3d_mode/attr/sliders/clip → row2）
- 674 passed (+1)，4 skipped（新增测试随 pyvistaqt 同步跳过）
- **教训**：toolbar 拆行不要简单加 horizontal layout — `QToolBar.addWidget` 有 separator/spacing 行为，复用两个 QToolBar 实例比手撸 QHBoxLayout 更原生

#### 11.6-F Fix（commit pending）
- **双重根因**：
  1. `dtw_engine.py:74` `ref_idx = n // 2` 硬编码 — 无论用户在哪个深度拾取，DTW 永远从参考曲线中点找匹配
  2. 生产代码层面 DTWEngine 实际**从未被调用** — `CrossWellWidget.auto_link()` 仅做 formation-name 字符串匹配，DTW 引擎是孤儿
- **修复**：
  - `dtw_engine.correlate()` 新增 `ref_depth: float | None = None` 参数；`ref_idx = argmin(abs(ref_depths - ref_depth))`；用 `np.median(target_indices)` 收敛多对一映射
  - `CrossWellCanvas` 新增 `_extract_curve()` 提取曲线（优先 GR/SP/RT）+ `propagate_pick_via_dtw(ref_well, ref_depth, formation, band_radius=None)` 产生 ghost picks
  - 副作用 fix：`canvas.py` 补 `import numpy as np`（_paint_twt_axis 一直在用却没导入，latent bug）
- **回归测试**（3 个，全在 cross-well 包内）：
  - `test_ref_depth_propagates_correctly`：3 个不同 ref_depth（1300/2000/2700）必须得到 3 个不同结果，误差 < 3 sample
  - `test_ref_depth_default_is_midpoint`：backward-compat — 不传 ref_depth ≡ 传 midpoint depth
  - `test_propagate_pick_via_dtw`：end-to-end 集成测试，200-sample 曲线 + 20-sample shift，REF 拾取 1800m 在 TGT 应得到偏移 ~200m，误差 < 3 sample
- **测试覆盖讨论**：3 新测试位于 `packages/geoviz_cross_well/tests/`，而 `pyproject.toml` `testpaths = ["tests"]` 仅扫根目录 — 全局 `pytest` 仍是 674 passed 不变；包级 `pytest packages/geoviz_cross_well/tests/` 46 passed（+3）。本次保持现状不扩 testpaths，避免一次性引入未审计的包级测试到 headline 数字
- **未完成**：`propagate_pick_via_dtw` 已存在但**尚未接入 UI** — 用户在地震/连井页面点"自动连井"按钮仍走 name-match。需要在 `src/pages/cross_well/` 层添加：name-match 未命中时回退调用 `propagate_pick_via_dtw`。该 UI 接线留给 11.6-G 或单独 follow-up
- **教训**：
  - 测试覆盖率 ≠ 生产被调用 — DTW 引擎有 7 个单元测试全绿，但被 0 个生产路径调用；测试金字塔必须有"集成层"才能 catch 这种 orphan engine
  - "把 X 接入 Y" 在产品语境下是双向工作：fix engine + wire producer，缺一不可

### Session: 2026-05-31 (Phase 11.5-C/E/F — debt closeout)

- 11.5-C: investigated — **WON'T FIX**. The 3 skipped tests live in `test_seismic_view.py` and are legitimate `pyvistaqt.QtInteractor` headless environment gates, not the well_tie tests originally documented in task_plan
- 11.5-E: `packages/geoviz_seismic/CHANGELOG.md` synced — added 0.2.0 (Phases 6/7/8), 0.3.0 (Phases 9/9b/10/11/refactor), 0.4.0 (Phase 11.5-A/B); `__version__` bumped 0.1.2 → 0.4.0
- 11.5-F: README documents `VERSION` (0.7.0) vs `CHANGELOG.md` (0.10.0) intentional desync
- Full suite: **668 passed, 3 skipped**
- Phase 11.5 closeout: 5/6 sub-tasks DONE (A/B/D/E/F), 1 reclassified WON'T FIX (C)

### Session: 2026-05-31 (Phase 11.5-B + 11.5-D — AttributePipeline)

#### Implementation Completed
- New `attribute_pipeline.py` — `AttributeSpec` dataclass + `ATTRIBUTES` tuple (14 entries) + `labels()`/`rgb_index()`/`rgb_channel_indices()`/`apply()` API
- `seismic_view.py` `_apply_attr` collapsed from ~40 lines to 5 lines (delegates to pipeline)
- All `idx == 7` and `idx >= 8` magic numbers replaced with `_ap.rgb_index()` lookups
- Adding a new attribute now = 1 line in `ATTRIBUTES` tuple
- 32 new tests in `test_attribute_pipeline.py` (registry sanity, dispatch coverage for every idx 0-13, curvature range checks)
- Full suite: 668 passed, 3 skipped

### Session: 2026-05-31 (Phase 11.5-A — Curvature GPU path)

#### Implementation Completed
- `_compute_slope(data, xp=np)` — array-module-agnostic (numpy or cupy)
- `compute_curvature(..., use_gpu=True)` — real CuPy path via `cupyx.scipy.ndimage.uniform_filter` + `cp.gradient` + `cp.asarray`/`cp.asnumpy`
- `TestCurvatureGpuConsistency` now runs real GPU vs CPU comparison (max diff ~1.5e-3 float32, tolerance 5e-3 atol / 1e-3 rtol)
- 19 curvature tests + 636 full suite green

## Errors Encountered
| Error | Resolution |
|-------|------------|
| depth_to_twt TypeError on array input | np.ndim check — float for scalar, array for array |
| BinGridGeometry il/xl swapped | il = (-dx*sin + dy*cos)/spacing (inline along azimuth from north) |
| QPainter.drawPolyline(*args) TypeError | drawPolyline(QPolygonF(list)) — PySide6 takes single QPolygonF |
| set_clip_percentile empty if body | Restored original method body lost during overlay insertion |
| Reflectivity N-1 vs depth N mismatch | Build midpoint WellTieCalibration at (depths[:-1]+depths[1:])/2 |
| Auto-tie sign convention | Positive shift = synthetic late (should move down), test updated |

---
*Update after completing each phase or encountering errors*

### Session: 2026-05-31 (Phase 11.6-G — Manual pick UX)

#### Implementation Completed
- 全工具栏添加 Chinese tooltip — 加井/清除/井道/域/拾取/自动连接/导入层位/导出
- 新增「DTW 传播」按钮：把 11.6-F 添加的 `propagate_pick_via_dtw` producer 接入 UI
  - 行为：用户在任一口井手动拾取一个层位点，点按钮 → 自动以此点为锚把层位传播到所有其他井，生成灰色 ghost
  - 三分支防御：无井 / 无 manual pick / 成功传播，全部走 QMessageBox.information 给用户清晰反馈
- 状态栏在 pick mode 下显示完整快捷键提示：「拾取模式: 左键添加 · Shift+左键连接 · 右键删除 · Ctrl+Z 撤销 · Esc 退出」
- `picks_changed` 信号 → `_update_status` 实现拾取/撤销实时刷新井位计数
- 新增 `tests/test_cross_well_page_dtw.py` — 6 个 UX 回归测试覆盖：按钮存在/tooltip/三分支 message box/pick 模式提示/picks_changed 联动
- 全套件：680 passed, 4 skipped（+6 新）

**Bug fix during implementation**: 初版用了 `HorizonPick.depths_by_well` 不存在的属性 → 改为 `pick.connected_wells()` + `pick.depth_for_well(well)`。教训：写 page 层代码前要先读 dataclass 定义。

### Session: 2026-05-31 (Phase 11.6-D — paleo map HiDPI zoom blur)

#### Root cause: LayerPixmapCache 不感知 devicePixelRatio
- `paint_scheduler.py:_rerender` 创建 `QPixmap(buf_w, buf_h)` 时从未调 `setDevicePixelRatio` — pixmap 物理像素 = 逻辑像素
- HiDPI 屏（DPR=2/2.5/3）上文本/线在 cache 内以低密度渲染，blit 时被 Qt 默认双线性拉伸 → 模糊
- chrome layers（title/north_arrow/scale_bar/legend）经 11.6-B 已 bypass cache 所以没事 — 模糊只出现在 facies polygons 边界 + region labels

#### Fix（commit pending）
- `paint()` 从 `painter.device().devicePixelRatioF()` 取 DPR
- `_rerender(vp, dpr)` 分配 `QPixmap(int(buf_w*dpr), int(buf_h*dpr))` + `setDevicePixelRatio(dpr)` — layer 仍用逻辑坐标绘制，Qt 内部按物理像素渲染
- `_needs_rerender(vp, dpr)` 新增 DPR 变化检测（窗口拖到不同 DPI 显示器触发 rerender）
- `_blit` 不动 — `drawPixmap` 已自动处理 setDevicePixelRatio 后的源/目标缩放

#### 新增回归测试（test_paint_scheduler.py）
- `test_pixmap_dpr_matches_painter_device`：pixmap.devicePixelRatio() == painter 的 DPR；物理像素 = 逻辑像素 × dpr
- `test_dpr_change_triggers_rerender`：DPR 从 1.0 变到 2.0 → 强制 rerender

#### 测试结果
| Date | Suite | Result |
|------|-------|--------|
| 2026-05-31 (Phase 11.6-D) | 682 passed, 4 skipped | ✅ |

**11.6 整体状态**：7/8 done（A/B/C/D/F/G/H），剩 E（自动连井慢）

### Session: 2026-05-31 (Phase 11.6-E — DTW perf + 进度条)

#### Profile baseline
| n samples | full band (老默认) | 修后默认（band=n/4）|
|-----------|--------------------|--------------------|
| 500 | 0.44s | 0.075s |
| 1000 | 1.97s | 0.28s |
| 2000 | 7.09s | 1.06s |

5 井 × 4 次传播：修前 ≈ 40s，修后 ≈ 1.1s（acceptance 门槛 5s）

#### Root cause
- `dtw_engine.correlate()` 内层纯 Python 双循环 + 每格 `prev=[]; if i>0: prev.append(...); min(prev)` → CPython 解释开销在 1M 格上 ~2s
- `band_radius=None` 默认 `max(n,m)` → 强制全 O(n²)，无理由的全带宽

#### Fix
- **`dtw_engine.py`**：按行向量化（vertical+diag 用 `np.minimum` 一次性，horizontal 串行扫但去 list/tuple-min），默认 `band_radius = max(20, max(n,m)//4)`（25% 限带），新增 `progress_callback(current, total)` 参数
- **`canvas.py`**：`propagate_pick_via_dtw(...progress_callback=...)` 井级别回调
- **`src/pages/cross_well/page.py`**：`_on_dtw_propagate` 用 `FloatingProgressOverlay` 显示「DTW 传播中... (3/12)」，每步 `QApplication.processEvents()` 保持 UI 响应

#### 新增回归测试（test_dtw_engine.py，+3 个）
- `test_dtw_perf_under_one_second_for_1k_samples`：n=1000 必须 < 1s
- `test_progress_callback_receives_monotonic_updates`：(cur,total) 单调递增 + 最终 == n
- `test_vectorized_dtw_matches_reference_implementation`：与朴素双循环参考实现 suggested_depth 一致

#### 测试结果
| Date | Suite | Result |
|------|-------|--------|
| 2026-05-31 (Phase 11.6-E) | 682 passed, 4 skipped（+3 新 DTW，总收集 686）| ✅ |

**11.6 闭环**：8/8 全修，Phase 11.6 收官

---

## Session: 2026-05-31 Phase 11.7-A — 古地理图数据层错位修复

### Phase 11.7-A: LayerPixmapCache viewport 尺寸失效

#### 起因
用户 driving prompt："自行截图分析吧，古地理图标注和对象完全偏离了。"

自检截图（headless QT_QPA_PLATFORM=offscreen + canvas.grab()）发现：title / north arrow / scale bar / legend 横跨画布分布正常，但 facies polygons / wells / region labels 全部被压缩在左上角。视觉上是"标注居中、数据偏离"。

#### Root cause
`LayerPixmapCache._needs_rerender` 不检测 viewport 宽高变化。canvas 构造时默认 widget 大小 640×480，首次 paint 让 cache 按 buf=(1280, 960) 渲染并固化。`resize(1400, 900)` 后 viewport 变 1400×900，但 cache 视参数无变化（zoom/scale 没动）→ 走 `_blit` 路径。`_blit` 从老 pixmap 读取 (vp.width, vp.height) = (1400, 900) 矩形，但 pixmap 逻辑尺寸只有 (1280, 960)，超出部分透明 → 数据被压在左上角小块区域。

Chrome layers 因 11.6-B `is_chrome=True` 已 bypass cache 直绘 → 每帧用真实 viewport 渲染 → 正常分布。这造成"数据错位、标注正常"的诡异视觉。

#### Fix
`packages/geoviz_paleo_map/geoviz_paleo_map/paint_scheduler.py`：
- `__init__` 增 `self._vp_width: int = 0` / `self._vp_height: int = 0`
- `_needs_rerender` 增 `if vp.width > self._vp_width or vp.height > self._vp_height: return True`
- `_rerender` 末尾存 `self._vp_width = vp.width` / `self._vp_height = vp.height`

#### 新增回归测试
`tests/test_paint_scheduler.py::TestLayerPixmapCache::test_viewport_grow_triggers_rerender` — paint vp_small (400×300) 后再 paint vp_large (1200×800)，断言 render_count == 2。stash-test-pop 验证：剥离修复 → 测试 fail (`assert 1 == 2`)，恢复 → pass。

#### 视觉验证
重生成 `/tmp/paleo_shot.png`：facies polygons / wells (Well B, Well C) / region labels / title (古地理图 - 测试) / north arrow / scale bar / legend 全部正确分布于 1400×900 画布上，无左上角压缩。

#### 测试结果
| Date | Suite | Result |
|------|-------|--------|
| 2026-05-31 (Phase 11.7-A) | 14/14 test_paint_scheduler 通过；全套 681 passed, 4 skipped, 2 visual-parity 失败（pre-existing DPR 环境问题，与本修复无关，已 stash-test-pop 验证）| ✅ |

#### 教训
- 复合缓存层必须把所有影响 buffer 几何的输入都纳入失效判定。原 cache 查了 dirty/dpr/scale/pan，漏了 width/height——因为窗口 resize 不改 zoom，假设"只有 dirty/zoom 会动"是错的
- chrome bypass 既是优点也是 trap：它让 chrome 不受 cache bug 影响 → 视觉错位只表现在数据层 → 第一直觉是"投影算错了"而非"缓存没失效"。下次类似 bug，先查 cache invalidation 再查 transform
- 测试要锁住 invariant（"任何影响 buffer 几何的维度变化都必须 invalidate"）而非"已知 case"。补 `test_viewport_grow_triggers_rerender` 把这条 invariant 显性化

**11.7 状态**：A 完成，无其余子任务计划

---

### Session 2026-05-31 (Phase 11.7-B) — 古地理图缩放/平移时标签与多边形分离

#### 任务
用户报"古地理图标注和显示分离"，澄清后定位为：**缩放/平移过程中 RegionLabelsLayer 文字与 FaciesPolygonsLayer 几何对象错位**——多边形停在旧位置，label 漂到新位置。chrome（指南针/比例尺/图例）正常。

#### 根因
`packages/geoviz_paleo_map/geoviz_paleo_map/screen_path_cache.py` 的 `ScreenPathCache.get_or_build` 缓存键仅含 `(zoom_key, feature_id)`，但 `_transform_path` 把 `vp.center_world` 烤进 screen path。平移（center 改变、zoom 不变）时 cache_key 命中旧 entry → FaciesPolygonsLayer 拿到用旧 center 烤好的 path 画在旧屏幕坐标；而 RegionLabelsLayer 每帧实时 world_to_screen → 标签漂到新位置。

11.7-A 修了 LayerPixmapCache 的 viewport 增长失效，但 ScreenPathCache 的 center 失效是独立路径：两层 cache 的失效粒度不一致 → 一层"不 rerender"但另一层早 stale → layer 拿到 stale screen path 再画进新 buffer。

#### Fix
`packages/geoviz_paleo_map/geoviz_paleo_map/screen_path_cache.py`：
- `__init__` 增 `self._zoom_center: dict[float, tuple[float, float]] = {}`
- `get_or_build` 进入时先查 `_zoom_center.get(zoom_key)`，若与当前 `viewport.center_world` 不一致 → 清掉该 zoom 的所有 entry
- 构建完毕后 `self._zoom_center[zoom_key] = center`
- `_evict` 同步收缩 `_zoom_center` 防止内存泄漏

#### 新增回归测试
`tests/test_paint_scheduler.py::TestScreenPathCache::test_pan_invalidates_screen_path` — 同 zoom 下 vp1(center_lng=5)→vp2(center_lng=8)，断言两次 get_or_build 返回 path 的 boundingRect.center().x() 不同。修复前 FAIL（两边都是 200.0），修复后 PASS。

#### 测试结果
| Date | Suite | Result |
|------|-------|--------|
| 2026-05-31 (Phase 11.7-B) | 15/15 test_paint_scheduler 通过；全套 684 passed, 4 skipped | ✅ |

#### 教训
- **多层 cache 的失效条件必须对齐**：LayerPixmapCache（50% margin pan tolerance）与 ScreenPathCache（按 zoom）失效粒度不一致 → 上层 layer 拿到 stale path 再画进新 buffer。Cache 链应保证"上游命中 ⊆ 下游命中"
- **transform 中烤进的参数都属于 cache key 的一部分**：`_transform_path` 烤了 scale + center + viewport_size，但 cache key 只反映 scale → 任何烤进 transform 的参数变化都必须能让 key miss。这是一条可查的 code-review invariant
- **"X 与 Y 错位"通常意味着 X / Y 走了不同更新通道**：label live transform vs polygon cached transform — 先列两边数据流再查缓存

**11.7 状态**：A + B 完成，无其余子任务计划

---

### Session 2026-05-31 (Phase 11.7-C) — 对比模式下两边各画一套 chrome

#### 任务
用户报"不要区分区域，古地理图的图例指南针和比例尺都在一个画布上"。澄清后定位为：对比模式（点"对比"按钮并排显示两个时期）下，左右两个 PaleoMapCanvas 各画自己一套 Title / NorthArrow / ScaleBar / Legend → 屏幕上有两套 chrome 各只反映自己一侧的 facies，无法统一阅读。

#### 决策（AskUserQuestion 锁定）
- Bug 确认：对比模式下两边各有一套 chrome
- 修复方案：独立共享面板（中间分割）
- 图例内容：合并 A+B 的 facies

#### 根因
chrome 是 canvas 内嵌 layer，由 `PaleoMapCanvas` 在 4 个 `_layers` 构建点固定追加。canvas 不知道自己"是否独立呈现"——把两个 canvas 并排，chrome 就被双份渲染。Compare 模式只在 page 层把两个 canvas 塞进 QSplitter，无法 retroactively 抽出 chrome。

#### Fix
1. **`packages/geoviz_paleo_map/geoviz_paleo_map/canvas.py`**：
   - `__init__` 增 `show_chrome: bool = True` 参数
   - 在 4 个 `_layers.extend([...])` 调用点统一 `if self._show_chrome:` 包裹 chrome 4 件套
   - 增 `facies_names() -> set[str]` 返回 LegendLayer 已收集的 facies
   - 增类信号 `facies_changed = Signal()`，在 `load_features` / `load_hierarchy` 末尾 emit
2. **新建 `packages/geoviz_paleo_map/geoviz_paleo_map/shared_chrome_panel.py`**：
   - 固定宽 200px QWidget，自上而下：north arrow / 合并 legend (A∪B facies) / scale bar
   - 连接 canvas_a + canvas_b 的 `facies_changed` + `zoom_changed` → `self.update()`
   - scale bar 用 canvas_a._viewport.world_bbox() 计算 km
3. **`src/pages/paleo_map/page.py::_start_compare`**：
   - 弃用 QSplitter，改用 QHBoxLayout host
   - `[canvas_a (stretch=1)] [SharedChromePanel 200px] [canvas_b (stretch=1)]`
   - 两 canvas 都构造 `show_chrome=False`
   - `_stop_compare` 拆除 host + 共享面板 + 第二 canvas，重建带默认 chrome 的单 canvas

#### 新增回归测试
`tests/test_paleo_shared_chrome.py` 6 项：
- `test_default_includes_chrome_layers` — 默认 chrome 4 件套都在
- `test_show_chrome_false_omits_chrome` — `show_chrome=False` chrome 全去掉
- `test_facies_names_exposed` — `facies_names()` 返回当前 facies 集合
- `test_merges_facies_from_both_canvases` — SharedChromePanel 合并 A∪B
- `test_refreshes_when_canvas_reloads` — canvas reload 后 panel.merged_facies() 跟随
- `test_panel_paints_without_error` — `panel.grab()` 不抛异常

#### 测试结果
| Date | Suite | Result |
|------|-------|--------|
| 2026-05-31 (Phase 11.7-C) | 6/6 test_paleo_shared_chrome 通过；全套 690 passed, 4 skipped | ✅ |

#### 教训
- **chrome 归 composition root，不归 leaf widget**：canvas 应该是"可被多次实例化的内容画板"，副标题/图例/指北针/比例尺属于宿主页面。一旦可能并排两个实例，chrome 必属容器
- **多实例场景前先问"哪些 layer 是 per-instance、哪些是 per-composition"**：在加 11.7-C 之前这条 invariant 隐藏在"只有一个 canvas"的假设里。任何加 compare / split-screen / PiP 功能时，必须先把 layer 按"内容 vs chrome"分一次
- **leaf 暴露 signal + 状态查询接口比让 root 直接读私有字段更安全**：`facies_changed` + `facies_names()` 让 SharedChromePanel 不耦合 LegendLayer 内部；后续换 chrome 实现也不破壳

**11.7 状态**：A + B + C 完成，全部 ship

---

### Session 2026-05-31 (Phase 11.7-C2) — chrome overlay 视觉返工

#### 用户反馈
"不要把指南针，图例和显示地理图的区域区分开。" → AskUserQuestion 锁定：**对比模式：chrome 应该叠在画布上，不要占独立区域**。

#### 根因
11.7-C 把 `SharedChromePanel` 作为 `canvas_A | panel | canvas_B` 三件套塞进 QHBoxLayout → panel 占独立 200px 列，两个 canvas 被一条灰白竖条切开。QHBoxLayout 是 layout-managed sibling，panel 必然占自己几何区 → 物理上不可能"叠"在 canvas 上。

#### 修复
1. `SharedChromePanel.__init__` 新增 `overlay: bool = False`：overlay=True 时设 `WA_TranslucentBackground + WA_TransparentForMouseEvents`
2. `_start_compare` 不再把 panel 加 QHBoxLayout，直接 `parent=self.map_view` 挂到左 canvas；QHBoxLayout 只放两个 canvas 各占 50%
3. 新增 `_install_chrome_overlay_positioning()` 包装 `canvas.resizeEvent`，每次 resize 把 panel 移到 canvas 右上角（width-panel_w-8, 8）并 `raise_()`
4. 新增测试 `test_overlay_mode_is_translucent_child` 锁定 overlay parent + 透明属性

#### 测试结果
| Date | Suite | Result |
|------|-------|--------|
| 2026-05-31 (Phase 11.7-C2) | 7/7 test_paleo_shared_chrome 通过；全套 691 passed, 4 skipped | ✅ |

#### 教训
- **"X 不要占独立区域"≠"X 不存在"**：用户要的是视觉融合，不是删除。先确认"位置/层叠"再考虑"存在性"
- **Qt overlay = parent 关系 + 手动 move/raise_，不靠 layout**：layout-managed 必然占区；overlay 必须脱离 layout
- **overlay 必须配 `WA_TransparentForMouseEvents`**：否则虽然背景透明，但 panel 矩形仍然吃事件 → canvas 拖动/缩放在 panel 覆盖区域里会失效

**11.7 状态**：A + B + C + C2 完成，全部 ship

---

### Session 2026-05-31 (Phase 11.7-D) — 删除 compare 模式，回归单画布

#### 用户反馈
"删除对比这个功能。古地理图这里就一个画布，所有信息都在画布上（图例，指南针，比例尺等等）。"

#### 根因
compare 模式不是用户提出的需求，是 Phase 11.6 时自作主张加的功能。11.7-C 解决"双份 chrome"、11.7-C2 解决"chrome 占独立列"——这两个问题本身只在 compare 模式下存在。用户两次反馈视觉问题后直接要求删除整个功能。

#### 修复
1. `PaleoMapCanvas` 移除 `show_chrome` 参数 / `facies_changed` 信号 / `facies_names()` 方法；4 处 `_layers` 构造点无条件追加 chrome 八件套
2. `git rm packages/geoviz_paleo_map/geoviz_paleo_map/shared_chrome_panel.py`
3. `src/pages/paleo_map/page.py`：移除 SharedChromePanel 导入、`_compare_mode` 字段、`_compare_btn` 按钮（含 toolbar add）、`_on_period_changed` 的 compare 分支、`_toggle_compare/_start_compare/_install_chrome_overlay_positioning/_stop_compare` 四个方法
4. `git rm tests/test_paleo_shared_chrome.py`（7 测试随 SharedChromePanel 退役）

#### 验证
- `grep -rn "shared_chrome\|SharedChromePanel\|show_chrome\|facies_changed\|_compare\|map_view_b" src/ tests/ packages/`：无输出
- 全套：684 passed, 4 skipped（691 → 684 = -7 共享 chrome 测试）

#### 测试结果
| Date | Suite | Result |
|------|-------|--------|
| 2026-05-31 (Phase 11.7-D) | 全套 684 passed, 4 skipped | ✅ |

#### 教训
- **用户没要的功能就是债**：11.7-C/C2 两轮工程的工作量是负面 ROI——它们解决的问题在 compare 删除后自动消失
- **"用户反馈视觉问题"不一定是"调整视觉"，可能是"删除整个功能"**：用户两次反馈调整方向，第二次反馈应该是更早的删除信号
- **scope 添加要先经用户确认**：compare 模式在 Phase 11.6 加入时没问用户；如果先问，根本不会有 11.7-C 系列
- **回滚要彻底**：不仅删 SharedChromePanel，连 canvas 上为它而生的 `show_chrome/facies_changed/facies_names` 都要拔——这些 API 只有 compare 模式用，留着就是死代码

**11.7 状态**：A + B + D + E + F 完成；C/C2 已回滚

---

### Session 2026-05-31 (Phase 11.7-F) — 图例/比例尺/指北针/标题内嵌贴图与安全边界收缩

#### 用户反馈
"面板不要区分为三部分，把图例/比例尺/指南针，定制在地图画布上即可，不需要分成这部分。"

#### 根因
虽然 Phase 11.7-E 实现了视口自动缩放以填满画布，但图例、比例尺和指北针默认是锚定在**整个 Widget 的边缘**绘制的（例如 Legend 位于 `widget.width - 140 - 12` 处）。当地图的实际地质研究区域（即 facies polygons 块）因其自身边界形成一个有黑框的内部矩形时，这些 Chrome 元素仍然漂浮在黑框之外的空白缓冲灰底上，在视觉上依然割裂为“地图在中间，Chrome 元素悬空在两侧”的三个断层板块。

#### 修复
1. **画面元素物理内嵌（Inside Map Frame Customization）**：
   - 将 `fit_viewport_to_data` 生成的数据绝对地理边界框 `data_bounds` (`min_lng, max_lng, min_lat, max_lat`) 注入到 `PaleoMapViewport` 模型中，在画板每一次 `paintEvent` 触发时计算其在当前缩放比下的实时屏幕物理坐标矩形 `data_rect_px`。
   - 重构 `LegendLayer`、`NorthArrowLayer`、`ScaleBarLayer` 和 `TitleLayer` 的坐标计算方式：
     - **图例 (Legend)**：锚定在 `data_rect_px` 的右下角（`br.x() - box_w - 12, br.y() - box_h - 12`）。
     - **指北针 (Compass)**：锚定在 `data_rect_px` 的右上角（`br.x() - 46, tl.y() + 16`）。
     - **比例尺 (Scale Bar)**：锚定在 `data_rect_px` 的左下角（`tl.x() + 16, br.y() - 24`）。
     - **标题栏 (Title Box)**：动态水平居中在 `data_rect_px` 顶部（`(tl.x() + br.x()) / 2`）。
2. **平滑边缘回弹锚定（Viewport Boundary Clamping）**：
   - 为防止用户放大地图（Zoom In）至局部细节时边界矩形移出屏幕，在每一处 Chrome 坐标计算中都加入了智能边缘回弹（Clamping）逻辑。
   - 当地图边界位于屏幕内时，元素完美内嵌贴合于黑框内部角落；当地图被放大超出屏幕时，元素平滑滑动并自动停留在屏幕边缘（Viewport boundaries），确保其永远可见，实现自然且精密的 GIS 专业制图体验。

#### 验证
- `uv run pytest tests/test_export_professional.py tests/test_paint_scheduler.py`：全部通过
- 全套测试：684 passed, 4 skipped ✅

#### 测试结果
| Date | Suite | Result |
|------|-------|--------|
| 2026-05-31 (Phase 11.7-F) | 全套 684 passed, 4 skipped | ✅ |

---

### Session 2026-05-31 (Phase 11.7-E) — 古地理图整画布整合与自适应视口

#### 用户反馈
"古地理图这部分 不要如图这样分块，就一整个画布，图例和比例尺，还有指南针也要在上面。"

#### 根因
1. **视口未自适应**：在加载数据或切换地质时期时，视口默认居中在 (115E, 30N) 且 zoom=2.0，而加载的数据（如 J3）可能分布在不同区域，导致数据偏心并显得极小（在画布中只占一小块矩形，周围是大量空白），这使用户感觉画面是“分块”的，图例、比例尺与指北针也因此悬空在白色背景中，无法有机融为一体。
2. **导出逻辑割裂**：`export_professional_figure` 的专业排版默认将页面强制划分为主图区、副图区、侧边图例面板、顶部标题栏等多个独立板块（Grid Frame, Legend Panel等），在导出的 SVG/PDF/PNG 中呈现了明显的物理分块，而没有采用像 UI 中那样图例/比例尺/指北针直接层叠（overlay）在主画布上的统一体验。

#### 修复
1. **主视口自适应缩放（Live UI Auto-Fit）**：
   - 在 `PaleoMapCanvas` 中新增 `fit_viewport_to_data()` 方法，遍历加载的 Features（无论是 GeoJSON features 还是 hierarchy 模型里的 elements）提取所有经纬度边界框 `min_lng/max_lng/min_lat/max_lat`。
   - 自动将视口中心移至数据中心，并基于当前 widget 的真实宽高计算最佳 `zoom`，使地图数据能以 85% 比例充满整个画布。
   - 在 `load_features` 和 `load_hierarchy` 尾部自动触发该方法；并在 `resizeEvent` 中，如果尚未完成首次布局（如窗口初始化时 widget 尺寸为 640x480 的过渡期），当 widget 大小变为有效尺寸后自动进行首次完美贴合，完美杜绝了空白分块现象。
2. **导出大画布对齐（Export Unity）**：
   - 彻底简化 `export_professional_figure` 逻辑，将整个导出页面（包含 15mm 安全边距）设为**一整个完整的地图画布**（`map_rect` 占满除 margin 外的全部空间），不再划分右侧图例面板列或额外顶部标题栏。
   - 直接使用 `canvas` 现有的、已支持透明层叠渲染的 `LegendLayer`、`ScaleBarLayer` 、`NorthArrowLayer` 与 `TitleLayer`，使其按图纸比例在单一大画布上层叠绘制图例、比例尺、指北针与标题（完全 1:1 对齐 live UI 观感，并支持 `include_legend` 等开关）。

#### 验证
- `uv run pytest tests/test_export_professional.py tests/test_paint_scheduler.py`：通过
- 全套测试：684 passed, 4 skipped ✅

#### 测试结果
| Date | Suite | Result |
|------|-------|--------|
| 2026-05-31 (Phase 11.7-E) | 全套 684 passed, 4 skipped | ✅ |

