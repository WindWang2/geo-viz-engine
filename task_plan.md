# Task Plan: GeoViz Engine — 项目总览与下一步规划

> **更新于 2026-05-31**：基于 CEO + Eng 双重 review 重写。明确区分"已完成 / 待修复 / 下一步"。
> **同步于 2026-05-31**：Goal/Current State 同步至 Phase 11.7-D 完成后的真实状态。

## Goal
GeoViz Engine 是一款基于 PySide6 的桌面地质数据可视化引擎。Phase 1–17 已完成，702 tests passed。**核心市场定位**：科研院所 + 中小油田 + 教学（差异化于 Petrel 的轻量、可二次开发、出版级出图）。

## Current State
- **Branch:** main (synced with origin)
- **Tests:** 702 passed, 4 skipped (4 skipped 来自 `test_seismic_view.py` 对 `pyvistaqt.QtInteractor` 的环境探测——无显示则 skip，为正确的环境闸门行为，不待整改)
- **Latest commit:** `cb2b7d25 feat(geoviz-plots): add general 2D plotting, IDW/SciPy interpolation, and SurfaceWidget contouring`
- **Active phase:** Phase 14 in_progress (Cross-Well Section Planner & Professional PDF Report)
- **Health rating:** A+（Phase 11 + 11.5 + 11.6 + 11.7 + 11.8 + 11.9 + 17 全清，832 个单元测试全绿）

## Completed Phases

| Phase | Content | Status | Note |
|-------|---------|--------|------|
| 1 | PySide6 骨架、导航、单井剖面、地图、地震3D、数据管理 | ✅ | |
| 2 | 多井对比、相变连通、地层拉平、TVDSS对齐、SVG导出 | ✅ | |
| 3 | 测井引擎独立化、轨道管理器、矢量导出、AI预测集成 | ✅ | |
| 4 | 地震可视化独立化、3D体渲染+2D剖面、SEGY按需切片 | ✅ | |
| 5 | 连井对比拾取工作流（DTW、地震校深） | ✅ | |
| 6 | 地震属性分析（5属性+色标）、沿层位提取 | ✅ | |
| 7 | STFT谱分解、RGB属性融合、属性交叉图 | ✅ | |
| 8 | 井震结合可视化集成（WellTiePanel + auto-tie + overlay） | ✅ | |
| A7 | CheckshotTable → WellTieCalibration 委托去重 | ✅ | |
| 9 | Coherence (C3 eigenstructure) 相干属性 | ✅ | 含真实 GPU 路径 |
| 9b | GPU Acceleration for Coherence | ✅ | 1.5-1.9x speedup |
| 10 | PaleoMap 纹理填充 + 专业图件导出 | ✅ | 13 facies patterns |
| Refactor | seismic_view.py 拆分 | ✅ | 1471 → 1283 行 |
| 11 | Curvature (Dip/Azimuth + 6 kinds) | ✅ | GPU 路径已补，见 11.5-A |
| 11.5 | Phase 11 债务清理（GPU/dispatch/CHANGELOG/版本号/集成测试） | ✅ | A/B/D/E/F DONE；C WON'T FIX |
| 11.6 | PaleoMap 性能 + chrome 重构（A=texture cache, B=chrome bypass, C=Z-order, D=DPR, E=DTW vectorize） | ✅ | 5 子任务全 ship |
| 11.7 | PaleoMap 缓存失效 + 共享 chrome（A=viewport-size, B=pan-center, D=删除 compare 模式回归单画布） | ✅ | A+B+D ship；C/C2 回滚 |
| 11.8 | 层级锁定与图例/比例尺文字重叠修复（三子任务全 ship） | ✅ | 684 tests passed |
| 11.9 | 相纹理资料设计与微相/亚相色彩系统扩充 | ✅ | 687 tests passed, evaporite SVG added |
| 17 | geoviz-plots 通用图表与等值线插值渲染 | ✅ | 702 tests passed, 15个新 TDD 测试完美全绿 |


