# Task Plan: GeoViz Engine — 项目总览与下一步规划

> **更新于 2026-05-31**：基于 CEO + Eng 双重 review 重写。明确区分"已完成 / 待修复 / 下一步"。
> **同步于 2026-05-31**：Goal/Current State 同步至 Phase 11.7-D 完成后的真实状态。

## Goal
GeoViz Engine 是一款基于 PySide6 的桌面地质数据可视化引擎。Phase 1–17 已完成，702 tests passed。**核心市场定位**：科研院所 + 中小油田 + 教学（差异化于 Petrel 的轻量、可二次开发、出版级出图）。

## Current State
- **Branch:** feat/geoviz-plots
- **Tests:** 847 passed, 4 skipped (4 skipped 来自 `test_seismic_view.py` 对 `pyvistaqt.QtInteractor` 的环境探测——无显示则 skip，为正确的环境闸门行为，不待整改)
- **Latest commit:** Phase 22a + 22b + 22c complete
- **Active phase:** None
- **Health rating:** A（Phase 22 DONE，847 tests passed，all dead controls resolved）

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
| 12a | 双 GLVolumeItem 叠加 MVP | ✅ | 振幅体与属性体叠加，GPU colormap 及独立不透明度控制 |
| 12b | 共享纹理与 GLSL 着色器深度优化 | ✅ | 单 3D 纹理多通道打包，GLSL 在线色彩映射与混合，VRAM 减半，O(1) 调参 |
| 14 | 连井剖面自动化与专业报告导出 | ✅ | 井位地图 Shift+Drag 框选，PCA 自动走向排井，高保真 PDF 报告导出 |
| 15 | Project 工程文件序列化 (.gvz) | ✅ | 基于 Pydantic 的 Git 友好 schema，相对路径转换，DataPage UI 整合 |
| 19 | 高阶可视化增强 (3D 结构增强与科学制图) | ⏳ | 3D地层雕刻、梯度光照、防碰撞标注与 LOD 路径简化 |
| 20 | UI 视觉全量升级 (Azurite Design System) | ✅ | 像素级还原 UI-REF 蓝铜设计规范，全量重构主窗口 Shell 并实现 Chrome 动态响应 |
| Audit | 连井专题深度审计与修复（2026-06-01 用户回归发现） | ✅ | 修复连井带 28px 标签偏移错 位， 解决点击穿透 and Canvas 消费导致手动连井不起作用，实现连井带与拾取点对齐、跟随 Zoom/Pan 实时平移缩 放渲染 |
| 21 | UI 交互深度联动整合 (Premium UI Interactive Complete Integration) | ⏳ | 对设置页面、6大辅助工具、DataPage KPI、PlotsPage实时插值和合成标定进行交互深度联动，确保 100% 交互响应 |


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
| 11.6-I | **连井：连井带显示错位** — 根因：`ConnectionOverlay.depth_to_y` 未累加 well log canvas 顶部的 28px 标签高度，导致绘制的所有连线和色斑多边形整体向上偏移 28 像素。修复：在 `depth_to_y` 中使用 `canvas.mapTo(parent, ...)` 动态且通用地转换 Y 轴物理偏移坐标。 | `packages/geoviz_well_log/geoviz_well_log/connection_overlay.py` | 🔴 P0 | ✅ DONE |
| 11.6-J | **连井：手动连井不起效果** — 根因：(1) 新版 UI 遗漏了手动连井按钮；(2) 即使开启，各 well canvas 内部重写了鼠标捕获并默认 `accept()` 吞掉点击，导致事件无法向传递给 `CrossWellWidget.mousePressEvent`。修复：(1) 工具栏补回「手动连井」按钮并做互斥同步；(2) 利用 Qt 事件过滤器 `eventFilter()` 机制，在 `CrossWellWidget` 侧拦截 child canvas 的左键点击并转译为合成点击事件分发，成功触发连线。 | `packages/geoviz_well_log/geoviz_well_log/cross_well_widget.py`, `src/pages/cross_well/page.py` | 🔴 P0 | ✅ DONE |
| 11.6-K | **连井：连井带不跟随视口缩放** — 根因：`ConnectionOverlay` 和 `PickingOverlay` 均属于浮动透明遮罩，在 well log canvas 触发缩放（Zoom）和滚动（Pan）改变 depth 范围时，没有连接任何信号来通知遮罩重绘，导致连线和色斑图死板地“漂浮”在旧物理位置上。修复：在 `CrossWellWidget` 的 `add_canvas` 内将 `depth_range_changed` 信号级联连接到 `_overlay.update` 及自定义的 `canvas_depth_changed` 信号，使得缩放滚动时两个 Overlay 能够实时随之自适应联动重绘。 | `packages/geoviz_well_log/geoviz_well_log/cross_well_widget.py`, `packages/geoviz_cross_well/geoviz_cross_well/canvas.py` | 🔴 P0 | ✅ DONE |

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

