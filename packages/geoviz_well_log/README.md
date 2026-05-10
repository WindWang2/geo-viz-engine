# geoviz-well-log

基于 ECharts 的测井可视化渲染引擎，面向地质工程桌面应用（PySide6）。

支持测井曲线、岩性剖面、沉积相、地层系统、体系域等多种轨道类型，内置 SVG 矢量导出与多井同步滚动。

## 安装

```bash
pip install -e .
```

依赖：PySide6 ≥ 6.5, pydantic ≥ 2.0

## 30 秒上手

```python
import sys, json
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from geoviz_well_log import ChartEngine
from geoviz_well_log.export import export_dialog

app = QApplication(sys.argv)

engine = ChartEngine()
engine.render_data(json.dumps({
    "metadata": {"wellName": "Demo-1", "topDepth": 1000, "bottomDepth": 1200},
    "tracks": [
        {"type": "DepthTrack", "name": "深度\n(m)", "width": 6},
        {
            "type": "CurveTrack", "name": "GR", "width": 14,
            "series": [{"name": "GR", "color": "#15803d", "lineStyle": "solid",
                        "data": [[1000, 45], [1020, 67], [1040, 82], [1060, 55], [1080, 38], [1100, 61], [1120, 74], [1140, 50], [1160, 63], [1180, 70], [1200, 58]]}]
        }
    ]
}))

window = QWidget()
layout = QVBoxLayout(window)
layout.addWidget(engine)
window.resize(400, 800)
window.show()
app.exec()
```

## 核心概念

### 轨道类型 (Track Types)

引擎通过 JSON payload 描述图表布局，支持以下轨道类型：

| 类型 | 说明 | 必需字段 |
|------|------|----------|
| `DepthTrack` | 深度标尺 | `name`, `width` |
| `CurveTrack` | 测井曲线（支持多 series 叠加） | `name`, `width`, `series[]` |
| `LithologyTrack` | 岩性剖面（带 SVG 图案填充） | `name`, `width`, `data[]` |
| `IntervalTrack` | 通用区间（地层、沉积相、体系域等） | `name`, `width`, `data[]` |

### JSON Payload 结构

```json
{
  "metadata": {
    "wellName": "HZ25-1-1",
    "topDepth": 2800.0,
    "bottomDepth": 3400.0
  },
  "tracks": [
    {
      "type": "DepthTrack",
      "name": "深度\n(m)",
      "width": 6
    },
    {
      "type": "CurveTrack",
      "name": "GR",
      "width": 14,
      "series": [
        {
          "name": "GR",
          "color": "#15803d",
          "lineStyle": "solid",
          "rangeLabel": "0 - 150",
          "data": [[2800.0, 45.2], [2800.125, 67.8], "..."]
        }
      ]
    },
    {
      "type": "LithologyTrack",
      "name": "岩性",
      "width": 9,
      "data": [
        {"top": 2800, "bottom": 2850, "name": "砂岩", "lithology": "sandstone", "color": "#cbd5e0"},
        {"top": 2850, "bottom": 2900, "name": "泥岩", "lithology": "mudstone", "color": "#cbd5e0"}
      ]
    },
    {
      "type": "IntervalTrack",
      "name": "组",
      "width": 4,
      "parentGroup": "地层系统",
      "textOrientation": "vertical",
      "data": [
        {"top": 2800, "bottom": 3000, "name": "恩平组", "color": "#ffffff"}
      ]
    }
  ]
}
```

### 区间轨道附加属性

`IntervalTrack` 的 data 项支持可选字段：

| 字段 | 说明 |
|------|------|
| `shape` | 形状：`"rect"`（默认）、`"triangle-up"`、`"triangle-down"` |
| `lithology` | SVG 图案 ID，用于岩性/沉积相填充 |
| `parentGroup` | 分组名（如 `"地层系统"`、`"沉积相"`），同组合并表头 |

## API 参考

### ChartEngine

