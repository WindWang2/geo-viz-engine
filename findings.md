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


### 10. 自动连井 DTW 性能（11.6-E 已修）

**根因：纯 Python 双循环 + 每格 list/tuple-min + 全 O(n²) 默认带宽**
- `dtw_engine.py:correlate()` 原实现对每格做 `prev=[]; if i>0: prev.append(...); ... cost[i,j] = dist[i,j] + min(prev)`
- 每格构造 0–3 元 list + `min(prev)` + 3 次 numpy 标量索引 → CPython 解释开销在 1k×1k = 1M 格上累计 ~2s
- `band_radius=None` 默认 = `max(n,m)` → 全 O(n²)；典型 1000-sample 测井 1.97s/次 × 5 井 × 4 传播 ≈ 40s

**修复（packages/geoviz_cross_well/dtw_engine.py）**
1. **按行向量化**：对每行 i，一次性算 `vbase = np.minimum(prev_row, diag) + row_dist`（vertical+diag 不依赖行内顺序），然后行内 horizontal 仍串行扫一遍（因为 cost[i,j] 依赖 cost[i,j-1]）。关键是去掉 list/tuple 开销，纯标量算术
2. **限带默认 `band_radius = max(20, max(n,m)//4)`**：保留 25% 宽容 warp 区间，对地质 well log 完全够用（实测 shift=5% 的 case suggested_depth 误差 < 1 个采样间隔）
3. **`progress_callback(current, total)` 参数**：每 5% 行回调一次，UI 接 `FloatingProgressOverlay.update_progress`

**修复（canvas.py）**：`propagate_pick_via_dtw(...progress_callback=...)` 在井级别回调（每跑完一口 target 井触发一次）

**修复（src/pages/cross_well/page.py）**：`_on_dtw_propagate` 计算 `total_steps = picks × (wells-1)`，FloatingProgressOverlay 显示「DTW 传播中... (3/12)」，每步 `QApplication.processEvents()` 保持 UI 响应

**基准（n=samples per curve）**
| n | 修前默认 | 修后默认（限带）| 修后强制 full band | 加速比 |
|---|---------|----------------|--------------------|--------|
| 500 | 0.44s | 0.075s | 0.16s | 5.9× |
| 1000 | 1.97s | 0.28s | 0.60s | 7.0× |
| 2000 | 7.09s | 1.06s | 2.41s | 6.7× |

5 口井 × 4 次传播 ≈ 1.1s（修前 ≈ 40s），远低于 acceptance 5s 门槛。

**教训**：
- **numpy 优化不一定是「彻底向量化」**：DTW 的内层 horizontal 步骤天然串行（cost[i,j] = f(cost[i,j-1])），强行用 cumulative tricks 反而错。真正赚的是消除 Python list/tuple/标量 boxing
- **限带不是性能 hack 是正确性问题**：测井数据 sample 间隔通常 0.125m，1000 sample = 125m；DTW 全带宽允许 1000m 错位，但地质上根本不存在 — 限到 25% 既快又防伪匹配
- **进度条不只是 UX**：DTW 长时间无反馈会让用户怀疑死锁去重启 → 哪怕只跑 1s 也要给进度，QApplication.processEvents() 让用户能看到「正在动」
- **回归测试该锁住性能**：新增 `test_dtw_perf_under_one_second_for_1k_samples` —— 未来谁不小心把限带逻辑改坏会立即抓到

**测试覆盖**（packages/geoviz_cross_well/tests/test_dtw_engine.py — 新增 3 个）
- `test_dtw_perf_under_one_second_for_1k_samples`：n=1000 必须 < 1s
- `test_progress_callback_receives_monotonic_updates`：(cur, total) 单调递增、最终 == n
- `test_vectorized_dtw_matches_reference_implementation`：与朴素双循环参考实现对比 suggested_depth 一致
- 全套件：682 passed, 4 skipped（总收集数 686，包含新增 3 个 DTW 用例）

