# Geoviz Well Log 可视化包使用指南

`geoviz-well-log` 是一个为 PySide6 桌面应用设计的模块化测井渲染引擎。它底层基于 ECharts (SVG 模式)，能够高效处理大规模测井数据并提供符合地质标准的专业制图能力。

## 1. 安装与配置

该包目前以本地包形式存在于 `packages/geoviz_well_log` 目录中。在主项目中，可以通过以下方式安装：

```bash
uv add ./packages/geoviz_well_log
```

**依赖要求：**
- PySide6 >= 6.6
- pyqtgraph >= 0.13 (辅助计算)
- pydantic >= 2.0
- jinja2 (用于渲染 ECharts 模板)

## 2. 核心 API 说明

### 2.1 `ChartEngine` (核心渲染器)
这是最主要的 PySide6 控件，继承自 `QWidget`。

- `render_well_log_data(data: WellLogData, offset: float = 0.0)`: **推荐方法**。直接传入 Pydantic 模型进行渲染，内置了默认的轨道排列逻辑。
- `render_data(well_data_json: str)`: 底层渲染方法，接收 JSON 格式的硬编码配置。
- `export_svg()`: 触发异步 SVG 导出，结果通过 `bridge.svg_received` 信号返回。
- `bridge.zoom_changed`: 信号，当用户缩放深度轴时发出 `(start, end)`。
- `bridge.interval_clicked`: 信号，当用户点击岩性或相图层块时发出 `(top, bottom)`。

### 2.2 数据模型 (`models.py`)
使用 Pydantic 定义，确保数据类型安全：

- `WellLogData`: 井整体数据容器。
- `CurveData`: 单条测井曲线数据（含深度、数值、颜色、值域、线型）。
- `WellIntervals`: 地层分层数据容器（含系、统、组、段、岩性、相、层序等）。
- `IntervalItem`: 通用的区间块（top, bottom, name）。

### 2.3 跨井组件
- `SyncManager`: 管理多个 `ChartEngine` 实例的视口同步。
- `ConnectionOverlay`: 透明罩层，用于在两口井之间绘制彩色连通多边形。

## 3. 使用示例

### 3.1 渲染单井

```python
from geoviz_well_log import ChartEngine
import json

# 1. 初始化引擎
engine = ChartEngine()
engine.show()

# 2. 构造符合规范的 Payload
# 注意：通常从 WellLogData 模型通过 logic 转换生成
payload = {
    "metadata": { 
        "wellName": "Well_X", 
        "topDepth": 2500, 
        "bottomDepth": 2600,
        "depthOffset": 0.0 # 用于地层拉平的偏移量
    },
    "tracks": [
        { "type": "DepthTrack", "name": "深度", "width": 6 },
        { 
            "type": "CurveTrack", "name": "GR", "width": 15,
            "series": [
                {
                    "name": "GR", 
                    "color": "#e53e3e", 
                    "lineStyle": "solid", 
                    "data": [[2500.0, 45.2], [2500.1, 46.8], ...] # [depth, value]
                }
            ]
        },
        {
            "type": "LithologyTrack", "name": "岩性", "width": 10,
            "data": [
                {"top": 2500, "bottom": 2540, "name": "砂岩", "lithology": "sandstone", "color": "#fef08a"},
                {"top": 2540, "bottom": 2600, "name": "泥岩", "lithology": "mudstone", "color": "#cbd5e0"}
            ]
        }
    ]
}

# 3. 渲染
engine.render_data(json.dumps(payload))
```

### 3.2 实现连井对比

```python
from geoviz_well_log import ChartEngine, SyncManager, ConnectionOverlay, CorrelationLink

# 1. 创建多口井引擎
engine_a = ChartEngine()
engine_b = ChartEngine()

# 2. 注册同步
sync_manager = SyncManager()
sync_manager.register_engine(engine_a)
sync_manager.register_engine(engine_b)

# 3. 配置连线 (Correlation)
# 每一个 CorrelationLink 定义了 source_well 和 target_well 之间的对应层位
links = [
    CorrelationLink(
        source_well="Well_A", target_well="Well_B",
        source_interval_id="2500_2540_砂岩",
        target_interval_id="2510_2555_砂岩",
        color="#fef08a"
    )
]

overlay = ConnectionOverlay(parent_widget, [engine_a, engine_b])
overlay.set_links(links)
```

## 4. 轨道类型 (Track Types)

| 类型 | 说明 | 数据结构示例 |
|------|------|-------------|
| `DepthTrack` | 深度轴轨道 | `{"type": "DepthTrack", "depthOffset": 0.0}` |
| `CurveTrack` | 测井曲线轨道 | `{"series": [...], "bgIntervals": [...]}` |
| `LithologyTrack` | 岩性花纹轨道 | `{"data": [{"lithology": "sandstone", ...}]}` |
| `IntervalTrack` | 通用区间轨道 (相、地层) | `{"data": [{"name": "三角洲", ...}]}` |
| `SystemsTractTrack` | 体系域三角形轨道 | `{"data": [{"shape": "triangle-up", ...}]}` |

## 5. 样式与主题

系统内置了标准的地质纹理库（SVG 格式），位于主项目的 `src/patterns` 中。渲染时通过 `lithology` 字段指定的 ID（如 `sandstone`, `shale`）自动匹配对应的纹理图片。
