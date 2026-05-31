# Progress Log — GeoViz Engine

## Project Status: Phase 1–11 COMPLETE, Refactor COMPLETE

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