**11.6 整体收尾状态**
- ✅ A/B/C/D/E/F/G/H = 8/8 全修
- Phase 11.6 闭环完成


## 11.7-A — LayerPixmapCache 不感知 viewport 尺寸变化（2026-05-31）

**用户报告**："古地理图标注和对象完全偏离"。自检截图后发现：title / north arrow / scale bar / legend 在画布上分布正常，但 facies polygons / wells / region labels 全部挤压在画布左上角，与 chrome 完全错位。

**根因**：`LayerPixmapCache._needs_rerender` 只检查 `dirty` / `dpr` / `scale` / pan 距离，**没检查 viewport 宽高变化**。`PaleoMapCanvas` 默认 widget 大小是 640×480，构造时执行的首次 paint 让 cache 按 buf=(1280, 960) 渲染并写入 `_vp_scale`。随后 `resize(1400, 900)` + `show()` 把 viewport 改成 1400×900，但 cache 视参数无变化（scale 同 zoom）→ 直接走 `_blit` 路径。`_blit` 从老 pixmap 读取 `(vp.width, vp.height) = (1400, 900)` 矩形，但 pixmap 逻辑尺寸只有 (1280, 960)，超出部分透明 → 画布左上角看到一小块数据，右下大片空白。

为什么 chrome 没事：11.6-B 改造后 title / north_arrow / scale_bar / legend 都设 `is_chrome=True`，直接 `paint(painter, viewport)` 不走 cache → 每帧用真实 viewport 重画 → 正常分布。这就是"标注居中、数据偏移"的视觉效果。

**修复**（`packages/geoviz_paleo_map/geoviz_paleo_map/paint_scheduler.py`）：

```python
class LayerPixmapCache:
    def __init__(self, layer):
        ...
        self._vp_width: int = 0
        self._vp_height: int = 0

    def _needs_rerender(self, vp, dpr):
        ...
        # Viewport resize invalidates the cached pixmap: the cache was rendered
        # for a (buf_w, buf_h) sized buffer matched to the old vp dimensions,
        # and _blit reads a (vp.width, vp.height) rect from it. If the live
        # viewport grew, the rect runs off the cached pixmap and content
        # collapses into the upper-left of the canvas.
        if vp.width > self._vp_width or vp.height > self._vp_height:
            return True
        ...

    def _rerender(self, vp, dpr):
        ...
        self._vp_width = vp.width
        self._vp_height = vp.height
```

**回归测试**：`tests/test_paint_scheduler.py::TestLayerPixmapCache::test_viewport_grow_triggers_rerender` — paint vp_small(400×300) 后再 paint vp_large(1200×800)，断言 render_count == 2。stash-test-pop 验证：移除修复 → 测试失败 `assert 1 == 2`，恢复 → 通过。

**视觉验证**：`/tmp/paleo_shot.png` 重生成确认 facies polygons / wells / region labels / chrome 全部正确分布于 1400×900 画布上。

**教训**：
- **复合缓存层必须把所有维度都纳入失效判定**：dirty/dpr/scale 都查了，唯独漏了 width/height，因为窗口 resize 不改 scale → 假设"只有 dirty/zoom 会动"是错的
- **chrome bypass 既是优点也是 trap**：它让 chrome 不受 cache bug 影响 → 视觉错位只表现在数据层 → 第一直觉是"投影/坐标算错了"而非"缓存没失效"。下次类似 bug，先检查 cache invalidation 再查 transform
- **测试要锁住 invariant 而非"已知 case"**：原 cache 测试只测了 dirty/zoom/dpr 各自触发 rerender，没测 viewport 维度。补 `test_viewport_grow_triggers_rerender` 是把"任何影响 buffer 几何的输入都必须 invalidate"这条 invariant 显性化

---

## 11.7-B 根因分析：缩放/平移时标签与多边形分离

**症状**：用户报"古地理图标注和显示分离"。澄清后：缩放/平移过程中，`RegionLabelsLayer` 的文字与对应 `FaciesPolygonsLayer` 的几何对象错位 — 多边形停在旧位置，label 漂到新位置。

