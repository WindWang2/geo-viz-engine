# Findings & Decisions — GeoViz Engine (All Phases)

## Project Architecture
- 单进程 PySide6 桌面应用，6 个独立 pip-installable 包
- 无 IPC、无 HTTP、无 token auth — 纯 Python 函数调用
- 数据层：Pydantic v2 models + pandas/numpy + Rust Calamine 解析加速

## Seismic Attribute System (Phase 6-7)

### Tier 1 — 已实现 ✅
- Envelope / Instantaneous Amplitude — Hilbert transform
- Instantaneous Phase — angle of analytic signal
- Instantaneous Frequency — gradient of unwrapped phase / 2π
- RMS Amplitude — uniform_filter1d windowed RMS
- Sweetness — envelope / sqrt(freq)
- Relative Acoustic Impedance — cumsum

### Tier 2 — 部分实现 ✅
- Spectral Decomposition (STFT) ✅ — scipy.signal.stft bandpass filter bank
- RGB Attribute Fusion ✅ — fuse_rgb + render_rgba (ProfileVD)
- Attribute Crossplot ✅ — QPainter scatter dialog (freq vs envelope)
- Coherence (C3 eigenstructure) ❌ — 3D 邻域分析，eigenvalue 分解

### Tier 3 — 未实现
- Curvature（需先算 dip/azimuth）
- 3D 属性体渲染（需扩展 Renderer3D 双体支持）

### STFT Implementation Details
- `nperseg = min(64, data.shape[axis])`，`noverlap = nperseg // 2`
- Zxx shape: `(n_traces, n_freqs, n_time_frames)` — mask on axis 1
- `scipy.signal.istft` 不支持 `axis` 参数（与 stft 不同）
- `moveaxis` 是 `np.moveaxis()` 模块函数，不是 ndarray 方法

## Well-Seismic Tie (Phase 8)

### 核心库 (geoviz-well-tie)
- Ricker + Ormsby 子波生成（纯 NumPy，零额外依赖）
- 反射系数：sonic × density → impedance → reflectivity
- 合成地震记录：reflectivity ⊛ wavelet
- WellTieCalibration: T-D 转换, sonic 积分, 深度→TWT 重采样
- `generate_synthetic_twt()`: unit-safe wrapper (dt_ms → dt_seconds)
- `resample_to_seismic_grid()`: standalone function for seismic grid alignment
- `auto_tie_with_quality()`: numpy.correlate cross-correlation, returns (shift_samples, CC)

### 关键技术发现

#### 1. 反射系数 N-1 对齐问题
- Reflectivity from N samples produces N-1 values
- Must use midpoint depths `(depths[:-1] + depths[1:]) / 2` for calibration
- Building a separate `WellTieCalibration` at midpoint depths is the cleanest approach
- Pipeline: sonic → RC (N-1) → mid_cal.resample_to_twt() → wavelet convolve

#### 2. BinGridGeometry 方位角约定
- `il_azimuth_deg`: clockwise from north (地理方位角)
- Inline 方向 = azimuth 方向; Crossline = perpendicular
- 公式: `il = (-dx*sin + dy*cos)/spacing`, `xl = (dx*cos + dy*sin)/spacing`
- When azimuth=0 (north): dy → iline, dx → crossline
- Azimuth=90 (east): dx → iline, dy → crossline (sign flip)

#### 3. QPainter Overlay on ProfileVD
- `set_synthetic_overlay(h_position, twt, values)` → `_draw_synthetic_overlay(painter, img_rect)`
- Uses `_seismic_to_pixel()` for correct twt → y positioning
- Wiggle trace via `QPolygonF` + `drawPolyline()` — single argument form (PySide6)
- Overlay drawn between axes and crosshair in paintEvent
- `set_clip_percentile` method body was lost during insertion — must preserve existing code when editing

#### 4. SeismicView Panel Integration Pattern
- Lazy creation: `_well_tie_panel = None` initially, created on first toggle
- `_well_tie_btn` is checkable QPushButton in toolbar
- Panel inserted into h_layout at position 0 (left side)
- Toggle off → `hide()`, toggle on → `show()` — same object persists
- Panel width fixed at 280px

#### 5. Auto-tie Sign Convention
- `auto_tie()` returns shift in samples
- Positive shift = synthetic arrives late (should be shifted down in time)
- `np.correlate(seismic, synthetic, mode="full")` with `lag = peak_idx - (n-1)`
- CC coefficient from `np.corrcoef` at the aligned position