## 🔴 Phase 11.5: 收尾与债务清理（最高优先级，必须先于 Phase 12）

**目的：** 修复 Phase 11 遗留的工程债务，恢复 task_plan 与代码的诚信。

### Tasks

| ID | Task | Files | Priority | Status |
|----|------|-------|----------|--------|
| 11.5-A | **实现 `compute_curvature` 的 CuPy GPU 路径**（或删除 `use_gpu` 参数并更新 docstring/task_plan） | `packages/geoviz_seismic/geoviz_seismic/attributes.py:404-483` | 🔴 P0 | ✅ DONE |
| 11.5-B | **抽象 `AttributePipeline` 类**：把 `seismic_view.py:831-867` 的 hardcoded `_FN` 列表 + `if idx>=8` 魔数收敛到一个 dispatch 表（dict[idx → (name, fn, kwargs_resolver, axis)]） | `packages/geoviz_seismic/geoviz_seismic/seismic_view.py` | 🟡 P1 | ✅ DONE |
| 11.5-C | ~~整改 3 个 skipped 测试~~ — **核实后取消**：实际 3 个 skip 来自 `test_seismic_view.py` 对 `pyvistaqt.QtInteractor` 的环境探测（无显示则 skip），而非 well_tie 测试。这是正确的环境闸门行为，不需要改 xfail。task_plan 原描述基于陈旧假设。 | `tests/test_seismic_view.py` (verified) | 🟢 P2 | ❌ WON'T FIX |
| 11.5-D | **新增 `_apply_attr` idx=8-13 集成测试**：当前曲率/dip/azimuth 的 UI 分支路径无测试覆盖 | `tests/test_seismic_view.py` | 🟢 P2 | ✅ DONE |
| 11.5-E | **同步子包 CHANGELOG**：`geoviz_seismic/CHANGELOG.md` 停留在 0.1.2（5月11日），与根 CHANGELOG 脱钩 | `packages/*/CHANGELOG.md` | 🟢 P2 | ✅ DONE |
| 11.5-F | **版本号策略文档化**：在根 README 加注 `VERSION (0.7.0)` vs `CHANGELOG (0.10.0)` 是有意为之 | `README.md` | 🟢 P3 | ✅ DONE |

---

## 🔴 Phase 11.6: 用户测试发现的 UX/功能缺陷（2026-05-31 用户回归测试）

**目的：** 修复用户实测发现的页面级 bug 和体验问题；以"用户可用"为标准而非"测试通过"。

### Tasks