#### Phase 12b: 共享纹理与 GLSL 深度优化（DONE ✅）
- **Goal:** 避免双份 GPU 显存占用，通过单个 DualGLVolumeItem 包装多通道数据，手写 GLSL Fragment Shader 在 GPU 端完成在线 colormapping 和 alpha blending。
- **Benefit:** GPU VRAM 开销降低 50%，拖拽不透明度/切换色标性能由 O(N^3) 纹理重传缩短为 O(1) 仅更新 shader uniforms，体验极速流畅。
- **Tests:** 新增专门的 `test_dual_gl_volume_item_unit` 测试以验证其正常运行。

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

### 🆕 Phase 18: 测井与连井深度性能优化 (Excel 加载与 QPainter 渲染)
> **Goal**: 解决读取 Excel 慢和多井道渲染卡顿的问题，实现秒级加载与极速重绘。

- **Tasks & Roadmap**:
  - **OPT-1 (🔴 P0) - WellLogCanvas QPixmap 静态层缓存**: 将静态渲染轨道内容缓存至 `QPixmap`，鼠标移动和十字丝悬浮时仅重绘 Overlay/Crosshair，避免每帧全量重绘 8-12 个 Track Widget。 (✅ DONE)
  - **OPT-2 (🔴 P0) - Excel 延迟/按需 Sheet 读取**: 优化 `loaders.py` 中的 `pd.read_excel`，仅解析所需的 Sheet（如 `测井曲线`、`地层系统` 等），避免一次性加载全部 10+ Sheet，大幅缩短首次解析耗时。 (✅ DONE)
  - **OPT-3 (🟡 P1) - 二进制缓存机制（Pickle/MsgPack）**: 将大容量 `CurveData` 从 JSON 格式（浮点数文本反序列化慢）改为二进制序列化缓存（MsgPack 或 Python Pickle），使缓存命中路径的读取速度提升 3-5 倍。 (✅ DONE)
  - **OPT-4 (🟡 P1) - 多线程/进程异步并行加载**: 将连井页面中的多口井顺序串行加载修改为基于 `QThreadPool` 或 `concurrent.futures` 的并行读取，缩短首次无缓存情况下的总等待时间。 (✅ DONE)
  - **OPT-5 (🟡 P1) - CurveTrack QPainterPath 缓存与 NumPy 向量化坐标转换**: 在视口/尺寸未改变时，复用已生成的 `QPainterPath`；在重绘时利用 NumPy 进行大批量的深度/测井值与屏幕物理坐标的矩阵式映射转换，完全消除 Python 逐点 `lineTo` 的循环开销。 (✅ DONE)
  - **OPT-7 (🟢 P2) - 连井事件节流与重绘微内核合并**: 对 `CrossWellWidget` 里的 `depth_range_changed` 缩放/滚动重绘信号进行 coalescing（16ms 节流合并），平滑多井联动时的瞬间计算压力。 (✅ DONE)

- **Acceptance Criteria**:
  - 10 口井连井场景下，鼠标移动帧率稳定在 60+ FPS (鼠标移动重绘时间由 ~50ms 降至 <2ms)。
  - 首次无缓存加载单井耗时控制在 1.0s 内，缓存命中路径读取耗时控制在 100ms 内。

---