### WellTiePanel Widget
- Wavelet combo: Ricker (default) / Ormsby with f1-f4 sliders
- Peak frequency slider: 5–80 Hz, default 25 Hz
- Auto-tie button: runs cross-correlation, updates CC and shift readout
- Export button: CSV with depth_m, twt_ms columns
- Signal: `synthetic_changed(twt_array, values_array)` for overlay wiring

## Seismic Package Extensibility

| 组件 | 扩展性 | 评估 |
|------|--------|------|
| `SeismicLoader` | ✅ 好 | 纯数据读取，输出 numpy 数组，可直接喂属性函数 |
| `attributes.py` | ✅ 好 | 9 个属性函数 + fuse_rgb，结构清晰 |
| `ProfileVD` | ✅ 好 | 支持 render (colormap) + render_rgba (RGBA bypass) + synthetic overlay |
| `ColormapManager` | ✅ 好 | seismic/gray/jet/hsv/viridis/phase_wheel |
| `Renderer3D` | ❌ 受限 | 单体单色标，不支持属性体/叠加显示 |
| `SeismicCache` | ⚠️ 需扩展 | cache key 不含属性类型 |
| `SeismicView` 工具栏 | ✅ 好 | 8 属性选项 + RGB融合 + 交叉图 + 井震标定面板 |

## A7 Dedup: CheckshotTable → WellTieCalibration

### Problem
`geoviz-cross-well/seismic_tie.py` 的 `CheckshotTable` 和 `geoviz-well-tie/calibration.py` 的 `WellTieCalibration` 有重复的 T-D 插值逻辑（`np.interp`）。

### Solution
- `CheckshotTable` (dataclass) 通过 `__post_init__` 构建 `WellTieCalibration` 实例
- `interpolate_twt` / `interpolate_depth` 委托给 `calibration.depth_to_twt` / `twt_to_depth`
- 副作用：自动获得 array 输入支持（之前只支持 scalar）
- `calibration` property 暴露底层 `WellTieCalibration`，cross-well 用户可访问 `resample_to_twt` 等高级功能

### Dependency Direction
```
geoviz-cross-well → geoviz-well-tie (pure NumPy, zero Qt) ✅ 合理
```

## Phase 2 Legacy: DTW Ghost Picks + Dual-Axis

### DTW Ghost Pick Accept
- Left-click on DTW ghost pick → `_pick_at()` finds it → `accept_dtw_pick()` changes source to "manual"
- Right-click on DTW ghost pick → `reject_dtw_pick()` deletes it (already worked)
- The `_pick_at()` method searches picks by position proximity (5.0 depth tolerance)
- Placement: checked before `_canvas_at()` so DTW picks anywhere on the canvas are caught first

### TWT Dual-Axis Rendering
- `PickingOverlay._paint_twt_axis()` renders TWT labels when `_depth_domain == "TWT"` and `_seismic_tie` loaded
- Uses `seismic_tie.table_for_well(well).calibration.depth_to_twt()` for batch array conversion
- 10 evenly spaced ticks from top to bottom of leftmost canvas
- Labels rendered at canvas_left - 42 px, header "TWT(ms)" above
- Only renders when both conditions met (domain=TWT AND seismic_tie has data)

## Resources
- SEG Wiki 瞬时属性：https://wiki.seg.org/wiki/Instantaneous_attributes_-_book
- SEG Wiki 甜点属性：https://wiki.seg.org/wiki/Sweetness
- SEG Wiki 相干属性：https://wiki.seg.org/wiki/Coherence

## Phase 11.6 — 用户测试发现的缺陷（2026-05-31）

### 1. MapCanvas 点击井无响应（11.6-A 已修）
- **根因**：`WellsLayer.paint()` 把屏幕坐标写入 `_screen_positions`，但 `LayerPixmapCache._rerender()` 使用 **2× 大小的 buffer viewport**（`buf_w/buf_h = vp.width*2`）来绘制 layer
- `hit_test` 优先复用 `_screen_positions` → 坐标系错位 → 命中永远失败
- 修复：`hit_test` 始终用 live viewport 重新投影，忽略 `_screen_positions`
- 教训：**画布缓存（pixmap cache）只能存像素，不能存坐标**；命中检测必须用当前视口现算

