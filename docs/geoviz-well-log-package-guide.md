# Geoviz Well Log 可视化包使用指南

> 完整 API 参考和示例见 `packages/geoviz_well_log/README.md`。

`geoviz-well-log` 是一个为 PySide6 桌面应用设计的独立测井渲染引擎。它底层基于 ECharts (SVG 模式)，能够高效处理大规模测井数据并提供符合地质标准的专业制图能力。

## 1. 安装与配置

```bash
pip install -e ./packages/geoviz_well_log
```

**依赖要求：**
- PySide6 >= 6.6
- pydantic >= 2.0

## 2. 包模块概览

| 模块 | 职责 |
|------|------|
| `chart_engine.py` | `ChartEngine` — 核心渲染控件（QWebEngineView + ECharts） |
| `payload_builder.py` | 数据变换函数 — `WellLogData` → ECharts JSON payload |
| `track_manager.py` | `TrackManager` — 轨道排序、可见性、合并/拆分管理 |
| `export.py` | SVG/PDF/PNG 矢量导出 |
| `pattern_map.py` | `PATTERN_MAP` — 岩性/沉积相 → SVG 图案 ID 映射 |
| `models.py` | Pydantic 数据模型（`WellLogData`, `CurveData` 等） |
| `sync_manager.py` | `SyncManager` — 多井深度同步 |
| `connection_overlay.py` | `ConnectionOverlay` — 井间对比连线 |

## 3. 数据流

```
WellLogData (Pydantic 模型)
     │
     ▼  build_tracks_from_data()
Track Pool (dict[str, dict])
     │
     ▼  TrackManager.build_payload()
JSON Payload (str)
     │
     ▼  ChartEngine.render_data()
ECharts SVG 渲染
     │
     ▼  export_dialog() / export_svg()
矢量文件 (SVG/PDF)
```

## 4. 核心 API

### 4.1 ChartEngine（渲染控件）

```python
engine = ChartEngine(parent=None)
engine.render_data(json_str)          # 主渲染接口
engine.render_well_log_data(data)     # 便捷方法（自动构建默认布局）
engine.export_svg()                   # 触发 SVG 导出（异步）

# Bridge 信号
engine.bridge.ready                   # ECharts 就绪
engine.bridge.svg_received(str)       # SVG 导出完成
engine.bridge.zoom_changed(float, float)  # 用户缩放
engine.bridge.interval_clicked(float, float)  # 用户点击区间
```

### 4.2 PayloadBuilder（数据变换）

```python
from geoviz_well_log import build_tracks_from_data, build_legacy_display_items

# 自动构建所有轨道（地层、曲线、深度、岩性、沉积相、体系域、层序）
track_pool = build_tracks_from_data(well_log_data)

# 生成默认显示顺序
display_order = build_legacy_display_items(track_pool)

# 单独构建各类轨道
from geoviz_well_log import (
    build_curve_track,       # 曲线轨道
    build_interval_track,    # 通用区间轨道
    build_lithology_track,   # 岩性轨道
    build_systems_tract_track, # 体系域轨道
    build_merged_curve_track,  # 合并曲线轨道
    build_ai_prediction_tracks, # AI 预测结果轨道
)
```

### 4.3 TrackManager（轨道管理）

```python
from geoviz_well_log import TrackManager

mgr = TrackManager(track_pool)

# 生成完整 JSON payload（只渲染 checked 的轨道）
display = [("地层系统 (系/统/组)", True), ("曲线: GR", True), ("深度 (m)", False)]
payload = mgr.build_payload(metadata, display)
engine.render_data(payload)

# 合并/拆分曲线
mgr.merge_curves("AC", "GR")
mgr.split_curves("AC/GR")

# 添加/移除轨道
mgr.add_tracks({"AI预测相": track_descriptor})
mgr.remove_tracks(["AI预测相", "AI预测置信度"])
```

### 4.4 导出（矢量格式，与显示一致）

```python
from geoviz_well_log.export import export_dialog, export_svg, export_pdf

# 统一导出对话框（用户选格式）
export_dialog(engine, parent=window, default_name="HZ25-1")

# 直接指定格式
export_svg(engine, parent=window)   # SVG 矢量（与显示一致）
export_pdf(engine, parent=window)   # PDF 矢量（A3 横版）
```

### 4.5 多井同步

```python
from geoviz_well_log import SyncManager

sync = SyncManager()
sync.register_engine(engine1)
sync.register_engine(engine2)
# 一口井滚动/缩放 → 其他井自动跟随
```

## 5. 支持的轨道类型

| 类型 | 说明 | 必需字段 |
|------|------|----------|
| `DepthTrack` | 深度标尺 | `name`, `width` |
| `CurveTrack` | 测井曲线（支持多 series 叠加） | `name`, `width`, `series[]` |
| `LithologyTrack` | 岩性剖面（带 SVG 图案填充） | `name`, `width`, `data[]` |
| `IntervalTrack` | 通用区间（地层、沉积相、体系域等） | `name`, `width`, `data[]` |

## 6. 图案资源

内置 20 种地质 SVG 图案（`assets/patterns/`），符合 GB/T 附录M/O 规范。

```python
from geoviz_well_log import PATTERN_MAP
# {"砂岩": "sandstone", "泥岩": "mudstone", "潮坪": "tidal-flat", ...}
```