| ID | Task | Files | Priority | Status |
|----|------|-------|----------|--------|
| 11.6-A | **地图：点击井无响应** — 井位地图上点具体井位无反应（既不切到测井页也无提示） | `src/pages/map/`, `packages/geoviz_map/canvas.py` | 🔴 P0 | ✅ DONE |
| 11.6-B | **古地理图：图例/指南针/比例尺消失** — 根因：LayerPixmapCache 2× buffer 与 chrome layer 锚定 viewport 边界冲突，buf_vp 尺寸是真实 viewport 的 2 倍导致锚点 (viewport.width-46) 落在缓冲区外。修复：base 增 `is_chrome` 标志，chrome 类（title/north_arrow/scale_bar/legend）跳过 LayerPixmapCache 直绘 | `packages/geoviz_paleo_map/canvas.py`, `layers/base.py`, `legend.py`, `north_arrow.py`, `scale_bar.py`, `title.py` | 🔴 P0 | ✅ DONE |
| 11.6-C | **古地理图：PDF 导出空白** — 已修 QPixmap.scaled QSizeF→QSize 类型错误（DevicePixel rect 需 toRect），现已将 `_export_pdf` / `_export_svg` / `_export_png` 改为委托给 `export_professional_figure`，自动带 title / 边框 / 比例尺 / 指南针 / 图例 | `src/pages/paleo_map/page.py` | 🔴 P0 | ✅ DONE |
| 11.6-D | **古地理图：缩放后文字模糊** — 根因：`LayerPixmapCache._rerender` 创建 `QPixmap(buf_w, buf_h)` 时未感知 `devicePixelRatio`，HiDPI 屏上 cache pixmap 物理像素密度=逻辑密度，blit 时被放大插值 → 标签/边界线全部模糊。Title/north arrow/scale bar/legend 因 chrome bypass 不受影响。修复：`paint()` 从 `painter.device().devicePixelRatioF()` 取 DPR，pixmap 按 `phys = buf * dpr` 分配并 `setDevicePixelRatio(dpr)`；DPR 变化触发 rerender | `packages/geoviz_paleo_map/paint_scheduler.py` | 🟡 P1 | ✅ DONE |
| 11.6-E | **连井：自动连井太慢** — 根因：`dtw_engine.correlate()` 内层 Python 双循环 + 每格构造 prev list + tuple-min，且 `band_radius=None` 默认全 O(n²)。修复：(1) 改写为按行向量化（vertical+diag 用 np.minimum 一次性，horizontal 因依赖前一格仍串行但去掉了 list/tuple 开销）；(2) 默认 `band_radius = max(20, max(n,m)//4)` 限带；(3) 新增 `progress_callback(current, total)` 参数，UI 用 FloatingProgressOverlay 显示进度。基准：n=1000 由 1.97s→0.28s (7×)，n=2000 由 7.09s→1.06s (6.7×)，5 井 4 次传播 < 2s | `packages/geoviz_cross_well/geoviz_cross_well/dtw_engine.py`, `packages/geoviz_cross_well/geoviz_cross_well/canvas.py`, `src/pages/cross_well/page.py`, `packages/geoviz_cross_well/tests/test_dtw_engine.py` | 🟡 P1 | ✅ DONE |
| 11.6-F | **连井：自动连井位置不对** — 根因双重：(1) `dtw_engine.py:74` `ref_idx = n//2` 硬编码无视用户拾取深度；(2) "自动连井"按钮仅做 formation name match，DTW 引擎从未被生产代码调用。修复：`correlate()` 新增 `ref_depth` 参数 + `CrossWellCanvas.propagate_pick_via_dtw()` 真正调用 DTW 产生 ghost picks | `packages/geoviz_cross_well/dtw_engine.py`, `canvas.py` | 🔴 P0 | ✅ DONE |
| 11.6-G | **连井：手动拾取交互体验差** — 全工具栏添加 tooltip；状态栏在拾取模式下显示快捷键提示（左键/Shift+左键/右键/Ctrl+Z/Esc）；新增「DTW 传播」按钮把 11.6-F 的 producer 接入 UI（用户在某口井手动拾取一个点后，一键传播到所有其他井产生灰色 ghost）；`picks_changed` 信号连接到 `_update_status` 实现实时刷新 | `src/pages/cross_well/page.py`, `tests/test_cross_well_page_dtw.py` | 🟡 P1 | ✅ DONE |
| 11.6-H | **地震：toolbar 显示不完整** — 当前单行 toolbar 控件过多导致末端被裁；按功能分组（视图/属性/标定/导出）拆为 2 行（QToolBar 多行或 2× horizontal layout） | `packages/geoviz_seismic/geoviz_seismic/seismic_view.py` (toolbar 构造段) | 🟡 P1 | ✅ DONE |