### 2. paleo_map 导出 PDF 崩溃（已修 part 1）
- `printer.pageRect(QPrinter.DevicePixel)` 在 PySide6 返回 `QRectF` → `.size()` 是 `QSizeF`
- `QPixmap.scaled()` 不接受 `QSizeF`（PyQt5 时代接受，PySide6 严格类型）
- 修复：`page_rect.toRect()` 强转为 `QRect`
- 仍待办（11.6-C）：导出还缺图名/比例尺/指南针/图例，需复用 Phase 10 `export_professional_figure`

### 3. PySide6 严格类型对照 PyQt5
- `QRectF.size()` → `QSizeF`（不可隐式转 `QSize`）
- `QPainter.drawPolyline(QPointF, QPointF, ...)` → 只接受 `QPolygonF` 单参数
- 这类问题需要在 PR 时主动 grep 检查重载签名

### 4. paleo_map chrome layers 消失（11.6-B 已修）
- **根因（与 11.6-A 同源）**：`LayerPixmapCache._rerender()` 用 **2× buffer viewport** 渲染 layer (`buf_w = vp.width*2`, `buf_h = vp.height*2`)，blit 时只取中心一块回真实 viewport
- chrome layer（北针/比例尺/图例/标题）锚定 `viewport.width - 46`、`viewport.height - 24` 等边缘坐标 → 在 buf_vp 下变成 `2*vp.width - 46`，blit 后落在屏幕外 → 完全不可见
- **修复**：
  - `PaleoLayer.is_chrome: bool = False` 基类标志
  - 4 个 chrome 类（TitleLayer / NorthArrowLayer / ScaleBarLayer / LegendLayer）`is_chrome = True`
  - `PaleoMapCanvas._rebuild_layer_caches` 为 chrome layer 存 `None`
  - `paintEvent` 中 `cache is None` 直接调 `layer.paint(painter, self._viewport)`
- **回归测试**：`test_chrome_layers_bypass_pixmap_cache` 锁定 chrome → None / 数据层 → cache 的映射
- **教训（与 11.6-A 互补）**：
  - 11.6-A 教训："命中检测不能信缓存坐标"
  - 11.6-B 教训："viewport-anchored 渲染不能走缓存"
  - 通用结论：**LayerPixmapCache 的 2× buffer 模式只适合 world-coord 内容；任何与 viewport 几何强耦合的逻辑都必须 bypass cache**

### 5. paleo_map 导出 PDF 缺出版要素（11.6-C 已修）
- **根因**：page 层 `_export_pdf` 自己 grab pixmap + 居中铺 A4，不带 title / 比例尺 / 指南针 / 图例 / 边框 — 出来的 PDF 在用户眼里就是"空白"或"残缺"
- **修复**：`src/pages/paleo_map/page.py` 的 `_export_pdf` / `_export_svg` / `_export_png` 全部委托给 `geoviz_paleo_map.export_professional.export_professional_figure`（Phase 10 产出）
- title 由 `_figure_title()` 生成：`{current_period} 古地理相图`
- **教训**：独立 package 已经把 publishing 能力做好了；page 层重复实现导出 = 引入 bug + 缺失 frame；scan 项目中其他 page 是否有类似低质量 export

### 6. 待调查（pending）
- 11.6-D 缩放后文字模糊：缓存 pixmap 在 zoom 时被放大插值，labels layer 也需在 zoom 改变时 invalidate
- 11.6-E 连井慢：DTW 是 O(N²) 全矩阵；先 profile 找瓶颈
- ~~11.6-F DTW 位置不对~~：✅ 已修，见下方 11.6-F 章节
- 11.6-G 拾取 UX：缺操作提示

### 11.6-F DTW 位置错位 — 双重根因（已修）

**根因 1：引擎参考点硬编码**
- `dtw_engine.py:74` `ref_idx = n // 2` — 无论用户拾取在哪个深度，DTW 永远从参考曲线中点找匹配
- 这是 5 月初 Phase 5 写 DTW 时的占位逻辑，从未被替换
- 修复：`correlate()` 新增 `ref_depth: float | None = None`；`ref_idx = argmin(abs(ref_depths - ref_depth))`；多对一映射用 `np.median(target_indices)` 收敛