核心渲染控件，继承 `QWidget`，内嵌 QWebEngineView + ECharts。

```python
from geoviz_well_log import ChartEngine

engine = ChartEngine(parent=None)
```

#### 方法

| 方法 | 签名 | 说明 |
|------|------|------|
| `render_data` | `(well_data_json: str) -> None` | 主渲染接口，接收 JSON 字符串 |
| `render_well_log_data` | `(data: WellLogData, offset=0.0) -> None` | 便捷方法，自动构建默认布局 |
| `export_svg` | `() -> None` | 触发 SVG 导出（异步，结果通过 `bridge.svg_received` 信号返回） |

#### Bridge 信号

通过 `engine.bridge` 访问：

| 信号 | 参数 | 触发时机 |
|------|------|----------|
| `ready` | 无 | ECharts 页面加载完成 |
| `svg_received(str)` | SVG 字符串 | SVG 导出完成 |
| `zoom_changed(float, float)` | (起始深度, 结束深度) | 用户缩放/滚动时 |
| `interval_clicked(float, float)` | (顶界深度, 底界深度) | 用户点击区间元素时 |

---

### 数据模型 (`models`)

所有模型基于 Pydantic v2。

```python
from geoviz_well_log import (
    WellLogData, CurveData, IntervalItem,
    WellIntervals, FaciesData, LithologyInterval, FaciesInterval
)
```

#### WellLogData

```python
WellLogData(
    well_name="HZ25-1-1",
    top_depth=2800.0,
    bottom_depth=3400.0,
    datum_elevation=0.0,
    curves=[
        CurveData(name="GR", depth=[...], values=[...], color="#15803d"),
        CurveData(name="RT", depth=[...], values=[...], color="#b91c1c"),
    ],
    intervals=WellIntervals(
        formation=[IntervalItem(top=2800, bottom=3000, name="恩平组")],
        lithology=[IntervalItem(top=2800, bottom=2850, name="砂岩")],
        facies=FaciesData(
            phase=[IntervalItem(top=2800, bottom=2900, name="潮坪")],
            sub_phase=[...],
            micro_phase=[...],
        ),
        systems_tract=[IntervalItem(top=2800, bottom=2950, name="TST")],
        sequence=[IntervalItem(top=2800, bottom=3200, name="SQ1")],
    ),
    custom_tracks=[],  # 可选：预构建的轨道描述列表
)
```

---

### Payload Builder

将 `WellLogData` 转换为 ECharts JSON payload 的工具函数。

```python
from geoviz_well_log import (
    build_tracks_from_data,
    build_curve_track,
    build_interval_track,
    build_lithology_track,
    build_systems_tract_track,
    build_merged_curve_track,
    build_ai_prediction_tracks,
    build_legacy_display_items,
)
```

| 函数 | 说明 |
|------|------|
| `build_tracks_from_data(data: WellLogData) -> dict[str, dict]` | 从 WellLogData 自动构建完整 track pool（地层/曲线/深度/岩性/沉积相/体系域/层序） |
| `build_curve_track(data, curve_names, label, width) -> dict \| None` | 构建单条或多条叠加曲线轨道 |
| `build_interval_track(items, name, width, ...) -> dict \| None` | 构建通用区间轨道（支持分组、旋转文字、SVG 图案填充） |
| `build_lithology_track(data, width, color) -> dict \| None` | 构建岩性剖面轨道（自动匹配 SVG 图案） |
| `build_systems_tract_track(items, width) -> dict \| None` | 构建体系域轨道（自动识别 TST/HST 形状和颜色） |
| `build_merged_curve_track(pool, names, width) -> dict` | 合并多条曲线到同一轨道（不同颜色） |
| `build_ai_prediction_tracks(records, pool) -> list[str]` | 从 AI 预测结果构建「预测相」+「置信度」轨道，加入 pool |
| `build_legacy_display_items(pool) -> list[str]` | 生成默认的轨道显示顺序列表 |

