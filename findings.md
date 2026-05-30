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

## Resources
- SEG Wiki 瞬时属性：https://wiki.seg.org/wiki/Instantaneous_attributes_-_book
- SEG Wiki 甜点属性：https://wiki.seg.org/wiki/Sweetness
- SEG Wiki 相干属性：https://wiki.seg.org/wiki/Coherence

---
*Update after every 2 view/browser/search operations*
