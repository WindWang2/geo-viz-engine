# GeoViz Engine — 地质数据可视化桌面引擎

![PySide6](https://img.shields.io/badge/PySide6-6.6+-41CD52?logo=qt)
![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python)
![pyqtgraph](https://img.shields.io/badge/pyqtgraph-0.13+-2CA5E0)
![PyVista](https://img.shields.io/badge/PyVista-0.43+-5896FF)
![License](https://img.shields.io/badge/License-MIT-green)

面向地质工程师和科研人员的**跨平台桌面应用**，提供测井数据可视化、井位地图、地震体三维显示等功能。

> **v0.1-web** (Tauri + React + FastAPI 架构) 已归档于 git tag `v0.1-web`。

---

## About / 项目简介

GeoViz Engine 是一款基于 **PySide6 + pyqtgraph + PyVista** 的单进程地质数据可视化桌面应用：

- **UI 框架（PySide6/Qt）**：窗口管理、页面导航、文件对话框、表格展示
- **2D 渲染（pyqtgraph + QGraphicsScene）**：测井曲线、岩性柱、沉积相综合柱状图
- **3D 渲染（PyVista/VTK）**：地震体三维显示、任意方向剖面、等值面提取
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
│  │ 侧栏 │  QStackedWidget (4 页面)                  │    │
│  │      │                                          │    │
│  │ 🗺   │  MapPage     QWebEngineView + MapLibre   │    │
│  │ ⛏   │  WellLogPage pyqtgraph + QGraphicsScene   │    │
│  │ 🧊   │  SeismicPage PyVista + VTK               │    │
│  │ 📁   │  DataPage    QTableWidget + 文件对话框     │    │
│  │      │                                          │    │
│  └──────┴──────────────────────────────────────────┘    │
│                                                         │
│  data/  loaders (lasio, segyio, openpyxl)               │
│         models (Pydantic)   cache (内存缓存)             │
└─────────────────────────────────────────────────────────┘
```

### Tech Stack / 完整技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| UI 框架 | PySide6 6.6+ | 桌面窗口、导航、控件 |
| 2D 曲线 | pyqtgraph 0.13+ | 测井曲线 GPU 加速渲染 |
| 2D 岩性 | QGraphicsScene + SVG | 岩性柱、沉积相 SVG 花纹填充 |
| 地图 | MapLibre GL (QWebEngineView) | 井位地图、交互选井 |
| 3D 渲染 | PyVista 0.43+ / VTK | 地震体三维显示、剖面切片 |
| 测井数据 | lasio 0.14+ | LAS 格式解析 |
| 地震数据 | segyio 1.9+ | SEG-Y 格式解析 |
| Excel 解析 | python-calamine | 基于 Rust 的极速表格数据解析引擎 |
| 数据处理 | pandas 2.x / numpy 1.26+ | 表格数据、数值计算 |

---

## Features / 功能模块

### 井剖面 — 综合测井解释图

- **混合渲染**：测井曲线使用 pyqtgraph（GPU 加速，万级数据点流畅），岩性/沉积相使用 QGraphicsScene + SVG 花纹填充
- **多轨道编排**：chart_engine 统一管理深度、曲线、岩性、沉积相等轨道的水平布局和滚动同步
- 6 种岩性 SVG 花纹（砂岩、粉砂岩、泥岩、页岩、灰岩、白云岩）— GB/T 附录M
- 10 种沉积相 SVG 纹理（潮坪、陆棚、砂坪等）— GB/T 附录O

### 连井对比 — 地层与构造剖面

- **智能相连通**：基于层序地层学骨架（Sequence/Member），自动跨井追踪并绘制彩色沉积相连通多边形。
- **全画幅视口同步**：多口井的滚动与缩放实现毫秒级锁步（Lock-step）联动。
- **双重对齐模式**：
  - **地层拉平**：选择任意层序顶面作为基准线，动态计算深度补偿，实现水平拉平展示。
  - **海拔 (TVDSS) 对齐**：自动提取补心高，按绝对海拔真实还原构造起伏。
- **超宽 SVG 导出**：支持一键将包含多口井曲线、岩性及井间彩色连通带的完整长卷剖面，无缝缝合并导出为高清 SVG 矢量图。
- **小地图联动**：右下角悬浮地图实时展示连井剖面的地理走向与经纬度分布。

### 地图总览

- 57 口真实井位坐标（EPSG:4326/WGS84），MapLibre GL 暗色底图
- 井位点击 → Qt WebChannel 信号 → 切换到井剖面页面

### 地震 3D

- SEGY 文件加载（segyio）→ PyVista UniformGrid → 三维体渲染
- 任意方向切片（inline/crossline/timeline）
- 等值面提取、层位显示
- 交互旋转/缩放/拾取

### 数据管理

- 文件导入：Excel (.xlsx)、LAS (.las)、SEGY (.sgy)
- 极速缓存：采用 Rust Calamine 引擎 + Pickle 二进制缓存，实现数十万点 Excel 数据 10毫秒级“秒开”。
- 井位坐标表格展示

---

## Roadmap / 开发路线图

| 阶段 | 状态 | 内容 |
|------|------|------|
| v0.1-web | ✅ 已归档 | Tauri+React+FastAPI Web 架构 (tag: v0.1-web) |
| Phase 1 | ✅ 已完成 | PySide6 骨架、导航、单井剖面、地图、地震3D、数据管理 |
| Phase 2 | ✅ 已完成 | 多井对比、相变连通模型、地层拉平、TVDSS对齐、全画幅SVG导出、Calamine解析加速 |
| Phase 3 | 📋 待规划 | LAS 上传与解析、层序地层分析工具、交互编辑连线 |
| Phase 4 | 📋 待规划 | 地震属性分析、井震结合 |

---

## Quick Start / 快速开始

### 前置条件

- Python 3.12+
- 系统依赖：OpenGL 驱动（PyVista/VTK 需要）

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
├── src/                        # 主应用代码
│   ├── main.py                 # 入口 (QApplication)
│   ├── app.py                  # MainWindow + 侧栏导航
│   ├── pages/                  # 4 个页面
│   │   ├── map_page.py         # 地图总览 (MapLibre GL)
│   │   ├── well_log_page.py    # 井剖面 (pyqtgraph + SVG)
│   │   ├── seismic_page.py     # 地震3D (PyVista)
│   │   └── data_page.py        # 数据管理
│   ├── renderers/              # 渲染组件
│   │   ├── well_log/           # 井剖面渲染器
│   │   │   ├── chart_engine.py       # 多轨道编排
│   │   │   ├── curve_renderer.py     # pyqtgraph 曲线
│   │   │   ├── lithology_renderer.py # QGraphicsScene 岩性
│   │   │   ├── facies_renderer.py    # QGraphicsScene 沉积相
│   │   │   └── depth_renderer.py     # 深度刻度
│   │   ├── map_renderer.py     # QWebEngineView + MapLibre
│   │   └── seismic_renderer.py # PyVista 3D
│   ├── data/                   # 数据层
│   │   ├── loaders.py          # lasio/segyio/openpyxl
│   │   ├── models.py           # Pydantic 数据模型
│   │   └── cache.py            # 内存缓存
│   ├── patterns/               # SVG 图案 (岩性 + 沉积相)
│   └── resources/              # 图标、Qt 资源
├── data/                       # 井坐标、测井、地震数据
├── tests/                      # pytest 测试
├── scripts/
│   └── build.py                # PyInstaller 打包脚本
└── docs/                       # 设计文档、方法论文档
```

---

## Testing / 测试

| 框架 | 用途 |
|------|------|
| pytest | 数据模型、加载器、渲染器单元测试 |
| pytest-qt | Qt 组件测试 (qtbot fixture) |

```bash
source .venv/bin/activate && pytest
```

---

## License

[MIT](LICENSE)