**根因**：`packages/geoviz_paleo_map/geoviz_paleo_map/screen_path_cache.py` 的 `ScreenPathCache.get_or_build` 缓存键只含 `(zoom_key, feature_id)`，但 `_transform_path` 把 `vp.center_world` 烤进 screen path：

```python
def _transform_path(self, world_path, vp):
    s = vp.scale
    cx, cy = vp.center_world   # 烤进 transform
    ...
    t.translate(ox, oy); t.scale(s, -s); t.translate(-cx, -cy)
    return world_path * t
```

平移（center 改变、zoom 不变）时 `cache_key` 命中旧 entry → `FaciesPolygonsLayer` 拿到用旧 center 烤好的 path，画在旧屏幕坐标；而 `RegionLabelsLayer.paint` 每帧 `viewport.world_to_screen(*item.centroid_world)` 实时算 → label 浮到新 center 对应的位置。二者错位 = "标注和显示分离"。

**修复**：让 `ScreenPathCache` 把 center 纳入失效判定。维护 `_zoom_center: dict[zoom_key, (lng, lat)]`，`get_or_build` 检测到该 zoom 的记录 center ≠ 当前 viewport center 时，丢掉该 zoom 的所有条目再重建。`_evict` 同步收缩 `_zoom_center` 防止内存泄漏。

```python
cached_center = self._zoom_center.get(zoom_key)
center = viewport.center_world
if cached_center is not None and cached_center != center:
    self._cache = {k: v for k, v in self._cache.items() if k[0] != zoom_key}
...
self._zoom_center[zoom_key] = center
```

**回归测试**：`tests/test_paint_scheduler.py::TestScreenPathCache::test_pan_invalidates_screen_path` — 同 zoom 下 vp1(center_lng=5)→vp2(center_lng=8)，断言两次 `get_or_build` 返回 path 的 boundingRect.center().x() 不同。修复前 FAIL（两边都是 200.0），修复后 PASS；全套 684 passed。

**教训**：
- **多层 cache 的失效条件必须对齐**：`LayerPixmapCache`（带 50% margin pan tolerance）和 `ScreenPathCache`（按 zoom）的失效粒度不一致 → 一层"不 rerender" 但另一层早 stale → 上层 layer 拿到 stale 数据再画进新 buffer。Cache 链应保证"上游命中 ⊆ 下游命中"
- **transform 中烤进的参数都属于 cache key 的一部分**：`_transform_path` 烤了 scale + center + viewport_size，但 cache key 只反映 scale → 任何烤进 transform 的参数变化都必须能让 key miss。是一条 code-review invariant
- **"X 与 Y 错位"通常意味着 X / Y 走了不同更新通道**：label live transform vs polygon cached transform — 先列两边数据流再查缓存

---

## 11.7-C 根因分析：对比模式下两边各画一套 chrome

**症状**：用户报"不要区分区域，古地理图的图例指南针和比例尺都在一个画布上"。澄清：对比模式（点"对比"按钮并排显示两个时期）下，左右两个 `PaleoMapCanvas` 各自独立绘制 Title / NorthArrow / ScaleBar / Legend → 屏幕上有两个图例、两个指南针、两个比例尺，且每个只反映自己一侧的 facies，无法统一阅读。

**根因**：chrome 是 canvas 的内嵌 layer，由 `PaleoMapCanvas` 在 4 个 `_layers` 构建点（`__init__` / `load_features` / `load_hierarchy` / `_update_active_layers`）固定追加进去。canvas 不知道自己"是否独立呈现"——所以一旦把两个 canvas 并排，chrome 就被双份渲染。Compare 模式逻辑在 `src/pages/paleo_map/page.py::_start_compare`，那里只是把两个 canvas 塞进 QSplitter，没法 retroactively 把 chrome 从 leaf 抽出来。

**修复**：让 chrome 的归属从 leaf 移到 composition root。