**示例：从原始数据构建图表**

```python
from geoviz_well_log import (
    ChartEngine, WellLogData, CurveData, IntervalItem,
    WellIntervals, build_tracks_from_data, build_legacy_display_items,
)
import json

data = WellLogData(
    well_name="Demo",
    top_depth=1000, bottom_depth=1200,
    curves=[
        CurveData(name="GR", depth=[1000, 1050, 1100, 1150, 1200],
                  values=[45, 67, 82, 55, 38], color="#15803d"),
    ],
    intervals=WellIntervals(
        formation=[IntervalItem(top=1000, bottom=1200, name="恩平组")],
    ),
)

# 方式一：全自动（推荐）
track_pool = build_tracks_from_data(data)
display_order = build_legacy_display_items(track_pool)
engine = ChartEngine()
engine.render_data(json.dumps({
    "metadata": {"wellName": data.well_name, "topDepth": data.top_depth, "bottomDepth": data.bottom_depth},
    "tracks": [track_pool[name] for name in track_pool if name in display_order],
}))

# 方式二：便捷方法（简单默认布局）
engine.render_well_log_data(data)
```

---

### TrackManager

管理轨道的排序、可见性、合并/拆分。

```python
from geoviz_well_log import TrackManager

pool = build_tracks_from_data(data)
mgr = TrackManager(pool)
```

| 方法 | 说明 |
|------|------|
| `build_payload(metadata, display_items) -> str` | 生成完整 JSON payload。`display_items` 为 `[(text, checked), ...]` 列表 |
| `resolve_sorted_tracks(display_items) -> list[dict]` | 只解析轨道，不生成 JSON |
| `merge_curves(name1, name2) -> dict` | 合并两条曲线轨道 |
| `split_curves(merged_name) -> (dict, dict)` | 拆分合并轨道（`merged_name` 为 `"GR/RT"` 格式） |
| `add_tracks(tracks: dict)` | 向 pool 添加新轨道 |
| `remove_tracks(names: list[str])` | 从 pool 移除轨道 |
| `pool` (property) | 获取当前 track pool 字典 |

**示例：交互式轨道管理**

```python
mgr = TrackManager(build_tracks_from_data(data))

# 构建渲染 payload（只显示 checked 的轨道，按指定顺序）
display = [("地层系统 (系/统/组)", True), ("曲线: GR", True), ("深度 (m)", False)]
payload = mgr.build_payload(metadata, display)
engine.render_data(payload)

# 合并曲线
merged = mgr.merge_curves("AC", "GR")

# 添加 AI 预测轨道
build_ai_prediction_tracks(records, mgr.pool)
```

---

### 导出 (`export`)

矢量导出，输出与屏幕显示完全一致。SVG/PDF 为矢量格式。

```python
from geoviz_well_log.export import export_dialog, export_svg, export_pdf, export_png
```

| 函数 | 格式 | 矢量 | 说明 |
|------|------|------|------|
| `export_dialog(engine, parent, default_name)` | SVG/PDF/PNG | SVG ✓, PDF ✓ | 统一导出对话框，用户选格式 |
| `export_svg(engine, parent, default_name)` | SVG | ✓ | ECharts 内置 SVG 导出，与显示一致 |
| `export_pdf(engine, parent, default_name)` | PDF | ✓ | QWebEngineView printToPdf，A3 横版 |
| `export_png(engine, parent, default_name)` | PNG | ✗ | 控件截图（栅格，仅作便利用途） |

**SVG 导出原理**：ECharts 使用 SVG renderer 渲染，`export_svg()` 调用 `chart.getDataURL({type:'svg'})` 直接从渲染结果提取 SVG，保证导出与显示像素级一致。

**示例：导出矢量图**

