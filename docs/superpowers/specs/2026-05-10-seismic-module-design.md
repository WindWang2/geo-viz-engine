# Seismic Module Design

独立地震可视化包 `geoviz-seismic`，提供 3D 体积渲染 + 2D 剖面显示（VD/Wiggle），可 `pip install` 后在任何 PySide6 项目中使用。

## Package Structure

```
packages/geoviz_seismic/
├── geoviz_seismic/
│   ├── __init__.py              # 公开 API 导出
│   ├── models.py                # Pydantic 数据模型
│   ├── loader.py                # SEGY 按需加载 + 降采样
│   ├── horizon.py               # 层位解析 + 补全
│   ├── cache.py                 # LRU 切片缓存
│   ├── colormap.py              # 地震专业色标管理
│   ├── renderer_3d.py           # PyVista 3D 渲染 widget
│   ├── profile_vd.py            # VD 模式渲染 (QImage)
│   ├── profile_wiggle.py        # Wiggle 模式渲染 (VisPy)
│   ├── profile_widget.py        # 2D 剖面统一 widget (QStackedWidget)
│   ├── seismic_view.py          # 高层组合 widget (3D+2D+toolbar，开箱即用)
│   └── assets/                  # 色标定义文件等
├── pyproject.toml
└── README.md
```

## Architecture

```
SeismicPage (QWidget)
├── Toolbar
│   ├── 加载 SEGY / Demo
│   ├── 色标选择
│   ├── 显示模式切换 (VD / Wiggle)
│   ├── 剖面类型 (Inline / Crossline / Time)
│   └── 层位加载
├── QSplitter (垂直，可拖拽)
│   ├── Renderer3D (PyVista QtInteractor)
│   │   ├── 体积渲染 (vtkSmartVolumeMapper, 降采样数据)
│   │   ├── 三组可拖拽切面指示器 (plane widget)
│   │   ├── 层位面 (PolyData mesh)
│   │   └── emit slice_changed(type, position)
│   └── ProfileWidget (QStackedWidget)
│       ├── ProfileVD (QImage 热图渲染)
│       ├── ProfileWiggle (VisPy GPU 线渲染)
│       ├── 坐标轴 / 色标 / 标注
│       └── slot on_slice_changed → 更新剖面
├── SeismicLoader (segyio 按需切片读取)
├── HorizonParser (移植自 clustering 项目)
└── SeismicCache (LRU, 50 条切片)
```

## Data Flow

```
SEGY 文件
  ↓ segyio.open()
SeismicLoader
  ├── inspect_axes() → SeismicVolumeMeta
  ├── read_inline(idx) → numpy 2D
  ├── read_crossline(idx) → numpy 2D
  ├── read_timeslice(idx) → numpy 2D
  └── get_volume_downsampled(factor) → numpy 3D
        ↓                          ↓
  Renderer3D (降采样体)     ProfileWidget (全分辨率切片)
        ↓                          ↓
  PyVista volume render     QImage VD / VisPy Wiggle
```

切面联动：
```
用户拖拽 3D 切面指示器
  → Renderer3D.slice_changed signal
  → SeismicPage.on_slice_changed slot
  → SeismicLoader.read_xxx(position) [cache hit or disk read]
  → ProfileWidget.update_profile(data, axis_info)
```

## Component Design

### SeismicLoader

按需读取，不一次性加载整个 SEGY 到内存。

```python
class SeismicLoader:
    def __init__(self, path: str): ...
    def inspect(self) -> SeismicVolumeMeta: ...
    def read_inline(self, iline: int) -> np.ndarray: ...      # shape: (nX, nT)
    def read_crossline(self, xline: int) -> np.ndarray: ...   # shape: (nI, nT)
    def read_timeslice(self, sample: int) -> np.ndarray: ...   # shape: (nI, nX)
    def get_volume_downsampled(self, factor=(4,4,2)) -> np.ndarray: ...
    def close(self): ...
```

- 内部保持 `segyio.open()` 文件句柄
- 参考自 `clustering/segy_reader.py` 的轴推断和采样间隔逻辑
- 支持 regular 和 non-regular 采样轴

### SeismicCache

```python
class SeismicCache:
    def __init__(self, max_slices: int = 50): ...
    def get(self, key: tuple) -> np.ndarray | None: ...
    def put(self, key: tuple, data: np.ndarray): ...
    def clear(self): ...
```

- LRU 策略，key 为 `(slice_type, position)`
- 降采样体单独缓存，只生成一次

### Renderer3D

```python
class Renderer3D(QWidget):
    slice_changed = Signal(str, int)  # (slice_type, position)

    def load_volume(self, data: np.ndarray, meta: SeismicVolumeMeta): ...
    def add_horizon(self, horizon_data: np.ndarray, meta: SeismicVolumeMeta): ...
    def set_colormap(self, cmap_name: str): ...
    def set_slice_position(self, slice_type: str, position: int): ...
    def clear(self): ...
```

- PyVista `QtInteractor` 嵌入 Qt
- 三组 `add_plane_widget()` 切面指示器，拖拽时 emit signal
- 体积用 `vtkSmartVolumeMapper` + 降采样数据
- 切面用 `slice_orthogonal()` 或自定义 plane widget 回调
- 坐标轴标注真实 Inline/Xline/Time 值
- 拖拽过程中只更新 3D 预览，松手后才触发 2D 剖面刷新

### ProfileWidget