1. **canvas 增 `show_chrome: bool = True` 开关**（`packages/geoviz_paleo_map/geoviz_paleo_map/canvas.py`）：在 4 个 `_layers.extend([...])` 调用点统一 `if self._show_chrome:` 包裹 chrome 4 件套。默认 True 保持单画布行为不变；compare 模式构造两个 canvas 都传 `show_chrome=False`。

2. **canvas 暴露内部状态供共享面板订阅**：新增 `facies_names() -> set[str]` 返回当前 LegendLayer 已收集的 facies；新增类信号 `facies_changed = Signal()`，在 `load_features` / `load_hierarchy` 末尾 emit，让外部刷新触发。

3. **新建 `SharedChromePanel`**（`packages/geoviz_paleo_map/geoviz_paleo_map/shared_chrome_panel.py`）：固定宽 200px 的 QWidget，自上而下绘制 north arrow / 合并 legend（A∪B facies）/ scale bar；连接两个 canvas 的 `facies_changed` + `zoom_changed` → `self.update()`。scale bar 用 `canvas_a._viewport.world_bbox()` 计算 km。

4. **page 接入**（`src/pages/paleo_map/page.py::_start_compare`）：弃用 QSplitter，改用 QHBoxLayout host 把 `canvas_a` (stretch=1) / `SharedChromePanel` / `canvas_b` (stretch=1) 三件套塞进 `_compare_host`。`_stop_compare` 拆除 host + 共享面板 + 第二 canvas，重建带默认 chrome 的单 canvas。

**回归测试**：`tests/test_paleo_shared_chrome.py` 6 项 — 默认 chrome 在 / `show_chrome=False` 关 chrome / `facies_names()` 暴露 / SharedChromePanel 合并两侧 facies / canvas 重新 load 后 panel 刷新 / panel.grab() 无错。全部通过；全套 690 passed, 4 skipped。

**教训**：
- **chrome 归 composition root，不归 leaf widget**：第一直觉是"chrome 是图的一部分"→ 放到 canvas 里；但只要可能并排两个实例，chrome 就属于"承载它们的容器"。canvas 应该是"可被多次实例化的内容画板"，副标题/图例/指北针属于宿主页面
- **多实例场景前必先问"哪些 layer 是 per-instance、哪些是 per-composition"**：在加 11.7-C 之前，这条 invariant 隐藏在"只有一个 canvas"的假设里。任何加 compare/split-screen/PiP 类功能时，先把 layer 按"内容 vs chrome"分一次
- **leaf 暴露 signal + 状态查询接口比让 root 直接读私有字段更安全**：`facies_changed` + `facies_names()` 让 SharedChromePanel 不耦合 LegendLayer 内部；后续如果换 chrome 实现也不会破壳

---

## 11.7-C2 根因分析：chrome 占独立列让画布割裂

**症状**：11.7-C 把 SharedChromePanel 作为 `canvas_A | panel | canvas_B` 三件套塞进 QHBoxLayout，panel 占独立 200px 列 → 用户反馈"不要把指南针、图例和显示地理图的区域区分开"。两个 canvas 中间被一条灰白竖条切开，破坏了"一张地图"的整体观感。

**根因**：上一轮把 chrome 从 leaf 抽出来时，只解决了"双份"问题，但没解决"chrome 应该浮在画布上还是占独立区域"。QHBoxLayout 是 layout-managed sibling 关系，panel 必然占据自己的几何区域 → 物理上不可能"叠"在 canvas 上。

**修复**：让 panel 变成 overlay child，而不是 sibling。

1. **`SharedChromePanel` 新增 `overlay: bool = False` 构造参数**：overlay=True 时设 `WA_TranslucentBackground`（背景透明）+ `WA_TransparentForMouseEvents`（不拦截鼠标，让 canvas 的拖动/缩放穿透）。非 overlay 模式保持原行为，兼容现有 6 个测试。

2. **`_start_compare` 不再把 panel 加进 QHBoxLayout**：直接 `parent=self.map_view` 挂到左 canvas 上，QHBoxLayout 只有两个 canvas 各占 50%。新增 `_install_chrome_overlay_positioning()` 包装 `canvas.resizeEvent`，每次 resize 把 panel 移到 canvas 右上角（`width-panel_w-8, 8`）并 `raise_()`。