```python
from geoviz_well_log.export import export_dialog

# 用户选择格式后自动导出
export_dialog(engine, parent=window, default_name="HZ25-1-1_well_log")

# 或直接指定格式
from geoviz_well_log.export import export_svg
path = export_svg(engine, parent=window, default_name="HZ25-1-1")
# path 为保存路径，SVG 异步写入（通过 bridge.svg_received 信号）
```

---

### 多井同步 (`SyncManager`)

多口井的深度轴联动缩放/滚动。

```python
from geoviz_well_log import SyncManager

sync = SyncManager()
sync.register_engine(engine1)
sync.register_engine(engine2)
# engine1 滚动 → engine2 自动跟随，反之亦然
```

| 方法 | 说明 |
|------|------|
| `register_engine(engine)` | 注册引擎（自动连接 `zoom_changed` 信号） |
| `unregister_engine(engine)` | 移除引擎 |

---

### 井间对比连线 (`ConnectionOverlay`)

在多井之间绘制沉积相对比多边形。

```python
from geoviz_well_log import ConnectionOverlay

overlay = ConnectionOverlay(parent=container, engines=[engine1, engine2])
overlay.set_links([
    CorrelationLink(source_well="W1", target_well="W2",
                    source_interval_id="2800_2900", target_interval_id="2810_2910",
                    color="#3b82f6"),
])
```

---

### 岩性/沉积相图案 (`pattern_map`)

内置 20 种地质图案映射（GB/T 勘探管理图件图册编制规范 附录M/O）。

```python
from geoviz_well_log import PATTERN_MAP

# {"砂岩": "sandstone", "泥岩": "mudstone", "潮坪": "tidal-flat", ...}
pattern_id = PATTERN_MAP["砂岩"]  # → "sandstone"
```

SVG 图案文件位于 `geoviz_well_log/assets/patterns/`，`ChartEngine` 启动时自动加载为 base64 data URL。

## 完整示例

### 示例 1：从 LAS 文件渲染单井

```python
import json
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton
from geoviz_well_log import (
    ChartEngine, WellLogData, CurveData, IntervalItem,
    WellIntervals, build_tracks_from_data, build_legacy_display_items,
    TrackManager,
)
from geoviz_well_log.export import export_dialog

app = QApplication([])

# 构造数据（实际使用中从 LAS/Excel 加载）
data = WellLogData(
    well_name="HZ25-1-1",
    top_depth=2800.0,
    bottom_depth=3200.0,
    curves=[
        CurveData(name="GR", depth=[2800, 2850, 2900, 2950, 3000, 3050, 3100, 3150, 3200],
                  values=[45, 67, 82, 55, 38, 61, 74, 50, 63], color="#15803d"),
        CurveData(name="RT", depth=[2800, 2850, 2900, 2950, 3000, 3050, 3100, 3150, 3200],
                  values=[2.1, 3.5, 8.2, 4.1, 1.5, 6.3, 12.0, 3.8, 5.1], color="#b91c1c"),
    ],
    intervals=WellIntervals(
        formation=[IntervalItem(top=2800, bottom=3200, name="恩平组")],
        lithology=[
            IntervalItem(top=2800, bottom=2950, name="砂岩"),
            IntervalItem(top=2950, bottom=3100, name="泥岩"),
            IntervalItem(top=3100, bottom=3200, name="砂岩"),
        ],
    ),
)

# 构建 track pool 和管理器
track_pool = build_tracks_from_data(data)
display_items = build_legacy_display_items(track_pool)
mgr = TrackManager(track_pool)

# 创建引擎
engine = ChartEngine()
metadata = {"wellName": data.well_name, "topDepth": data.top_depth, "bottomDepth": data.bottom_depth}
display = [(text, True) for text in display_items]
engine.render_data(mgr.build_payload(metadata, display))

# 布局
window = QWidget()
layout = QVBoxLayout(window)
layout.addWidget(engine)

export_btn = QPushButton("导出")
export_btn.clicked.connect(lambda: export_dialog(engine, window, data.well_name))
layout.addWidget(export_btn)

window.resize(600, 900)
window.show()
app.exec()
```

