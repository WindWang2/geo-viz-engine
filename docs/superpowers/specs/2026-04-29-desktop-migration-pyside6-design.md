# GeoViz Engine 桌面版迁移设计

## 背景

当前架构为三层 Web 桌面应用：Tauri 2 (Rust) + React 18 + FastAPI (Python)。存在以下痛点：

- **打包复杂**：Python sidecar 打包未实现，三层架构构建流程重
- **开发体验差**：三层 IPC 通信、Token 认证、双渲染系统（Canvas2D + D3/SVG），维护成本高
- **性能不足**：Web 渲染（D3/Canvas/MapLibre）处理大量地质数据时受限
- **未来需求**：3D 地震体和剖面显示（大数据量），Web 端难以胜任

Web 版本已打 tag `v0.1-web` 保存。

## 决策：迁移至 PySide6 单进程桌面架构

### 核心变化

| | 旧架构 (Web) | 新架构 (PySide6) |
|---|---|---|
| 进程数 | 3 (Tauri + React + FastAPI) | 1 |
| IPC | 2次 (Tauri→React→FastAPI) | 0 |
| 认证 | Token (X-API-Token) | 无需 |
| 语言 | Rust + TypeScript + Python | Python |
| 3D 能力 | Three.js (WebGPU 未成熟) | PyVista + VTK (工业级) |

## UI 设计

### 布局：现代简洁风格 (VSCode 风格)

- 左侧 48px 图标导航栏（4个入口）
- 顶部面包屑 + 页面标题
- 主工作区全宽展示

### 导航页面

| 图标 | 页面 | 说明 |
|------|------|------|
| 地图 | 地图总览 | 井位分布、底图、点击井位进入详情 |
| 井 | 井剖面 | 测井曲线、岩性柱、沉积相等综合柱状图 |
| 立方体 | 地震3D | 3D地震体、任意方向剖面、层位追踪 |
| 数据库 | 数据管理 | 数据导入/导出、项目管理、设置 |

## 渲染方案

### 井剖面：混合渲染

- **测井曲线**：pyqtgraph (MIT) — GPU 加速，万级数据点实时交互
- **岩性柱/沉积相**：QGraphicsScene + SVG 填充 — 复用现有 16 个岩性 SVG + 10 个沉积相 SVG 图案
- **深度刻度**：pyqtgraph ViewBox 自定义轴
- **编排**：chart_engine.py 统一管理多轨道布局和滚动同步

两套渲染器共享 Qt 坐标系，比 Web 端 Canvas2D + D3/SVG 双系统简单得多。

### 地图：QWebEngineView + MapLibre GL

轻量地图需求，用 QWebEngineView 嵌入 MapLibre GL JS。可复用现有 MapLibre 配置，井位点击通过 Qt WebChannel 信号回传 Python。

### 地震3D：PyVista + VTK

全功能 3D 地震显示：
- SEGY 体数据加载 (segyio → numpy → PyVista UniformGrid)
- 任意方向切片 (inline/crossline/timeline)
- 等值面提取
- 层位显示与追踪
- 交互旋转/缩放/拾取

## 数据层

| 数据类型 | 加载库 | 说明 |
|----------|--------|------|
| 测井 (.las) | lasio | Python 唯一成熟的 LAS 格式库 |
| 地震 (.sgy) | segyio | SEG-Y 标准读写库 |
| Excel/表格 | openpyxl + pandas | 复用现有数据格式 |
| 井坐标 | JSON (标准库) | 复用 well_coordinates.json |
| XML 井数据 | lxml 或标准库 xml.etree | 复用现有 XML 数据 |

## 项目结构

```
src/
├── main.py                 # 入口，QApplication
├── app.py                  # MainWindow + 图标导航
├── pages/
│   ├── map_page.py         # 地图总览页
│   ├── well_log_page.py    # 井剖面页
│   ├── seismic_page.py     # 地震3D页
│   └── data_page.py        # 数据管理页
├── renderers/
│   ├── well_log/
│   │   ├── curve_renderer.py     # pyqtgraph 曲线
│   │   ├── lithology_renderer.py # QGraphicsScene 岩性
│   │   ├── facies_renderer.py    # QGraphicsScene 沉积相
│   │   ├── depth_renderer.py     # 深度刻度
│   │   └── chart_engine.py       # 多轨道编排
│   ├── map_renderer.py           # QWebEngineView + MapLibre
│   └── seismic_renderer.py       # PyVista 3D
├── data/
│   ├── loaders.py          # lasio/segyio/openpyxl 加载
│   ├── models.py           # Pydantic 数据模型
│   └── cache.py            # 内存缓存
├── patterns/               # SVG 图案资源 (复用现有)
└── resources/              # 图标、qrc 资源
data/                       # 井坐标、测井、地震数据
tests/
pyproject.toml
scripts/
└── build.py                # PyInstaller 打包脚本
```

## 数据流

### 井剖面

文件选择 → loaders.py (lasio/openpyxl) → models.py (验证) → chart_engine.py (编排轨道) → curve_renderer + lithology_renderer (并行绘制) → 显示

### 地震3D

SEGY 文件 → loaders.py (segyio) → numpy 数组 → PyVista UniformGrid → 剖面切片/等值面 → 交互旋转/缩放

### 地图

well_coordinates.json → MapLibre GL (JS) → QWebEngineView 嵌入 → 点击井位 → WebChannel 信号回 Python → 切换井剖面页

## 核心依赖

| 依赖 | 版本 | 许可证 | 用途 |
|------|------|--------|------|
| PySide6 | 6.6+ | LGPL | UI 框架 |
| pyqtgraph | 0.13+ | MIT | 2D 曲线渲染 |
| PyVista | 0.43+ | MIT | 3D 地震渲染 |
| VTK | 9.3+ | BSD | PyVista 底层 |
| lasio | 0.14+ | MIT | LAS 测井格式 |
| segyio | 1.9+ | BSD | SEG-Y 地震格式 |
| pandas | 2.x | BSD | 数据处理 |
| numpy | 1.26+ | BSD | 数值计算 |
| PyInstaller | 6.x | GPL | 打包分发 |

## 打包方案

使用 PyInstaller 生成单目录或单文件分发：
- 输出：可执行文件 + 依赖目录
- VTK/PyVista 需额外配置 hidden imports
- 预估大小：~200-300MB（含 VTK 运行时）
- 跨平台：Windows / Linux / macOS

## 迁移策略

从零搭建 PySide6 项目，逐步迁移功能：

1. 骨架：MainWindow + 图标导航 + 页面切换
2. 井剖面：chart_engine + curve_renderer + lithology_renderer
3. 地图：QWebEngineView + MapLibre + 井位交互
4. 数据管理：文件加载 + 表格显示
5. 地震3D：segyio 加载 + PyVista 渲染 + 剖面交互

每个阶段独立可运行，不依赖旧代码。
