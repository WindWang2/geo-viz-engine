# Task Plan: GeoViz Engine — 通用可视化与等值线插值渲染库规划
## Goal
规划并设计一个全新的通用可视化库 `geoviz_plots`（作为第 7 个独立子包），并基于 TDD 流程实现：
1. **通用二维数据可视化**（高品质线图、散点图，具备自动轴刻度、抗锯齿、交互缩放和平移、SVG/PDF 矢量导出）。
2. **空间散点数据插值与等值线/色斑图渲染**（支持 IDW 及 Scipy RBF/克里金/GridData 空间插值，Marching Squares / contourpy 等值线与多边形提取，QPainter 矢量级等值线与色斑面渲染，支持 CNPC 标准色标）。

该库遵循 GeoViz Engine 的轻量级、高可定制、出版级出图定位，采用 **PySide6 QPainter 纯矢量渲染** 技术路线，确保在高 DPR 和跨平台环境下保持绝对清晰。

## Current Phase
Phase 5: 整体集成与 Demo 方案规划 (COMPLETE)

## Phases

### Phase 1: 需求拆解与架构设计 (Requirements & Architecture)
- [x] 理解用户意图与核心痛点（线图 + 散点图 + 空间插值渲染）
- [x] 确定技术路线：采用 `QPainter` 纯矢量重绘，支持完美矢量导出。
- [x] 确定包名：`geoviz_plots` 及其内部目录架构。
- [x] 规划 API 接口规范与数据输入输出格式。
- [x] 在 `findings.md` 中记录设计规范。
- **Status:** complete

### Phase 2: 二维通用线图/散点图模块实现 (2D Plotting Module)
- [x] 实现 `PlotWidget` (基于 QPainter) 的双轴自适应刻度标定算法（Heckbert's nice ticks）。
- [x] 实现线图（Line Series）、散点图（Scatter Series）数据结构与 NaNs 过滤。
- [x] 引入 **数据降采样算法 (LTTB - Largest-Triangle-Three-Buckets)**，解决 $100K+$ 大量测点 QPainter 渲染流畅度瓶颈，确保在 60+ FPS。
- [x] 实现 **联动高亮接口 (Interactive Linking API)**，支持 `point_selected` 信号及 `highlight_point` 双向联动。
- [x] 实现缩放与平移（Zoom & Pan）交互设计，支持鼠标滚轮在光标处缩放与左/中键拖拽平移。
- [x] 实现 SVG/PDF 矢量画布重定向导出逻辑。
- **Status:** complete

### Phase 3: 空间散点数据插值模块实现 (Spatial Interpolation)
- [x] 设计三维散点 $(x_i, y_i, z_i)$ 插值引擎接口。
- [x] 实现快速 **反距离权重算法 (IDW, Inverse Distance Weighting)** 及其 NumPy 向量化广播。
- [x] 实现 **Scipy GridData & RBF 插值** 封装，支持 linear, cubic, nearest-neighbor, RBF 方法。
- [x] 引入 **`QThread` 异步计算机制 (`InterpolationWorker`)**，将插值计算从 GUI 主线程剥离，防止 UI 出现假死或卡顿。
- [x] 实现 **NaN 数据清洗与外插凸包遮罩 (Convex Hull Masking)**，防止无效物理测点导致插值曲面发散。
- **Status:** complete

### Phase 4: 等值线与色斑图面渲染模块实现 (Contour & Surface Rendering)
- [x] 实现等值多边形与等值线高效率提取（基于 `contourpy` 拓扑路径提取）。
- [x] 实现 `SurfaceWidget` 的多维矢量渲染：
  - **色斑图填充 (Filled Contours)**：使用 `QPainterPath` 的多圈（OuterOffset / OddEvenFill）闭合填充，完美渲染带孔的多边形。
  - **等值线绘制 (Contour Lines)**：平滑的矢量 isoline 连线绘制。
  - **断口标签标注 (Contour Labels)**：基于文本宽度与走向切线向量，自动将等值线进行打断并留白绘制 rotated text。
- [x] 集成 **中石油 (CNPC) 地质图件标准色标库**（`cnpc_strat` 及 `cnpc_fluid`）。
- **Status:** complete

### Phase 5: 整体集成与测试 (Integration & Testing)
- [x] 编写全面的 TDD 测试套件 `tests/test_geoviz_plots.py`（包含 Axis  ticks、IDW 插值、Scipy 插值与 Mask 覆盖、LTTB 采样、PlotWidget 交互、InterpolationWorker 异步信号以及 Contour 路径解析等 15 个独立测试场景）。
- [x] 执行 pytest 获得 15/15 green。
- [x] 全量测试套件执行通过（702 passed tests）。
- **Status:** complete

---

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| **新建 `geoviz_plots` 子包** | 保持高内聚低耦合的子包架构，独立升级发布。 |
| **纯 QPainter 矢量化渲染路径** | 满足出版级（Publish-grade）的高清出图要求，支持完美无损 PDF/SVG 矢量导出。 |
| **NumPy 向量化计算 IDW 空间插值** | 通过矩阵广播彻底消除 Python 循环，实现毫秒级超快插值重算。 |
| **Matplotlib / contourpy 矢量路径提取** | 完美处理复杂的地质盆地/高地嵌套关系，避免手写行进多边形的多环岛屿嵌套 bug。 |
| **QThread 异步封装计算** | 将空间计算委托给独立计算线程，避免 GUI 假死。 |