### 示例 2：自定义 JSON payload（无数据模型）

```python
import json
from PySide6.QtWidgets import QApplication
from geoviz_well_log import ChartEngine

app = QApplication([])
engine = ChartEngine()

engine.render_data(json.dumps({
    "metadata": {"wellName": "Custom", "topDepth": 0, "bottomDepth": 100},
    "tracks": [
        {"type": "DepthTrack", "name": "深度", "width": 6},
        {
            "type": "CurveTrack", "name": "GR + SP", "width": 14,
            "series": [
                {"name": "GR", "color": "#15803d", "lineStyle": "solid", "rangeLabel": "0 - 150",
                 "data": [[0, 45], [20, 67], [40, 82], [60, 55], [80, 38], [100, 61]]},
                {"name": "SP", "color": "#b91c1c", "lineStyle": "dashed", "rangeLabel": "-200 - 200",
                 "data": [[0, -50], [20, -80], [40, -120], [60, -60], [80, -30], [100, -90]]},
            ]
        },
        {
            "type": "LithologyTrack", "name": "岩性", "width": 10,
            "data": [
                {"top": 0, "bottom": 40, "name": "砂岩", "lithology": "sandstone", "color": "#fef9c3"},
                {"top": 40, "bottom": 70, "name": "泥岩", "lithology": "mudstone", "color": "#e2e8f0"},
                {"top": 70, "bottom": 100, "name": "灰岩", "lithology": "limestone", "color": "#fecaca"},
            ]
        },
        {
            "type": "IntervalTrack", "name": "层序", "width": 5,
            "textOrientation": "vertical",
            "data": [
                {"top": 0, "bottom": 50, "name": "SQ1", "color": "#dbeafe"},
                {"top": 50, "bottom": 100, "name": "SQ2", "color": "#fef3c7"},
            ]
        },
    ]
}))

engine.show()
app.exec()
```

### 示例 3：多井同步对比

```python
from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout
from geoviz_well_log import ChartEngine, SyncManager
import json

app = QApplication([])

engines = []
for name in ["Well-A", "Well-B"]:
    e = ChartEngine()
    e.render_data(json.dumps({
        "metadata": {"wellName": name, "topDepth": 1000, "bottomDepth": 1200},
        "tracks": [
            {"type": "DepthTrack", "name": "深度", "width": 6},
            {"type": "CurveTrack", "name": "GR", "width": 14,
             "series": [{"name": "GR", "color": "#15803d", "data": [[1000+i*10, 40+i*3] for i in range(21)]}]},
        ]
    }))
    engines.append(e)

sync = SyncManager()
for e in engines:
    sync.register_engine(e)

window = QWidget()
layout = QHBoxLayout(window)
for e in engines:
    layout.addWidget(e)
window.resize(900, 800)
window.show()
app.exec()
```

## 包结构

```
geoviz_well_log/
├── __init__.py              # 公共 API 导出
├── chart_engine.py          # ChartEngine (QWidget + ECharts) + Bridge
├── models.py                # Pydantic 数据模型
├── config.py                # 轨道配置类
├── payload_builder.py       # 数据 → ECharts JSON 变换
├── track_manager.py         # 轨道排序/可见性/合并/拆分管理
├── pattern_map.py           # 岩性/沉积相 → SVG 图案映射
├── export.py                # SVG/PDF/PNG 矢量导出
├── sync_manager.py          # 多井深度同步
├── connection_overlay.py    # 井间对比连线
├── utils.py                 # build_default_payload 便捷方法
├── configs/
│   └── laolong1.py          # 预置配置（老龙1井）
├── assets/
│   └── patterns/            # 16 种 SVG 岩性/沉积相图案
└── web_dist/
    ├── index.html           # ECharts 宿主页
    └── assets/index.js      # ECharts + 测井渲染代码（打包后）
```

## 版本

0.1.0