### 🆕 Phase 19: 高阶可视化增强 (3D 结构增强与科学制图)
> **Goal**: 提升 3D 解释的直观性与 2D 地图的专业出版质量。

- **Tasks & Roadmap**:
  - **Task 19.1 (🔴 P0) - 3D 地层雕刻 (Horizon Sculpting)**: 在 `Renderer3D` 中实现基于层位面的体数据实时切除（GLSL Fragment Shader `discard` 逻辑），仅显示特定层段内部数据。
  - **Task 19.2 (🔴 P0) - 3D 梯度光照 (Hillshading)**: 在 GPU 端实时计算地震反射面的 3D 梯度强度，通过调制亮度产生“凹凸感”阴影，大幅增强细微构造识别度。
  - **Task 19.3 (🟡 P1) - 地图防碰撞动态标注 (Collision-aware Labeling)**: 为井位和沉积相区域实现贪婪/力导向标注算法，确保缩放时文字不重叠。
  - **Task 19.4 (🟡 P1) - 视口相关矢量路径简化 (LOD)**: 实现沉积相多边形边界的 Level of Detail (LOD) 机制，根据比例尺自动简化路径，平衡交互性能与数百 MB PDF 导出的精细度。
  - **Task 19.5 (🟢 P2) - 自适应颗粒纹理缩放**: 优化 `PatternEngine`，使岩性 SVG 图案颗粒大小随视口缩放动态调整，模拟真实地质放大观察效果。

- **Acceptance Criteria**:
  - 3D 窗口支持“显示万山组至泥盆系之间”的独立切块，切换时无明显延迟。
  - 地震反射层在侧光模式下呈现清晰的浮雕阴影。
  - 地图在多井密集区自动隐藏或偏移标签，保持 100% 文字可读。

---

### 🆕 Phase 20: UI 视觉全量升级 (Azurite Design System 像素级还原) ✅ DONE (2026-06-02)
> **Goal**: 深度还原 `UI-REF` 里的 HTML 蓝铜设计规范（Azurite Design System），实现主窗口与各子页面的高保真还原与线性图标完美同步。