3. **回归测试** `test_overlay_mode_is_translucent_child`：断言 overlay 模式下 `panel.parent() is canvas_a` + 两个透明属性都已设置。691 passed, 4 skipped。

**教训**：
- **"X 不要占独立区域"≠"X 不存在"**：用户要的是视觉融合，不是删除。先确认"位置/层叠"再考虑"存在性"
- **Qt overlay = parent 关系 + 手动 move/raise_，不靠 layout**：layout-managed 必然占区；overlay 必须脱离 layout
- **overlay 必须配 `WA_TransparentForMouseEvents`**：否则虽然背景透明、视觉上看不见，但 panel 矩形仍然吃事件 → 用户在 panel 覆盖区域里拖动/缩放会失效。是 PySide6 overlay 的常见坑

---

## 11.7-D 根因分析：compare 模式从一开始就是过度设计

**症状**：经过 11.7-C（兄弟列）和 11.7-C2（overlay）两轮迭代后，用户直接说："删除对比这个功能。古地理图这里就一个画布，所有信息都在画布上（图例，指南针，比例尺等等）。"

**根因**：compare 模式不是用户提出的需求。它是我们在 Phase 11.6 时观察到"两个时期可以对比"自作主张加的功能。每一轮反馈都在调整 chrome 的位置——但用户真正想要的是单画布。我们花了 11.7-C + 11.7-C2 两轮工程在改造一个用户从未要的功能。

**修复**：把 compare 模式从代码与测试中整段移除，回归单画布默认。

1. **`PaleoMapCanvas` 退化为单形态**（`packages/geoviz_paleo_map/geoviz_paleo_map/canvas.py`）：移除 `show_chrome` 参数、`facies_changed` 信号、`facies_names()` 方法；4 个 `_layers` 构造点（`__init__` / `load_features` / `load_hierarchy` per-level group / `_update_active_layers`）无条件追加 chrome 八件套（Background + 3 数据层 + 4 chrome 层）。

2. **`shared_chrome_panel.py` 整文件 `git rm`**：上一轮一起补的 `tests/test_paleo_shared_chrome.py`（7 测试）同步 `git rm`。

3. **`src/pages/paleo_map/page.py` 清理 compare 残骸**：移除 `from geoviz_paleo_map.shared_chrome_panel import SharedChromePanel`、`self._compare_mode = False`、`self._compare_btn` 工具栏按钮（含 `tb_layout.addWidget`）、`_on_period_changed` 中的 `if self._compare_mode...` 分支、四个方法 `_toggle_compare/_start_compare/_install_chrome_overlay_positioning/_stop_compare`。

**回归测试**：684 passed, 4 skipped（从 691 → 684 = -7 = 删掉的 shared chrome 测试数）。`grep -rn "shared_chrome\|SharedChromePanel\|show_chrome\|facies_changed\|_compare\|map_view_b"` 在 `src/ tests/ packages/` 全为空。

**教训**：
- **用户没要的功能就是债**：11.7-C/C2 解决的问题（双份 chrome、chrome 占列）本身只在 compare 模式存在；删掉 compare 后这些问题不复存在。两轮工程的工作量是负面 ROI
- **"用户反馈视觉问题"不一定是"调整视觉"，可能是"删除整个功能"**：用户两次反馈调整方向（先 C→C2，再 C2→删除）。第二次反馈应该是更早的信号
- **scope 添加要先经用户确认，不要"我觉得这功能很自然就顺手加上"**：compare 模式在 Phase 11.6 加进来时没问用户；如果先问，根本不会有 11.7-C 系列
- **回滚要彻底**：不仅删 SharedChromePanel，连 canvas 上的 `show_chrome/facies_changed/facies_names` 都要拔——这些 API 只有 compare 模式用，留着就是死代码

---
*Update after every 2 view/browser/search operations*