```python
class ProfileWidget(QWidget):
    def update_profile(self, data: np.ndarray, axis_info: dict): ...
    def set_display_mode(self, mode: str): ...  # "vd" | "wiggle"
    def set_colormap(self, cmap_name: str): ...
    def set_wiggle_density(self, trace_step: int): ...
```

内部用 `QStackedWidget` 管理 VD 和 Wiggle 两个子 widget，切换时显示/隐藏。

### ProfileVD (VD 热图)

```python
class ProfileVD(QWidget):
    def render(self, data: np.ndarray, axis_info: dict, colormap: str): ...
```

- `numpy 2D` → `matplotlib.colormap` 查表 → `QImage` → `QPainter.drawPixmap()`
- QPainter 变换实现缩放/平移
- 右侧色标条（amplitude → color 映射）
- 鼠标位置 tooltip 显示坐标 + amplitude 值

### ProfileWiggle (Wiggle 波形道)

```python
class ProfileWiggle(QWidget):
    def render(self, data: np.ndarray, axis_info: dict): ...
```

- **VisPy Canvas** 嵌入 Qt（`vispy.app.backends._pyside6`）
- `LineVisual` 画波形曲线，`PolygonVisual` 填充正振幅
- 参考自 CIGVis 的 wiggle 渲染逻辑
- 默认隔 N 道画一条，`trace_step` 可调节
- VisPy 内置缩放/平移交互

### HorizonParser

```python
class HorizonParser:
    def __init__(self, path: str, unit: str = "sample", scale: float = 1.0): ...
    def parse(self, axes: dict) -> np.ndarray: ...  # shape: (nI, nX) ms 值
    def fill_nearest(self, max_dist: int = 0) -> np.ndarray: ...
    def fill_rbf(self, neighbors: int = 24, smoothing: float = 0.0) -> np.ndarray: ...
```

- 移植自 `clustering/horizon_parser.py`
- 支持 dense/sparse 层位文件
- 支持 ms / sample 单位
- 支持 nearest / rbf_linear_local 补全

### ColormapManager

```python
class ColormapManager:
    SEISMIC = "seismic"     # 红白蓝
    GRAY = "gray"
    JET = "jet"
    HUANG = "huang"         # 常用地震色标

    @staticmethod
    def get_colormap(name: str, n_colors: int = 256) -> np.ndarray: ...  # (N, 4) RGBA
    @staticmethod
    def get_lut(name: str, n_colors: int = 256) -> object: ...  # VTK or QImage compatible
```

- 提供地震专业色标：seismic, gray, jet, huang 等
- 输出格式同时支持 VTK transfer function 和 QImage LUT

### models.py

```python
class SeismicVolumeMeta(BaseModel):
    filename: str
    n_inlines: int
    n_crosslines: int
    n_samples: int
    sample_interval: float      # ms
    iline_start: int
    iline_step: int
    xline_start: int
    xline_step: int
    dt_ms: float
    t0_ms: float = 0.0

class SliceInfo(BaseModel):
    slice_type: str    # "inline" | "crossline" | "time"
    position: int
    axis_h_label: str
    axis_v_label: str
    axis_h_values: list[float]
    axis_v_values: list[float]

class HorizonData(BaseModel):
    name: str
    unit: str
    shape: tuple[int, int]
    filled: bool
```

## Public API Surface

```python
# geoviz_seismic/__init__.py
from .loader import SeismicLoader
from .cache import SeismicCache
from .horizon import HorizonParser
from .colormap import ColormapManager
from .renderer_3d import Renderer3D
from .profile_widget import ProfileWidget
from .profile_vd import ProfileVD
from .profile_wiggle import ProfileWiggle
from .seismic_view import SeismicView
from .models import SeismicVolumeMeta, SliceInfo, HorizonData
```

上层 `src/pages/seismic_page.py` 仅做 UI 编排（侧栏集成、数据目录默认路径等），核心逻辑全部在包内。包内高层 API `SeismicView` 提供完整的 3D+2D+toolbar 组合，可直接嵌入任何 Qt 布局。

## Performance Strategy

| 场景 | 数据量 | 策略 |
|------|--------|------|
| 3D 体积渲染 | 601×901×255 (原始) | 降采样 4×4×2 → 150×225×127 |
| 2D VD 剖面 | 901×255 ≈ 23 万像素 | QImage 直出，< 10ms |
| 2D Wiggle 剖面 | 901 traces × 255 samples | VisPy GPU 线渲染 |
| 切面拖拽 | 频繁读取 | LRU 缓存 50 条 + 松手刷新 2D |
| SEGY 文件读取 | 682MB | 按需 inline/crossline，不整体加载 |

## Dependencies

```
geoviz-seismic/
├── PySide6 >= 6.5
├── pyvista >= 0.43
├── pyvistaqt (Renderer3D 的 Qt 集成必需，不可用时降级为 QLabel 提示)
├── vispy >= 0.14 (for Wiggle rendering)
├── segyio >= 1.9
├── numpy
├── scipy (horizon fill)
└── pydantic >= 2.0
```

## Reference Code

- `clustering/segy_reader.py` → `loader.py` 的按需读取逻辑
- `clustering/horizon_parser.py` → `horizon.py` 的层位解析和补全
- `clustering/config.py` → 层位单位/缩放/补全参数的设计参考
- CIGVis (GitHub: JintaoLee-Roger/cigvis) → Wiggle 渲染和 VisPy 集成模式参考