- **Tasks & Roadmap**:
  - **Task 20.1 (🔴 P0) - 核心 AppShell 主架构重构 (MainWindow 像素级升级)**:
    - 将 `MainWindow` 的侧边栏宽度从 `160px` 拓宽至 `212px`，背景色统一为纯白 `#ffffff`，右侧框线为 `#e5eaf1`。
    - 在侧栏顶部集成完整的品牌区：包含铜蓝渐变背景的 `brand-mark`（内含 `seismic` 图标）及高精细的 HTML 富文本品牌名 `GeoViz <span style="color: #92a0b0; font-weight: 500;">Engine</span>`。
    - 引入顶部页头部件 (`hdr`, 高度 `52px`, 背景 `#ffffff`, 底边框 `#e5eaf1`) 和底部状态栏部件 (`status`, 高度 `26px`, 背景 `#ffffff`, 顶边框 `#e5eaf1`)，实现与 Web 页面完全一致的布局。
  - **Task 20.2 (🔴 P0) - 页头上下文与全局状态栏的响应式动态绑定**:
    - **页头标题与副标题动态同步 (`HCtxA`)**: 切换页面时，页头左侧动态更新为与 UI-REF 完全一致的标题与副标题。如：地图页 ("地图总览", "46 口井 · EPSG:4326")、古地理图 ("古地理图", "沧浪铺组 · Plate Carrée") 等。
    - **页头工具栏按需渲染 (`hdr-tools`)**: 为各子页面配置独立的工具栏按钮集合，直接嵌入页头右侧（利用 linear 图标资产如 `layers`、`ruler`、`palette`、`export`、`undo`、`redo`、`filter` 等），且支持中/英文切换下拉项 ("中文" 带 `globe` 图标)。
    - **状态栏动态更新**: 在底部状态栏左侧放置绿色呼吸灯 `dot` (`#2ca36b`) 和页面就绪状态文案，右侧常驻显示 `GeoViz Engine v0.8.0`。
  - **Task 20.3 (🔴 P0) - 侧栏导航分组化与底部设置菜单**:
    - 在侧栏菜单中引入 `.side-group-label`（分组小标题，大小 10.5px，加粗，间距 0.8px，大写，颜色 `#92a0b0`），分为 “可视化” (前6页) 和 “工作区” (后2页) 两大类别。
    - 在侧栏底部 (`side-foot`) 增加一条细线分割，并常驻放置 “设置” (Settings) 导航菜单，悬浮与点击状态与普通导航项对齐。
    - 重构导航按钮 `SidebarButton`：选中时显示为背景 `#e9effa`、前景色 `#1f66d4`、加粗，且左侧边缘显示一条 `3.5px` 宽 of 蓝色高亮长条指示器 (`border-left: 3.5px solid #1f66d4`)，深度贴合 `.nav-item.on::before` 视觉效果。
  - **Task 20.4 (🟡 P1) - 蓝铜设计规范 QSS 全局标准化**:
    - 重写 `main.py` 的全局样式表，收敛至 Azurite 配色：主要文字 `#1a2433`，次要文字 `#586878`，边框 `#d3dbe6`。
    - 将 `QGroupBox` 深度改写为 `.card` 样式：圆角 `12px`，边框 `#e5eaf1`，背景纯白 `#ffffff`，并配以微弱卡片投影。
    - 标准化 `QLineEdit`、`QComboBox`、`QSpinBox` 圆角为 `6px`，焦点状态下边框变为主色 `#1f66d4`。
  - **Task 20.5 (🟡 P1) - 页面及子部件的像素级深度对齐 (Subpages High-Fidelity Configuration)**:
    - **地图页 (MapPage)**:
      - 页面采用左右分栏。左侧为 `252px` 宽的侧边栏，背景 `#ffffff`，带搜索框（背景 `#fafbfd` 且输入框带 `search` 线性图标）、三个分类 Chip (`全部 46`, `已解释 31`, `含气 12`)，以及井位滚动列表（左侧 `pin` 图标，右侧带高度 Tag）。
      - 右侧底图上配置坐标网格标定，并在已选中的井位上展示高亮光晕气泡（外圈大半透明圈，内圈 `accent` 圆心）。
      - 弹出悬浮信息卡片（Well Callout Card），高精度展示选中的井名、Gas 标签、地理坐标与主按钮“打开井剖面”。
      - 地图画布的右上角悬浮一套白卡片工具栏 (`float-tb`，含 `zoomIn`, `zoomOut`, `fit`, `ruler`)；左上角悬浮图层管理器白卡片，左下角悬浮比例尺与指北针。
    - **古地理图页 (PaleoMapPage)**:
      - 页面采用左右分栏。右侧为 `230px` 宽的沉积相图例侧边栏，包含沉积相色斑图例和图层控制项（用白底透明背景的 Toggle Switch 滑块实现高保真开关），底部带“导出图件”按钮。
      - 地图画布渲染相带填充并融合岩性 SVG 纹理（包含 `pf-dots`, `pf-wave`, `pf-dash`, `pf-ring` 等），并在相带中央绘制相名称标注，井投影显示为地质标准的十字交叉针圆圈符合。
      - 地图右上角配置 `float-tb` (含 `zoomIn`, `zoomOut`, `fit` 图标)，左下角配置指北针图标。
    - **井剖面页 (WellLogPage)**:
      - 控制面板高度重构为无缝贴合的白卡片样式，包含井选择 Dropdown、深度范围标签、双段 Toggle Button ("综合柱状" / "曲线叠合")，以及 "轨道"、"导出 SVG" 动作按钮。
      - 剖面纸张主区域配置 11 个独立的轨道（从左到右：地层系统、AC/GR 曲线、深度、岩性图、RT/RXO 曲线、岩性描述、微相、亚相、相、体系域、层序），头部显示高精度的变量与刻度，轨道内容填充地质纹理、曲线色谱和文字走向。
    - **连井对比页 (CrossWellPage)**:
      - 顶栏包含连井属性标签 "4 口井 · PCA 自动排井"，段按钮 ("拾取", "连接", "浏览")，以及 "DTW 自动对比" 与 "超宽 SVG" 导出按钮。
      - 主画布为超宽滚动视图，多井之间绘制优美的三次贝塞尔连接色带（Facies Connectivity Bands），并在层位界线上绘制虚线连接线 (Tops Pick Lines) 和标志性 Pick 点；每口井顶部渲染 `accent-soft` 色块的井名标签。
    - **地震 3D 页 (SeismicPage)**:
      - 采用左右分栏。左侧主区域包含两个白底圆角卡片：上半部分为 "3D 体渲染 · GLVolumeItem" 黑色画布（绘制 3D oblique 立方体，前面板渲染地震层位波形波段，顶部叠加 horizon surface 及井柱）；下半部分为 "2D 剖面 · inline 420" 剖面图（带 Wiggle 波形包络曲线）。
      - 右侧为 `226px` 宽控制面板，带有 Inline/Crossline/Time 滚动条、Colormap 色卡带（seismic, gray, jet 切换）和井震标定 Auto-Tie 参数面板。
    - **平面图件页 (PlotsPage)**:
      - 左侧为平面图卡片，高精细度展示“沧浪铺组 砂体厚度等值图”，绘制渐变的多级砂体厚度色斑多边形和轴标定。
      - 右侧为 `200px` 宽插值控制面板，包含插值方法切换 (IDW / RBF / Kriging)、幂指数滑块、垂直渐变 Colormap 色条与导出 PDF 按钮。
    - **数据管理页 (DataPage)**:
      - 顶栏包含 "导入数据" 主按钮，以及 Excel / LAS / SEGY 快速导入小按钮，右侧带过滤输入框。
      - 页面中部为 4 个 KPI 卡片（注册井数、缓存占用、数据格式、Calamine 引擎速度）。
      - 下半部分为高保真数据表格（`table.gv` 样式），带 sticky 表头、状态指示点和向右详情箭头。
    - **工具箱页 (ToolsPage)**:
      - 标题带 "独立小工具集" 说明，下部平铺 6 个圆角白卡片工具（如 XML 转换、层位补全等），卡片内左侧采用 `accent-soft` 背景的图标，右侧为工具名、Tag 芯片和工具描述，鼠标悬浮带浮雕阴影。
  - **Task 20.6 (🟢 P2) - 启动闪屏 (Splash Screen) 与渐变动效**:
    - 新增启动闪屏，高保真呈现暖白背景 `#faf9f5` 下铜蓝渐变 Logo 逐渐淡入的解包动效，提升首屏高级感。

