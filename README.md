# GeoViz Engine — 地质数据可视化桌面引擎

![PySide6](https://img.shields.io/badge/PySide6-6.6+-41CD52?logo=qt)
![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python)
![ECharts](https://img.shields.io/badge/ECharts-Well_Log-41CD52)
![pyqtgraph](https://img.shields.io/badge/pyqtgraph-OpenGL-5896FF)
![License](https://img.shields.io/badge/License-MIT-green)

面向地质工程师和科研人员的**跨平台桌面应用**，提供测井数据可视化、井位地图、地震体三维显示等功能。

> **v0.1-web** (Tauri + React + FastAPI 架构) 已归档于 git tag `v0.1-web`。

---

## About / 项目简介

GeoViz Engine 是一款基于 **PySide6 + ECharts + pyqtgraph** 的单进程地质数据可视化桌面应用：

- **UI 框架（PySide6/Qt）**：窗口管理、页面导航、文件对话框、表格展示
- **测井渲染（ECharts SVG）**：测井曲线、岩性柱、沉积相综合柱状图，通过独立 `geoviz-well-log` 包提供
- **3D 渲染（pyqtgraph OpenGL）**：地震体三维显示、任意方向剖面、等值面提取
- **地图（MapLibre GL）**：井位分布、底图、交互选井

目标用户：地质工程师、测井分析人员、地球科学领域科研人员。

---

## Architecture / 技术架构

```
┌─────────────────────────────────────────────────────────┐
│           GeoViz Engine — 单进程 PySide6 桌面应用        │
│                                                         │
│  MainWindow                                             │
│  ┌──────┬──────────────────────────────────────────┐    │
│  │ 侧栏 │  QStackedWidget (7 页面)                  │    │
│  │      │                                          │    │
│  │ 🗺   │  MapPage     QPainter (geoviz-map)        │    │
│  │ 🌍   │  PaleoMap    QPainter (geoviz-paleo-map)  │    │
│  │ ⛏   │  WellLogPage ECharts + WebEngine         │    │
│  │ ⛓   │  CrossWell   QPainter (geoviz-cross-well)│    │
│  │ 🧊   │  SeismicPage pyqtgraph OpenGL            │    │
│  │ 📁   │  DataPage    QTableWidget + 文件对话框     │    │
│  │ 🛠   │  ToolsPage   独立小工具集                 │    │
│  └──────┴──────────────────────────────────────────┘    │
│                                                         │
│  packages/geoviz-well-log/                              │
│  ┌─────────────────────────────────────────────────┐    │
│  │  独立测井可视化引擎 (ECharts-based)              │    │
│  │  ├── ChartEngine    渲染控件                     │    │
│  │  ├── TrackManager   轨道排序/合并/拆分           │    │
│  │  ├── PayloadBuilder 数据→JSON 变换               │    │
│  │  ├── Export         SVG/PDF 矢量导出             │    │
│  │  ├── SyncManager    多井同步                     │    │
│  │  └── PatternMap     岩性/沉积相 SVG 图案         │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  packages/geoviz-seismic/                               │
│  ┌─────────────────────────────────────────────────┐    │
│  │  独立地震可视化引擎 (pyqtgraph + segyio)          │    │
│  │  ├── Renderer3D     pyqtgraph 3D 体渲染          │    │
│  │  ├── SeismicLoader  SEGY 按需切片读取            │    │
│  │  ├── ProfileVD/Wiggle 2D 剖面显示               │    │
│  │  ├── SeismicView    组合 3D+2D+工具栏            │    │
│  │  ├── HorizonParser  层位解析与插值               │    │
│  │  └── ColormapManager 色标管理                    │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  packages/geoviz-map/                                   │
│  ┌─────────────────────────────────────────────────┐    │
│  │  独立地图可视化引擎 (QPainter + Web Mercator)     │    │
│  │  ├── MapCanvas      组合 6 个 layer              │    │
│  │  ├── Projection     Web Mercator (MapLibre 兼容) │    │
│  │  ├── Viewport       center+zoom 像素映射         │    │
│  │  ├── ZoomPanHandler 拖拽+滚轮缩放                │    │
│  │  └── Layers         背景/网格/地块/标签/井点      │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  packages/geoviz-paleo-map/                             │
│  ┌─────────────────────────────────────────────────┐    │
│  │  独立古地理可视化引擎 (QPainter + Plate Carrée)   │    │
│  │  ├── PaleoMapCanvas 组合 8 个 layer              │    │
│  │  ├── FaciesStyleResolver 每相缓存复合纹理         │    │
│  │  ├── Layers         背景/多边形/标签/井点         │    │
│  │  └── Chrome         标题/指北/比例尺/图例         │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  src/   data/ loaders & models │ pages/ UI              │
└─────────────────────────────────────────────────────────┘
```

### Tech Stack / 完整技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| UI 框架 | PySide6 6.6+ | 桌面窗口、导航、控件 |
| 测井渲染 | ECharts 5.x (SVG) | 曲线、岩性/相柱状图（通过 `geoviz-well-log` 包） |
| 3D 渲染 | pyqtgraph 0.13+ / PyOpenGL | 地震体三维显示、剖面切片 |
| 地图 | QPainter (geoviz-map) | 井位地图、Web Mercator 投影、交互选井 |
| 数据模型 | Pydantic v2 | 强类型数据验证与序列化 |
| Excel 解析 | python-calamine | 基于 Rust 的极速表格数据解析引擎 |
| 数据处理 | pandas 2.x / numpy 1.26+ | 表格数据、数值计算 |

---

## Features / 功能模块

### 井剖面 — 综合测井解释图

- **独立渲染引擎**：底层 `geoviz-well-log` 包可脱离主应用独立使用，支持 `pip install` 后在任何 PySide6 项目中集成。
- **高性能 ECharts 渲染**：测井曲线支持万级数据点流畅缩放，岩性/沉积相使用 SVG 花纹填充。
- **轨道管理**：通过 `TrackManager` 实现拖拽排序、曲线合并/拆分、可见性控制。
- **矢量导出**：SVG/PDF 导出与屏幕显示完全一致（ECharts SVG renderer → 矢量输出）。
- **AI 沉积相预测**：支持一键调用 AI 模型预测沉积相，结果直接渲染为轨道并持久化到 Excel。
- 6 种岩性 SVG 花纹（砂岩、粉砂岩、泥岩、页岩、灰岩、白云岩）— GB/T 附录M
- 10 种沉积相 SVG 纹理（潮坪、陆棚、砂坪等）— GB/T 附录O

### 连井对比 — 地层对比与相关分析

- **独立渲染引擎**：底层 `geoviz-cross-well` 包可脱离主应用独立使用，支持 `pip install` 后在任何 PySide6 项目中集成。
- **层位顶面数据库**：支持从 CSV 加载层位顶面数据，以虚线标注并自动配色。可交互调整深度。
- **手动拾取**：在测井曲线上点击放置地层拾取点，Shift+点击跨井连接拾取，自动绘制贝塞尔相关连线。
- **撤销/重做**：完整的拾取操作撤销栈（Ctrl+Z / Ctrl+Y），支持拾取放置、连接、删除等操作。
- **DTW 自动对比**：基于动态时间规整（Dynamic Time Warping）的自动层位对比，以虚线"幽灵拾取"展示建议，点击接受或右键拒绝。
- **地震校深**：加载 checkshot CSV，支持深度-时间域转换与双轴显示。
- **智能相连通**：基于层序地层学骨架（Sequence/Member），自动跨井追踪并绘制彩色沉积相连通多边形。
- **全画幅视口同步**：多口井的滚动与缩放实现毫秒级锁步（Lock-step）联动。
- **超宽 SVG 导出**：支持一键导出高清 SVG 矢量图长卷。

### 工具箱

- **测井 XML 转换**：一键将复杂的测井 XML 数据转换为标准 LaoLong 格式 Excel。
- **更多工具**：预留小工具接入接口。

### 地图总览

- 57 口真实井位坐标（EPSG:4326/WGS84），MapLibre GL 暗色底图
- 井位点击 → Qt WebChannel 信号 → 切换到井剖面页面
- 井剖面页也支持下拉框直接选井

### 地震 3D

- **独立渲染引擎**：底层 `geoviz-seismic` 包可脱离主应用独立使用，支持 `pip install` 后在任何 PySide6 项目中集成。
- SEGY 文件加载（segyio）→ pyqtgraph GLVolumeItem → 三维体渲染
- 交互式切片平面（inline/crossline/time），拖拽实时更新 2D 剖面
- 2D 剖面双模式：VD 热图（Variable Density）与 Wiggle 波形，支持 CuPy GPU 加速（NumPy 自动回退）
- 层位文件加载与 3D 曲面叠加，支持 nearest/RBF 插值
- 内置合成地震数据演示（含断层、倾斜反射层、噪声）
- 4 种色标：seismic、gray、jet、hsv
- LRU 切片缓存（默认 50 条），拖拽切片 200ms 防抖

### 数据管理

- 文件导入：Excel (.xlsx)、LAS (.las)、SEGY (.sgy)
- 极速缓存：采用 Rust Calamine 引擎 + Pydantic-based JSON 缓存，实现数十万点 Excel 数据 10 毫秒级"秒开"。
- 井位坐标表格展示

---

## Roadmap / 开发路线图

| 阶段 | 状态 | 内容 |
|------|------|------|
| v0.1-web | ✅ 已归档 | Tauri+React+FastAPI Web 架构 (tag: v0.1-web) |
| Phase 1 | ✅ 已完成 | PySide6 骨架、导航、单井剖面、地图、地震3D、数据管理 |
| Phase 2 | ✅ 已完成 | 多井对比、相变连通模型、地层拉平、TVDSS对齐、全画幅SVG导出、Calamine解析加速 |
| Phase 3 | ✅ 已完成 | 测井引擎独立化、轨道管理器、矢量导出、AI预测集成、测井选择器 |
| Phase 4 | ✅ 已完成 | 地震可视化独立化、3D体渲染+2D剖面、SEGY按需切片、层位解析 |
| Phase 5 | ✅ 已完成 | 连井对比拾取工作流（层位顶面、手动拾取+撤销、DTW自动对比、地震校深） |
| Phase 6 | 🔄 进行中 | 地震属性分析、井震结合 |

---

## Quick Start / 快速开始

### 前置条件

- Python 3.12+
- 系统依赖：OpenGL 驱动（pyqtgraph OpenGL 需要）

### 开发模式

```bash
# 1. 克隆项目
git clone <repo-url>
cd geo-viz-engine

# 2. 创建虚拟环境并安装依赖
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 3. 启动应用
python -m src.main
```

### 生产构建

```bash
source .venv/bin/activate
python scripts/build.py
```

---

## Project Structure / 项目结构

```
geo-viz-engine/
├── packages/
│   ├── geoviz_well_log/           # 独立测井可视化包 (pip installable)
│   │   ├── geoviz_well_log/
│   │   │   ├── chart_engine.py    # ChartEngine (QWebEngineView + ECharts)
│   │   │   ├── payload_builder.py # 数据→ECharts JSON 变换
│   │   │   ├── track_manager.py   # 轨道排序/可见性/合并/拆分
│   │   │   ├── export.py          # SVG/PDF/PNG 矢量导出
│   │   │   ├── pattern_map.py     # 岩性/沉积相 SVG 图案映射
│   │   │   ├── models.py          # Pydantic 数据模型
│   │   │   ├── sync_manager.py    # 多井深度同步
│   │   │   ├── connection_overlay.py # 井间对比连线
│   │   │   ├── config.py          # 轨道配置类
│   │   │   ├── utils.py           # 便捷构建方法
│   │   │   ├── configs/           # 预置配置
│   │   │   ├── assets/patterns/   # 16 种 SVG 图案
│   │   │   └── web_dist/          # ECharts JS 打包
│   │   ├── pyproject.toml
│   │   └── README.md              # 包使用指南 + API 参考 + 示例
│   ├── geoviz_seismic/            # 独立地震可视化包 (pip installable)
│   │   ├── geoviz_seismic/
│   │   │   ├── renderer_3d.py     # pyqtgraph 3D 体渲染 + 交互切片
│   │   │   ├── seismic_view.py    # 组合 3D+2D+工具栏完整组件
│   │   │   ├── loader.py          # SEGY 按需切片 (segyio)
│   │   │   ├── profile_vd.py      # VD 热图渲染
│   │   │   ├── profile_wiggle.py  # Wiggle 波形渲染 (QPainter)
│   │   │   ├── profile_widget.py  # VD/Wiggle 统一切换
│   │   │   ├── horizon.py         # 层位解析 + nearest/RBF 填充
│   │   │   ├── colormap.py        # seismic/gray/jet/hsv 色标
│   │   │   ├── cache.py           # LRU 切片缓存
│   │   │   └── models.py          # SeismicVolumeMeta, SliceInfo 等
│   │   └── pyproject.toml
│   ├── geoviz_map/                # 独立地图可视化包 (pip installable)
│   │   ├── geoviz_map/
│   │   │   ├── canvas.py          # MapCanvas (QWidget 组合 layers)
│   │   │   ├── projection.py      # Web Mercator 投影
│   │   │   ├── viewport.py        # center+zoom → 像素映射
│   │   │   ├── zoom_pan.py        # 拖拽 + 滚轮缩放
│   │   │   ├── layers/            # 背景/网格/地块/标签/井点
│   │   │   └── models.py          # WellMarker, ReferenceLabel
│   │   └── pyproject.toml
│   └── geoviz_paleo_map/          # 独立古地理可视化包 (pip installable)
│       ├── geoviz_paleo_map/
│       │   ├── canvas.py          # PaleoMapCanvas (8 个 layer)
│       │   ├── projection.py      # Plate Carrée 投影
│       │   ├── viewport.py        # center+zoom → 像素映射
│       │   ├── zoom_pan.py        # 拖拽 + 滚轮缩放
│       │   ├── style.py           # FaciesStyleResolver
│       │   └── layers/            # 8 个渲染层
│       └── pyproject.toml
│   └── geoviz_cross_well/         # 独立连井对比包 (pip installable)
│       ├── geoviz_cross_well/
│       │   ├── canvas.py          # CrossWellCanvas + PickingOverlay
│       │   ├── tops_model.py      # FormationTopsModel (CSV I/O)
│       │   ├── picks_model.py     # HorizonPicksModel + UndoManager
│       │   ├── correlation_layer.py # CorrelationLayer (bezier ties)
│       │   ├── dtw_engine.py      # DTWEngine (banded DTW)
│       │   └── seismic_tie.py     # SeismicTie (checkshot T-D)
│       └── pyproject.toml
├── src/                           # 主应用代码
│   ├── main.py                    # 入口 (QApplication)
│   ├── app.py                     # MainWindow + 侧栏导航
│   ├── pages/                     # 页面 (每页独立文件夹)
│   │   ├── map/                   # 地图总览
│   │   │   ├── page.py            #   MapPage (MapLibre GL)
│   │   │   └── renderer.py        #   QWebEngineView + MapLibre
│   │   ├── paleo_map/             # 古地理图
│   │   │   ├── page.py            #   PaleoMapPage (调用 geoviz-paleo-map)
│   │   │   └── loader.py          #   CSV/Excel/GeoJSON 数据加载
│   │   ├── well_log/              # 井剖面 (UI 编排，调用 geoviz-well-log)
│   │   │   └── page.py
│   │   ├── cross_well/            # 连井对比
│   │   │   └── page.py
│   │   ├── seismic/               # 地震3D (薄封装 SeismicView)
│   │   │   └── page.py
│   │   ├── data/                  # 数据管理
│   │   │   └── page.py
│   │   └── tools/                 # 工具箱
│   │       └── page.py
│   ├── data/                      # 数据层
│   │   ├── loaders.py             # 数据加载器
│   │   ├── models.py              # Pydantic 模型
│   │   ├── cache.py               # 内存缓存
│   │   └── well_registry.py       # 井数据注册表
│   ├── utils/
│   │   └── constants.py           # 常量 (PATTERN_MAP re-export)
│   └── resources/                 # 图标、Qt 资源
├── data/                          # 井坐标、测井、地震数据
├── samples/                       # 示例 GeoJSON / 演示资源
├── tests/                         # pytest 测试
├── scripts/
│   ├── build.py                   # PyInstaller 打包脚本
│   └── build_with_conda.bat       # Windows + conda 构建脚本
├── docs/                          # 设计文档、方法论文档
│   ├── releases/                  # 各版本发布说明
│   └── screenshots/               # 文档配图统一目录
│       ├── references/            #   参考图、设计稿
│       └── qa/                    #   QA / 截图比对产物
└── archive/                       # 历史代码归档（不参与构建/引用）
    ├── README.md                  # 归档说明
    ├── scripts/                   # 早期一次性调试/验证脚本
    ├── web-echarts/               # 旧 ECharts 实验工程（更早完整 Web 架构见 v0.1-web tag）
    ├── web-deps/                  # 旧 Web 时代遗留的 package.json
    └── misc/                      # diff.txt、.coverage 等一次性产物
```

---

## Testing / 测试

| 框架 | 用途 |
|------|------|
| pytest | 数据模型、加载器、渲染器、轨道管理器单元测试 |
| pytest-qt | Qt 组件测试 (qtbot fixture) |

```bash
source .venv/bin/activate && pytest
```

---

## License

[MIT](LICENSE)
