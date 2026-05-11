# Changelog

All notable changes to this package will be documented in this file.

## [0.1.0] - 2026-05-11

### Added
- `SeismicLoader`: SEGY file reader with inline/crossline/timeslice reads and downsampled volume extraction.
- `Renderer3D`: PyVista Qt 3D volume renderer with interactive inline/crossline/time slice planes.
- `ProfileVD`: Variable-density heatmap profile renderer.
- `ProfileWiggle`: Wiggle-trace renderer with VisPy GPU acceleration and QPainter fallback.
- `ProfileWidget`: Unified VD/Wiggle display-mode switcher.
- `SeismicView`: Composite 3D+2D+toolbar widget (drop-in for any PySide6 app).
- `SeismicCache`: LRU slice cache (default 50 entries, count-based eviction).
- `ColormapManager`: seismic/gray/jet/hsv colormaps with LUT caching.
- `HorizonParser`: Tab-separated horizon file parser with nearest/RBF interpolation.
- `SeismicVolumeMeta`, `SliceInfo`, `HorizonData`: Pydantic data models.
- Async synthetic data generation and SEGY loading via QThread workers.
- `examples/demo.py` and `examples/load_segy.py` runnable examples.
- `python -m geoviz_seismic` entry point for quick demo.

## [0.1.2] - 2026-05-11

### Changed
- **迁移 3D 渲染引擎**：重写 `Renderer3D` 从 Vispy 迁移至 PyQtGraph。彻底解决 Wayland/OpenGL ES 上下文下的 #version 120 编译问题。
- **新增 GPU 加速层**：引入 `gpu_ops.py` 模块与 `cupy-cuda13x` 依赖，实现地震体数据 GPU 显存常驻和极速切片，告别 CPU 端 numpy 内存拷贝瓶颈。
- **更新测试套件**：现代化的 `test_renderer_3d.py` 替代原有的 subprocess probe 逻辑，直观验证本地 Qt 环境。

## [0.1.1] - 2026-05-11

### Changed
- Async SEGY and synthetic data loading via QThread workers (no UI freeze).
- QPixmap caching in ProfileVD and ProfileWiggle to skip re-renders.
- ColormapManager LUT caching to avoid rebuilding colour tables. Added `clear_cache()`.
- ProfileVD caches normalized data for fast colormap switches (skips nanmin/nanmax).
- VisPy wiggle rendering batched into single LineVisual with NaN separators.
- Vectorized synthetic data generation and slice info building with numpy.
- Fixed `_read_points` in HorizonParser: `nums[-1]` → `nums[2]` for correct column read.
- Thread safety: worker closes segyio handle before emitting; main thread re-opens lazily.
- Guard against double-clicking async worker buttons (disconnect previous signals).
- SmoothPixmapTransform scaling in ProfileVD paintEvent.
- Added docstrings to all public classes and methods.
- Literal types for enum-like strings (slice_type, mode, unit).
- HorizonAxes TypedDict for typed horizon parser axes parameter.
- SeismicLoader context manager support (`__enter__`/`__exit__`).
- Removed duplicate `is_loaded()` method (identical to `is_ready()`).