**根因 2：引擎是孤儿（更严重）**
- `CrossWellWidget.auto_link()`（在 geoviz-well-log 包内）只做 formation-name 字符串匹配 — DTW 引擎从未被任何生产代码调用
- 7 个 DTW 单元测试全绿，但实际用户点"自动连井"按钮 → name match 失败 → 静默无结果，DTW 完全没机会跑
- 修复：`CrossWellCanvas.propagate_pick_via_dtw(ref_well, ref_depth, formation, band_radius=None)` 真正调 DTW 产生 ghost picks
- `_extract_curve()` 辅助方法：优先取 GR/SP/RT，否则取首条可用曲线
- **副作用 fix**：`canvas.py` 一直在 `_paint_twt_axis` 里用 `np.linspace` 但没 import numpy — latent bug 一起修

**测试覆盖陷阱**
- 3 个新测试位于 `packages/geoviz_cross_well/tests/`，但 `pyproject.toml` `testpaths = ["tests"]` 只扫根目录
- `pytest` 全局：674 passed 不变（DTW 包级新测试没纳入 headline）
- `pytest packages/geoviz_cross_well/tests/` 包级：46 passed（+3）
- **本次决策**：保持现状，不扩 testpaths 一次性引入全部包级测试 — 那会让 headline 数字突涨且未审计；留作 11.6 收尾的独立讨论项

**未完成（已记 task #29 备忘）**
- `propagate_pick_via_dtw` 是 producer，**尚未接入 UI** — 用户点连井按钮仍走 name-match
- 需要 `src/pages/cross_well/` 层在 name-match 失败时回退调用 producer
- 留给 11.6-G（手动拾取 UX 改造）一起做，或单开 follow-up

**教训**
- **测试覆盖率 ≠ 生产被调用**：DTW 有 7 个单测全绿但生产路径调用数=0；金字塔必须有"集成层"才能 catch orphan engine
- **"接入"是双向工作**：fix engine（引擎正确）+ wire producer（生产路径调用）+ wire UI（用户能触发）— 缺一不可
- **占位逻辑要标注**：`n//2` 这种"先跑通"的逻辑必须留 TODO 或 raise NotImplementedError，否则 5 个月后没人记得它是占位

---
*Update after every 2 view/browser/search operations*

### 7. 地震 toolbar 拆成 2 行（11.6-H 已修）
- **根因**：`_build_toolbar` 把 ~30 个控件全塞进一个 `QToolBar`，1280px 窗宽下末端 IL/XL/T 滑块和井震标定按钮被裁
- **修复**：`_build_toolbar` 返回 `QWidget` 容器（`QVBoxLayout` spacing=0），内含 `_toolbar_row1` 和 `_toolbar_row2` 两个 `QToolBar`
  - Row 1（主操作）：加载/Demo/层位/层位管理 ‖ 拾取/清除/导出/标注 ‖ 切片信息+读出 ‖ 井震标定
  - Row 2（视图与属性）：3D模式/透明度/剖面/显示/色标 ‖ 裁剪/属性/RGB/交叉图 ‖ IL/XL/T 滑块
- **教训**：
  - `QToolBar` 自带 separator/spacing 行为，多行 toolbar 用多个 `QToolBar` 实例堆 `QVBoxLayout` 比手撸 `QHBoxLayout` 更原生
  - 控件创建必须在 `bar.addWidget` 之前完成（之前 `_attr_combo` / `crossplot_btn` / RGB 控件创建被嵌在 add 中间，refactor 时容易漏掉 — 这次差点 NameError）


### 8. 连井手动拾取 UX 改造（11.6-G 已修）

**问题清单（用户测试反馈）**
- 工具栏 7 个按钮无 tooltip — 用户不知道每个按钮做什么
- 拾取模式开启后状态栏只显示「3 口井」无操作提示 — 新手 30 秒内完不成一次拾取
- 11.6-F 的 `propagate_pick_via_dtw` producer 没有 UI 入口 — 用户即便手动拾了点也没法触发 DTW
- 手动拾取/撤销后状态栏不刷新 — 用户不知道是否操作生效

**修复（src/pages/cross_well/page.py）**
1. 全工具栏添加 tooltip — 7 个按钮全部说清楚做什么 + 怎么用
2. 新增「DTW 传播」按钮：把 11.6-F 留的 producer 接入 UI
   - 收集所有 `source == "manual"` 的 pick
   - 每个 pick 拿一个 `connected_wells()` 的井作 anchor，调 `propagate_pick_via_dtw`
   - 三分支 QMessageBox.information：无井 / 无 manual pick / 成功传播 → 用户始终拿到清晰反馈
3. `_update_status` 在 pick mode 下渲染完整快捷键 hint：
   `「拾取模式: 左键添加 · Shift+左键连接 · 右键删除 · Ctrl+Z 撤销 · Esc 退出」`