- **Acceptance Criteria**:
  - 应用界面骨架完美对齐 `UI-REF`，包含页头、212px 分组侧栏、主页面、状态栏。
  - 侧栏菜单点击切换时，页头标题、副标题、工具按钮及底部状态文字实时、无延迟同步响应。
  - 整个应用没有任何原生/粗糙的 Qt 边缘，圆角、描边、字色、背景色严格遵循 Azurite (Direction A) 主干规范。
  - 所有子页面（WellLog、CrossWell 等）与主框架视觉无缝贴合。

---

### ✅ Phase 21: UI 交互深度联动整合 (Premium UI Interactive Complete Integration) — DONE (2026-06-02)
> **Goal**: 围绕全新 Azurite 视觉大框架，对全量子页面进行 100% 深度交互与响应逻辑的开发与对齐，彻底告别只读占位符，保证所有按钮、滑块、配置项都有敏捷的地质背景数据和图形响应，提供极致的生产力体验。
>
> **Result**: 5/5 子任务全部 TDD 完成，新增 46 个测试全绿，全套 801 tests passed。

- **Tasks & Roadmap**:
  - **Task 21.1 (🔴 P0) ✅ - 独立设置页面 (SettingsPage) 与偏好广播持久化** — 6 tests GREEN:
    - **设置主页面**：新增 App 偏好设置页作为 Stack 的第 9 个常驻页，连接侧栏底部的“设置”按钮。
    - **主题动态切换**：提供 QComboBox 进行“浅米白 (默认) / 矿石灰”主题切换，触发加载对应的 QSS 文件并重刷全界面。
    - **坐标网格分发**：支持十进制 DD 格式与度分秒 DMS 格式一键切换，并通过全局信号（`coordinate_format_changed`）实时重置 MapPage / PaleoMapPage 的状态显示及标定值。
    - **高速缓存清除**：加入一键清理地质切片与 SVG 矢量图缓存动作，并在按钮右侧带转动动画及即时释放容量显示（MB/GB级）。
  - **Task 21.2 (🟡 P1) ✅ - 工具箱 (ToolsPage) 6 大独立小工具交互对话框闭环** — 18 tests GREEN:
    - **浮雕卡片点击响应**：为 ToolsPage 的 6 大卡片注册交互点击过滤器，点击时滑出/弹出一个专用的 Azurite 规范对话框 (Dialog Drawer) 并加载真实功能：
      1. **SEGY 头信息查看器 (SEGY Header Inspector)**：用户导入 SEGY，直观呈现并检索 EBCDIC 文本头及二进制线头数据。
      2. **测井曲线深度采样器 (LAS Curve Resampler)**：允许导入测井曲线，设置采样间隔步长进行降采样并输出对比。
      3. **井斜校正计算器 (Deviation/TVD Calculator)**：支持输入测斜表 (MD/Incl/Azim)，采用最小曲率法计算并输出 TVD/X/Y 三维轨迹坐标表。
      4. **XML 坐标转换工具 (XML Coordinates Converter)**：提供北京54/西安80/CGCS2000 投影坐标与经纬度的批量换算界面。
      5. **地层分层缺失自动插值器 (Tops Completion Interpolator)**：向导式缺失层位推导工具，辅助生成连井背景层。
      6. **Calamine 脚本高速编译引擎 (Calamine Compiler Simulation)**：地质公式的高速校验与编译提示框。
  - **Task 21.3 (🔴 P0) ✅ - 数据管理卡片 (DataPage) KPI 状态指标动态刷新与表项级联** — 6 tests GREEN:
    - **运行数据绑定**：将 DataPage 中部的 4 个大卡片 KPI 数值直接连接到底层 Cache（如 `len(self.cache.wells)` 动态刷新已注册井数，缓存占用空间以 `os.path.getsize` 计算，加载 SEGY IO 速度等）。
    - **表项向右箭头详情**：表格每行最右侧的 "向右箭头" 添加悬浮及点击响应，滑出右侧侧拉面板，精细展示此井的完整工程 JSON 元数据，并支持直接对其进行更名和快速删除操作。
  - **Task 21.4 (🟡 P1) ✅ - 平面图件页 (PlotsPage) 砂厚图参数实时插值与一键更新** — 6 tests GREEN:
    - **参数联动**：将右侧控制面板中所有的插值参数（插值方法 IDW/RBF/Kriging 下拉框、K值幂指数滑块、网格分辨率）与左侧 QPainter 二维图表连接。
    - **自动重算**：当用户拖动滑块或切换下拉框时，毫秒级异步触发后端插值运算，实时重绘带平滑等值线和色调斑块的“沧浪铺组砂体厚度图”，解除静止画面的呆板体验。
  - **Task 21.5 (🔴 P0) ✅ - 测井与平面地图双向联动工作流 (Map-to-WellLog Linkage)** — 3 tests GREEN:
    - **双向对齐**：在 MapPage 选中某口井，点击悬浮信息卡片（Well Callout Card）中的“打开井剖面”按钮时，不仅切换到测井页 (WellLogPage)，并且使测井页面的“当前井下拉框”立即变更并加载该井的 11 条地质曲线。