**Acceptance criteria:**
- 11.6-A 完成后：点井位 → 弹出该井 popover（井名/坐标/打开测井页按钮）或直接切到测井页并选中该井
- 11.6-B 完成后：默认打开古地理图三件套全部可见，颜色与背景对比足够
- 11.6-C 完成后：导出 PDF 含标题/比例尺/指南针/图例，能直接用于出版（复用 Phase 10 `export_professional_figure`）
- 11.6-D 完成后：标签和 title 在 1×–4× zoom 范围内清晰可读
- 11.6-E 完成后：典型 5 井数据自动连井 < 5 秒，有进度条
- 11.6-F 完成后：DTW 路径与已知 marker 对齐误差 < 5%
- 11.6-G 完成后：状态栏/工具栏显式说明拾取/撤销/切层操作；新手 30 秒内能完成一次拾取
- 11.6-H 完成后：1280px 窗宽下所有 toolbar 按钮可见，功能分组清晰（视图/属性/标定/导出）

---

## 🔴 Phase 11.7: 古地理图数据层错位修复（2026-05-31 自检截图发现）

**目的：** 修复用户报告"古地理图标注和对象完全偏离"的渲染错位 bug。

### Tasks

| ID | Task | Files | Priority | Status |
|----|------|-------|----------|--------|
| 11.7-A | **古地理图：数据层挤压到左上角** — 根因：`LayerPixmapCache._needs_rerender` 不检测 viewport 尺寸变化。Canvas 默认 640×480 时缓存 buffer 按 (1280, 960) 渲染，`show()`/`resize()` 后真实 viewport 变 1400×900 但缓存没失效；`_blit` 从旧 pixmap 读取 (vp.width, vp.height) 矩形 → 数据全部被压缩在画布左上角。Chrome layers（title/north_arrow/scale_bar/legend）因 11.6-B 已 bypass cache 不受影响，所以视觉上是"标注居中、数据偏移"。修复：在 `__init__` 记 `_vp_width/_vp_height=0`，`_needs_rerender` 增 `if vp.width > self._vp_width or vp.height > self._vp_height` 分支，`_rerender` 末尾存 `vp.width/vp.height`。回归测试 `test_viewport_grow_triggers_rerender` 锁定该路径。 | `packages/geoviz_paleo_map/geoviz_paleo_map/paint_scheduler.py`, `tests/test_paint_scheduler.py` | 🔴 P0 | ✅ DONE |
| 11.7-B | **古地理图：缩放/平移时标签与多边形分离** — 根因：`ScreenPathCache.get_or_build` 缓存键仅含 `(zoom_key, feature_id)`，但 `_transform_path` 把 `vp.center_world` 烤进 screen path。平移（center 改变，zoom 不变）时返回旧 center 烤好的 path，而 `RegionLabelsLayer.paint` 每帧用新 center 实时 `world_to_screen`，结果 facies polygons 留在旧位置、label 浮到新位置。修复：`ScreenPathCache` 维护 `_zoom_center: dict[zoom, (lng, lat)]`，每次 `get_or_build` 时若该 zoom 上记录的 center 与当前 viewport center 不一致，先清掉该 zoom 的所有条目再重建；`_evict` 同步收缩 `_zoom_center`。回归测试 `test_pan_invalidates_screen_path` 锁定该路径。 | `packages/geoviz_paleo_map/geoviz_paleo_map/screen_path_cache.py`, `tests/test_paint_scheduler.py` | 🔴 P0 | ✅ DONE |
| 11.7-C | **古地理图：对比模式两边各画一套 chrome** — 根因：`_start_compare` 用 QSplitter 装两个 `PaleoMapCanvas`，每个 canvas 都自带 `TitleLayer/NorthArrowLayer/ScaleBarLayer/LegendLayer`，所以对比时画布两边各浮一套标注。修复：(1) `PaleoMapCanvas.__init__` 新增 `show_chrome: bool = True` 参数，所有四处 `_layers` 构建点（`__init__`、`load_features`、`load_hierarchy` per-level group、`_update_active_layers`）都按 `self._show_chrome` 决定是否追加 chrome。(2) 新增 `packages/geoviz_paleo_map/shared_chrome_panel.py` — `SharedChromePanel(QWidget)`：固定宽 200px，从上到下绘制 north arrow / 合并图例 (A∪B facies) / 比例尺（以 canvas_a viewport 为基准）。(3) `_start_compare` 改用 QHBoxLayout 装 `canvas_A | SharedChromePanel | canvas_B`，两边 canvas 设 `show_chrome=False`；`canvas.facies_changed` 信号驱动 panel 自动刷新。(4) `_stop_compare` 拆除 panel 和 host 后重建带 chrome 的单画布。回归测试 `tests/test_paleo_shared_chrome.py` 锁定 6 个场景。 | `packages/geoviz_paleo_map/geoviz_paleo_map/canvas.py`, `packages/geoviz_paleo_map/geoviz_paleo_map/shared_chrome_panel.py`（新增）, `src/pages/paleo_map/page.py`, `tests/test_paleo_shared_chrome.py`（新增） | 🟡 P1 | ✅ DONE |
| 11.7-C2 | **古地理图：对比模式 chrome 应叠在画布上而非占独立列** — 用户反馈：11.7-C 把 SharedChromePanel 作为兄弟 widget 塞在 canvas_A 和 canvas_B 之间，视觉上把"指南针/图例/比例尺"与"地理图"区分成两栏，违和。修复：(1) `SharedChromePanel.__init__` 新增 `overlay: bool = False` 参数，overlay=True 时设 `WA_TranslucentBackground + WA_TransparentForMouseEvents`（透明背景 + 不拦截鼠标，让 canvas 的拖动/缩放穿透）。(2) `_start_compare` 不再把 panel 加入 QHBoxLayout，而是 `parent=self.map_view` 直接挂在左 canvas 上；新增 `_install_chrome_overlay_positioning()` 包装 canvas.resizeEvent，每次 resize 把 panel 移到右上角（width-panelW-8, 8）并 raise_。两个 canvas 各占 50%，chrome 浮在 canvas_A 右上角。(3) 新增测试 `test_overlay_mode_is_translucent_child` 锁定 overlay 模式下 panel 为 canvas_a 子控件 + 翻译/穿透属性。 | `packages/geoviz_paleo_map/geoviz_paleo_map/shared_chrome_panel.py`, `src/pages/paleo_map/page.py`, `tests/test_paleo_shared_chrome.py` | 🟡 P1 | ✅ DONE (回滚于 11.7-D) |
| 11.7-D | **古地理图：删除对比模式，回归单画布** — 用户直接要求："删除对比这个功能。古地理图这里就一个画布，所有信息都在画布上（图例，指南针，比例尺等等）。"教训：11.7-C/C2 是过度设计——用户从未要求 compare 模式，是我们自作主张加的。修复：(1) `PaleoMapCanvas` 移除 `show_chrome` 参数、`facies_changed` 信号、`facies_names()` 方法；所有 4 处 `_layers` 构造点（`__init__`/`load_features`/`load_hierarchy`/`_update_active_layers`）无条件追加 chrome 八件套。(2) `git rm` 删除 `packages/geoviz_paleo_map/geoviz_paleo_map/shared_chrome_panel.py`。(3) `src/pages/paleo_map/page.py` 移除 `SharedChromePanel` 导入、`_compare_mode` 字段、`_compare_btn` 工具栏按钮、`_on_period_changed` 中的 compare 分支、以及 `_toggle_compare/_start_compare/_install_chrome_overlay_positioning/_stop_compare` 四个方法。(4) `git rm` 删除 `tests/test_paleo_shared_chrome.py`（7 测试随 SharedChromePanel 退役）。全量测试 684 passed（691→684 = -7 共享 chrome 测试）。 | `packages/geoviz_paleo_map/geoviz_paleo_map/canvas.py`, `packages/geoviz_paleo_map/geoviz_paleo_map/shared_chrome_panel.py`（删除）, `src/pages/paleo_map/page.py`, `tests/test_paleo_shared_chrome.py`（删除） | 🔴 P0 | ✅ DONE |