4. `self._canvas.picks_model.picks_changed.connect(self._update_status)` — 拾取/撤销自动刷新

**陷阱：HorizonPick API 误用**
- 初版写 `for well in pick.depths_by_well:` — 属性不存在
- `HorizonPick` 实际是 `well_depths: list[tuple[str, float|None]]` + 方法 `connected_wells()` / `depth_for_well(well)` / `set_depth(well, depth)`
- **教训**：跨包消费 dataclass 前先读源码 — 别凭直觉写 `.something_by_X` / `.something_dict`

**测试覆盖（tests/test_cross_well_page_dtw.py — 新建）**
- 按钮 + tooltip / 三分支 message box / 端到端 DTW 产生 ghost / pick 模式 hint / picks_changed 联动 = 6 个用例
- 全套件：680 passed, 4 skipped（+6 新）

**双 page 模块情况确认**
- `src/pages/cross_well/page.py` ← `__init__.py` ← `src/app.py` 真实用的就是这个
- `src/pages/cross_well/scene_page.py` 是早期实验代码 — 只被 `tests/test_cross_well_page.py` 引用，**未被 app 加载**
- **教训**：双 page 模块共存是历史包袱 — 未来 cleanup 时考虑删 `scene_page.py`

**11.6 整体收尾状态**
- ✅ A/B/C/D/F/G/H = 7/8 已修
- ⏳ E（自动连井慢）= 1/8 剩余 P1


### 9. 古地理图缩放后文字模糊（11.6-D 已修）

**根因：LayerPixmapCache 不感知 devicePixelRatio**
- `paint_scheduler.py:_rerender()` 用 `QPixmap(buf_w, buf_h)` 分配 pixmap，从未调 `setDevicePixelRatio`
- HiDPI 屏（DPR=2/2.5/3）上，cache pixmap 物理像素 = 逻辑像素 → 文本/线在 cache 内以低像素密度渲染
- blit 时 painter 把 cache pixmap 当作 1× 资源拉伸到屏幕，叠加 Qt 默认双线性插值 → 文字模糊
- chrome layers（title/north_arrow/scale_bar/legend）经 11.6-B 的 `is_chrome=True` 已 bypass cache，所以它们没事 — 模糊只发生在 facies polygons 边界 + region labels 上

**修复**：`packages/geoviz_paleo_map/paint_scheduler.py`
1. `paint(painter, viewport)` 改为从 `painter.device().devicePixelRatioF()` 取 DPR
2. `_rerender(vp, dpr)` 分配 `QPixmap(int(buf_w*dpr), int(buf_h*dpr))` 然后 `setDevicePixelRatio(dpr)` — 这样 layer 绘制时仍用逻辑坐标，Qt 内部按物理像素渲染
3. `_needs_rerender(vp, dpr)` 新增 DPR 变化检测（窗口拖到不同 DPI 显示器时触发 rerender）
4. `_blit` 不动 — `drawPixmap` 已自动按 `setDevicePixelRatio` 处理源/目标缩放

**教训**：
- **PySide6 HiDPI 自动缩放 ≠ 自动管 QPixmap**：QPainter 直接画窗口时 Qt 帮你做 DPR；但你自己创建的 offscreen QPixmap 必须手动 `setDevicePixelRatio` 否则就是 1×
- **chrome bypass 与 DPR 修复互补**：11.6-B 把 viewport-anchored 内容拿出 cache（解决位置），11.6-D 把 cache 本身打通 DPR（解决清晰度）— LayerPixmapCache 现在对 world-coord 数据 + HiDPI 都正确
- **测试覆盖盲点**：测试默认在 DPR=1 环境跑，HiDPI 缺陷只在真机能复现 — 新增 `test_pixmap_dpr_matches_painter_device` 锁定 pixmap.devicePixelRatio() == painter.device DPR，未来回归会立即抓到

**测试覆盖**（tests/test_paint_scheduler.py — 新增 2 个）
- `test_pixmap_dpr_matches_painter_device`：pixmap.devicePixelRatio() == painter 的 DPR；物理像素 = 逻辑像素 × dpr
- `test_dpr_change_triggers_rerender`：DPR 从 1.0 变到 2.0 → `_needs_rerender` 返回 True
- 全套件：682 passed, 4 skipped（+2 新）


---
*Update after every 2 view/browser/search operations*


---
*Update after every 2 view/browser/search operations*