- **Acceptance Criteria**:
  - 点击“设置”菜单，界面流畅滑入第 9 页，视觉完全对齐 Azurite 扁平白卡片风格。
  - 改变坐标格式，平面地图和古地理图的坐标标定文字瞬时完成 DD 与 DMS 格式刷新，不产生内存重叠或黑白闪动。
  - 工具箱内 6 个小工具弹窗在 1280px 分辨率下完美适配，能导入本地 SEGY/LAS 文件并展现正确的地质图表。
  - 改变 PlotsPage 二维插值参数时，等值线及厚度色斑重绘耗时 < 300ms 且无卡顿。
---

### 🆕 Phase 22: Dead UI 大扫除 (Dead UI Audit & Fix)
> **Goal**: 2026-06-02 8-agent fan-out audit 发现 138 个控件中 60 个有不同程度的问题（3 崩溃、28 无响应、16 桩、13 有 bug）。逐项 TDD 修复，消灭所有死控件。

- **Sub-phases**:
  - **Phase 22a (🔴 Critical)**: 3 崩溃 + 20 HeaderToolButtons + MapPage 芯片/图层开关
  - **Phase 22b (🟡 High)**: ToolsPage 4 对话框后端 + SettingsPage 信号监听 + DataPage 导入/重命名/删除 + PaleoMap fit
  - **Phase 22c (🟢 Medium)**: QThread 泄漏 + 孤立代码清理 + 未使用导入 + 小 bug