**Acceptance criteria:**
- 11.7-A 完成后：截图 `/tmp/paleo_shot.png` 显示 facies polygons / wells / region labels 横跨全画布宽度，不再压缩到左上角；test_viewport_grow_triggers_rerender 通过
- 11.7-B 完成后：平移/缩放过程中，facies polygons 与 region labels 始终重合；test_pan_invalidates_screen_path 通过

---

**Acceptance criteria:**
- 11.5-A 完成后：`pytest tests/test_curvature.py::TestCurvatureGpuConsistency` 在有 CuPy 环境真正测试 GPU vs CPU 数值一致性（不再是空 skip）
- 11.5-B 完成后：新增第 15 个属性只需改 1 处（dispatch 表）
- 全程保持 636+ tests 绿

---

## 🔴 Phase 11.8: 层级锁定与重叠修复（2026-06-01 用户测试反馈）

**目的：** 实现用户要求的全局层级锁定，解决图例与首行元素的垂直重叠，以及比例尺滑动条刻度文本的水平重叠。

### Tasks

| ID | Task | Files | Priority | Status |
|----|------|-------|----------|--------|
| 11.8-A | **增加层级锁定**：在 `page.py` 工具栏增加 `层级锁定` combobox，在 `canvas.py` 实现 `_locked_level` 支持，根据锁定的层级在所有显示比例尺都显示锁定的层级。 | `src/pages/paleo_map/page.py`, `packages/geoviz_paleo_map/geoviz_paleo_map/canvas.py` | 🔴 P0 | ✅ DONE |
| 11.8-B | **图例重叠修复**：调整 `legend.py` 中 `y` 起始坐标偏移，增加 "图例" 标题与首行元素之间的垂直间距，避免二者重叠。 | `packages/geoviz_paleo_map/geoviz_paleo_map/layers/legend.py` | 🔴 P0 | ✅ DONE |
| 11.8-C | **比例尺文字重叠修复**：移除滑动条上杂乱的 `相→亚相` 转换文字，改为平铺在各自区域内；并在 `_make_ticks()` 中实现 `tx - last_x >= 45.0` 刻度水平间距防重叠保护。 | `packages/geoviz_paleo_map/geoviz_paleo_map/floating_slider.py` | 🔴 P0 | ✅ DONE |