#### Phase 22a (🔴 Critical) ✅ DONE — 2026-06-02

- **Task 22a.1 (🔴 P0) - PlotsPage SVG/PDF 导出按钮崩溃修复** ✅:
  - `_export_svg` 和 `_export_pdf` 使用 `QSvgGenerator` / `QPainter` 但从未导入 → `NameError`
  - 修复: 添加 `from PySide6.QtSvg import QSvgGenerator` + `from PySide6.QtGui import QPainter`
  - Tests: 4 tests in `test_plots_export_imports.py`

- **Task 22a.2 (🔴 P0) - PaleoMapPage 图层可见性开关崩溃修复** ✅:
  - "显示井位标定" / "显示沉积相标注" toggle 访问 `self.map_view.layers` → `AttributeError` (私有属性 `_layers`)
  - 修复: 在 `PaleoMapCanvas` 添加 `layers` property; 在 `PaleoLayer` 添加 `visible` 属性; `WellsScatterLayer.paint()` / `RegionLabelsLayer.paint()` 检查 `self.visible`
  - Tests: 6 tests in `test_paleo_layer_visibility.py`

- **Task 22a.3 (🔴 P0) - HeaderToolButton 全部 20 个按钮无响应** ✅:
  - `app.py:_update_header_and_footer()` 创建 `HeaderToolButton(t)` 后从未连接 `clicked`
  - 修复: 添加 `tool_key` attr 到 `HeaderToolButton`, `_on_header_tool` dispatch method 到 `MainWindow`, 连接 `.clicked` 到 dispatch
  - Tests: 4 tests in `test_header_tool_buttons.py`

- **Task 22a.4 (🔴 P0) - MapPage 6 个死控件修复** ✅:
  - 3 个 chip (全部/已解释/含气): 无 `toggled` 连接 → 修复: 连接到 well list 过滤器
  - 2 个 layer checkbox (井位标记/坐标网格): 无 `stateChanged` → 修复: 添加 `visible` toggle 到 `MapLayer` base
  - 1 个 ruler button "📏": 无 `clicked` → 修复: 隐藏按钮 (无后端)
  - Tests: 8 tests in `test_map_page_dead_controls.py`

#### Phase 22b (🟡 High) ✅ DONE — 2026-06-02

- **Task 22b.1 (🟡 P1) - ToolsPage 4 个对话框后端实现** ✅:
  - **LASCurveResamplerDialog**: 添加 `_do_resample(path, step)` → lasio 加载+np.interp 重采样
  - **DeviationTVDDialog**: `_compute_min_curvature(rows)` → 完整最小曲率法 (TVD/X/Y)
  - **XMLCoordsConverterDialog**: 添加 `_do_convert(src, dst, coords)` → pyproj 坐标转换
  - **TopsCompletionDialog**: 添加 `_do_interpolate(tops, method)` → 线性插值
  - **CalamineCompilerDialog**: 添加 `_do_compile(expr)` → 地质公式语法校验
  - Tests: 11 tests in `test_tools_dialog_backends.py`

- **Task 22b.2 (🟡 P1) - SettingsPage 信号无监听者修复** ✅:
  - `theme_changed` 发出但零监听者 → MainWindow 连接 `_on_theme_preference`
  - `cache_cleared` 发出但零监听者 → MainWindow 连接 `_on_cache_cleared` 更新 status bar
  - Tests: 5 tests in `test_settings_signals.py`