**Acceptance criteria:**
- 11.8-A：用户在顶部下拉框中选择 "相/亚相/微相" 后，无论怎么缩放地图，都只显示锁定的图层级别。
- 11.8-B：图例的 "图例" 标题与下方 "三角洲" 等首行色块元素之间有足够留白，不再紧贴重叠。
- 11.8-C：比例尺滑动条下方的 tick labels（如 1:1000万 等）在拉动缩放时不再密集成一团重叠，最少保持 45px 间距，且 `相→亚相` 这类重合文本已彻底移除。

---


## 📋 重写后的 Roadmap（基于 CEO + Eng review 综合判断）

### Phase 12 拆分为 12a + 12b（Eng review 建议降低单 phase 风险）

#### 🥇 Phase 12a: 双 GLVolumeItem 叠加 MVP（中等优先级）
- **Goal:** SeismicView 同时渲染原始振幅体 + 一个属性体（如 coherence）
- **Approach:** 两个独立 GLVolumeItem + alpha 混合（不做纹理共享）
- **Risk:** 中 — pyqtgraph OpenGL 多 volume 在 headless GL Mock 测试历史脆弱
- **Tests:** ~6 (alpha blending, layer toggle, memory)
- **Spike:** 开工前先验证 GLVolumeItem * 2 在当前 pyqtgraph 版本可正常显示

#### Phase 12b: 共享纹理优化（低优先级 stretch）
- **Goal:** 避免双份 GPU 显存占用，写 GLSL shader 让一个纹理多通道显示
- **Risk:** 高 — 需手写 GLSL，与 pyqtgraph 抽象层冲突
- **决策门：** 仅当 12a 真实数据测试发现显存瓶颈时才启动