- **Task 22b.3 (🟡 P1) - DataPage 导入/重命名/删除按钮** ✅:
  - "导入数据" button: 连接 `_on_import_data` → 多格式文件对话框
  - 导入 Excel/LAS/SEGY: `_import_file` → 连接实际 loader
  - 重命名 button: 添加 `_on_rename_well` 用 `QInputDialog`
  - 删除 button: 添加 `_on_delete_well` 带确认对话框
  - DataCache: 添加 `rename_well()`, `remove_well()`, `put_file()`
  - Tests: 4 tests in `test_data_page_buttons.py`

- **Task 22b.4 (🟡 P1) - PaleoMap fit 按钮修复** ✅:
  - Fit 按钮改用 `fit_viewport_to_data()` 替代 `set_zoom(1.0)`
  - Tests: 2 tests in `test_paleo_map_fit.py`

- **Task 22b.5 (🟡 P1) - CrossWell TWT 域切换 + 缺失 UI** ✅:
  - Worker progress 信号连接到 progress overlay → `_on_worker_progress`
  - Tests: 2 tests in `test_cross_well_ui.py`

#### Phase 22c (🟢 Medium) ✅ DONE — 2026-06-02

- **Task 22c.1 (🟢 P2) - WellLogPage QThread 泄漏 + 排序 bug**:
  - 快速切换井时 `_load_thread` 重新赋值无清理 → 添加 quit+wait
  - AI 预测 `_thread` 同样泄漏
  - Track 拖拽排序仅视觉生效 (`_update_tracks` 使用 `_all_tracks` 顺序)
  - `_tracks_btn` checked 状态与控制面板不同步
  - `_on_prediction_error` 未重新启用 combo

- **Task 22c.2 (🟢 P2) - PlotsPage power slider 初始状态 + 清理**:
  - power_slider 在非 IDW 方法下初始启用 (默认 SciPy Linear)
  - 9 个未使用导入
  - `contourpy` 缺失于 pyproject.toml (matplotlib 传递依赖掩盖)

- **Task 22c.3 (🟢 P2) - 孤立代码清理**:
  - `CrossWellScenePage`: 类从未实例化 → 连接或删除 `scene_page.py`
  - `CalamineCompilerDialog`: 类从未实例化 → 连接或删除
  - `interval_clicked` signal on WellLogCanvas: 声明但从未 emit → 删除或实现
  - `laolong1_config` / `config` variable in WellLogPage: 解包后未使用

- **Task 22c.4 (🟢 P2) - 小修复**:
  - MapPage `well_hovered` signal 未连接 → 连接到 status bar
  - `status_dot` 始终绿色 → 连接真实健康信号或移除
  - `version_label` 硬编码 "v0.8.0" → 读取 package `__version__`
  - WellLog `interval_clicked` signal 从未 emit → 删除声明

- **Acceptance Criteria**:
  - 所有 HeaderToolButton 要么工作要么移除 (零死控件)
  - PlotsPage SVG/PDF 导出不崩溃
  - PaleoMapPage 图层开关实际切换可见性
  - 4 个 ToolsPage 对话框执行真实操作
  - SettingsPage 主题切换加载 QSS 文件
  - DataPage 重命名/删除操作真实修改数据
  - WellLogPage 快速切换井不泄漏 QThread
  - 所有新功能有 TDD 测试覆盖

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
- 723 tests passed, 4 skipped — full suite green
- cross-well 依赖 well-tie（纯 NumPy，零 Qt）
- Phase 11.9 shipped — microfacies CNPC colors and evaporite SVG added
- Phase 12a, 14, 15 fully completed and committed under strict TDD
- 下一步动作：等待用户新需求反馈

## Errors Encountered
| Error | Phase | Attempt | Resolution |
|-------|-------|---------|------------|
| ValueError: Missing coordinate keys | 14 | 1 | 修复了 dict 和 object 属性中 `0.0` 坐标值被 Python `or` 隐式转换为 Falsy 并触发错误 fallback 的 bug，改用显式 `is not None` 进行过滤。 |