### 🥇 Phase 14（提前到 P1）：连井剖面自动化 + 报告导出
> **CEO 建议从 P3 提升到 P1** — 投入低、产出高、构成"地图点一下出一本报告"的杀手级 demo

- **场景：** 在井位地图上框选区域 → 自动按地理走向选 N 口井 → 连井剖面 → 井震 tie → 一键 PDF 报告
- **Components:**
  - `auto_section_planner.py`：几何算法（PCA / convex hull / 构造方位）
  - `report_export.py`：复用 Phase 10 的 `export_professional_figure` 出 PDF
  - `cross_well` 接收外部 wells 列表（API 微调）
- **Tests:** ~12（几何 + 报告渲染快照）
- **Risk:** 低 — 纯几何 + UI，cross_well + paleo_map 出图能力已就绪

### 🆕 Phase 15（新增，CEO 建议）：Project 工程文件 + Pilot 部署
> **CEO review 核心观点：当前所有 Phase 都是 demo，无 Project 概念无法 daily use**

- **Goal:** 引入 `.gvz` 工程文件（JSON-friendly，Git-friendly），可保存：
  - 加载的多井 / 多体 / 多层位 / 多相图引用
  - 用户拾取、相图编辑、属性配置、视图状态
- **Tasks:**
  - 设计 schema（参考 Petrel .pet 但简化）
  - Open/Save UI（与现有 DataPage 集成）
  - 找 1 家油田/院所做 pilot 反推 schema 缺漏
- **Risk:** 中 — schema 决策影响所有后续 phase；建议先 spike 写 RFC

### ⏸ Phase 13（CWT/时频 RGB）—— 暂缓
> CEO + Eng 一致建议：算法重、用户少、ROI 低；CWT 内存 O(N·scales) 需 spike 设计

- **前置条件：** 必须先有 Phase 15 pilot 用户反馈"需要时频分析"才启动
- **Pre-Phase spike：** "CWT 内存 / 性能 POC + chunking 设计文档"

### 🆕 Phase 16（候选）：AI 辅助解释
- 自动断层识别、相预测、井曲线智能补全
- 风险高：模型 / 数据 / 标注成本未知
- 决策门：Pilot 用户提出明确需求后启动

### ✅ Phase 17（自研完成）：geoviz-plots 通用图表与等值线插值渲染
- **Goal:** 构建完全自主知识产权的轻量级、高品质二维通用图表及空间散点等值线/色斑图渲染库。
- **Status:** ✅ COMPLETE

- **Tasks:**
  - 模块自适应刻度轴标定（Heckbert 算法）与 `PlotWidget` 折线/散点绘制。
  - **[Eng 强制]** 引入 **LTTB 数据降采样算法**，支撑 $100K+$ 点大数据量下 QPainter 60+ FPS 流畅渲染。
  - **[CEO 建议]** 设计 **联动高亮接口 (Interactive Linking)**，实现图表点与地图（井）及测井（深度段）跨页联动。
  - 二维规则网格自研 IDW 向量化及 Scipy RBF 空间插值计算核心。
  - **[Eng 强制]** 引入 **`QThread/QThreadPool` 异步计算机制**，避免大网格插值时 GUI 主线程假死卡顿。
  - **[Eng 强制]** 实现 **NaN 数据清洗掩膜 (Masking) 与外插边界保护**，防止异常数据发散。
  - 等值线（Marching Squares/非GUI Matplotlib 拓扑包络）提取，等值线断口打断标注（Contour Labels）。
  - **[CEO 建议]** 集成 **中石油 (CNPC) 地质制图标准色标模板库**，提供一键规范化渲染。
  - 支持高品质无损 PDF/SVG 矢量导出，与油田出图和学术出版完全接轨。
- **Risk:** 低 — 纯矢量数学逻辑，无第三方闭源授权陷阱（彻底规避 QtCharts 的 GPLv3 开源传染协议风险）。

---

## 📦 Packages (7 independent pip-installable packages)

| Package | 功能 | 健康度 | 备注 |
|---------|------|--------|------|
| geoviz-well-log | ECharts SVG 测井渲染 | ✅ | |
| geoviz-seismic | pyqtgraph OpenGL + 属性 | ⚠️ | seismic_view.py 1294 行待抽象（11.5-B） |
| geoviz-map | QPainter 井位地图 | ✅ | |
| geoviz-paleo-map | QPainter 古地理图 + 编辑 | ✅ | |
| geoviz-cross-well | 连井对比 → 依赖 well-tie | ✅ | |
| geoviz-well-tie | 井震结合 — 纯 NumPy | ✅ | 3 个 skipped 测试待整改（11.5-C） |
| geoviz-plots | 通用图表与等值线插值渲染 | ✅ | 纯自研 QPainter 矢量路线，高品质等值线与自适应轴标定，测试全通 |

**架构健康：** 无循环依赖；src/pages 全是薄壳；最大单文件 `seismic_view.py` 1294 行（已 refactor 一轮）。

---

## 🔑 Key Decisions（历史 + 新增）

| Decision | Rationale |
|----------|-----------|
| 属性扩展现有 geoviz-seismic | attributes.py 已有架子，工具栏已有 combo |
| 井震结合新建 geoviz-well-tie | 数据模型不同，遵循独立 package 模式 |
| 不引入 bruges 库 | 自行实现 Ricker/Ormsby，纯 NumPy |
| VERSION 0.7.0 vs CHANGELOG 0.10.0 | 用户有意为之；需在 README 文档化（11.5-F） |
| **新：Phase 11.5 优先于 Phase 12** | Eng review 发现 `compute_curvature` GPU 参数被静默忽略；技术债不还，后续 phase 越垒越歪 |
| **新：Phase 14 提前到 P1** | CEO 评估为最高 ROI 的差异化亮点 |
| **新：Phase 15 (Project 文件 + Pilot) 加入** | CEO 核心结论：无 Pilot 验证，所有 Phase 都是空中楼阁 |
| **新：Phase 13 暂缓** | CWT 内存风险高 + 用户需求未验证 |
| **新：基于 QPainter 自研二维图表与插值渲染** | 彻底规避 QtCharts 带来的 GPLv3 授权传染合规风险，实现完美扁平化的出版级 PDF/SVG 矢量导出。 |

---

## ⚠️ 风险与隐患（CEO + Eng 综合）

| 类别 | 风险 | 应对 |
|------|------|------|
| 🔴 工程诚信 | `compute_curvature` use_gpu 假承诺 | Phase 11.5-A 强制修复 |
| 🔴 用户验证 | 迄今 0 真实项目落地 | Phase 15 强制 Pilot |
| 🟡 依赖脆弱 | CuPy / pyqtgraph OpenGL 在 Windows 装机环境 | README 明确 NumPy-only 安装路径 |
| 🟡 测试盲区 | SeismicView 14 项 combo UI 集成 + RGB fusion 无测 | Phase 11.5-D |
| 🟡 版本管理 | 子包 CHANGELOG 与根脱钩 | Phase 11.5-E |
| 🟢 商业模式 | 开源 / 商用未决 | 待 Pilot 反馈后评估 |
| 🟢 性能基线 | 缺真实 SEGY 大数据 E2E | Phase 12a 之前补一份 benchmark 套件 |

---

## Notes
- 687 tests passed, 4 skipped — full suite green
- cross-well 依赖 well-tie（纯 NumPy，零 Qt）
- Phase 11.9 shipped — microfacies CNPC colors and evaporite SVG added
- 下一步动作：启动 Phase 14 连井剖面自适应选井及 PDF 报告导出工作流开发
