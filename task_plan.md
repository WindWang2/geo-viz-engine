# Task Plan: GeoViz Engine — 项目总览与下一步规划

> **更新于 2026-07-04**：Phase 28（连井多曲线叠置 v0.14.0）、Phase 29-A/B/C（3D 高斯雕刻、矢量排版、等值线断层屏障 v0.17.0）、Phase 30（井震精细标定工作台 v0.18.0）、Phase 31（交叉图分析与岩性聚类工具箱 v0.19.0）已全面完成并通过 100% 单元/集成测试。

## Goal
GeoViz Engine 是一款基于 PySide6 的桌面地质数据可视化引擎。当前绝大部分功能已完成，900+ tests passed。**核心市场定位**：科研院所 + 中小油田 + 教学（差异化于 Petrel 的轻量、可二次开发、出版级出图）。

## Current State
- **Tests:** 全量单元与集成测试套件通过（含 40 项 Phase 28-31 专项与集成测试）。
- **Active phase:** Phase 31 交叉图分析与岩性聚类工具箱已合入完成 (v0.19.0)
- **Health rating:** A+（功能完整，连井/3D地震/矢量排版/井震标定/交叉图聚类已合入，全量测试与代码审查通过）


## Completed Phases

| Phase | Content | Status | Note |
|-------|---------|--------|------|
| 1-10 | 基础架构、连井、测井、地震、属性、图件导出等 | ✅ | |
| 11-18 | 曲率、GPU加速、修复、通用图表、性能优化等 | ✅ | |
| 20-27 | UI 视觉/交互全量升级 (Azurite) 与全量审计修复 | ✅ | |
| 28 | 连井多曲线叠置与交互分层吸附拾取 (v0.14.0) | ✅ | |
| 29-A | 3D 地震层位曲面交互高斯雕刻与属性贴图 (v0.15.0) | ✅ | |
| 29-B | 出版级矢量图件排版与标准出图引擎 (v0.16.0) | ✅ | |
| 29-C | 通用 3D 曲面与等值线交互控制与断层屏障 (v0.17.0) | ✅ | |
| 30 | 独立井震精细标定工作台与矢量报告导出 (v0.18.0) | ✅ | |
| 31 | 交叉图分析与岩性聚类工具箱 (v0.19.0) | ✅ | |





---

## 🔍 CEO & ENG 深度审视 (Review of Phase 19)

**核心目标匹配度分析**：
项目定位为“科研院所 + 中小油田 + 教学”，并主打“出版级出图”。已完成的 Phase 19 高阶可视化增强，完全契合这一目标：
- 3D 雕刻与梯度光照（19.1, 19.2）为科研与教学提供了极具表现力的视觉工具。
- 动态防碰撞标注与 LOD（19.3, 19.4）是 GIS 出版级图件的硬性专业要求，解决密集数据不可读的痛点。

### 🤵 CEO Review
> "Phase 19 的圆满完成标志着 GeoViz Engine 已经具备了挑战专业商业地质软件的视觉底蕴。3D 雕刻和阴影效果极大提升了汇报演示的‘高级感’，而防碰撞标注和 LOD 则是我们作为‘出版级制图引擎’的门面。这块拼图的补齐让我们在科研汇报和油田部署中更具竞争力。"

### 👨‍💻 ENG Review
> "技术实现总结：
> - **19.1 & 19.2**: 通过 GLSL Shader 实时处理 discard 和梯度光照，保持了极高的帧率，同时实现了复杂的体切除逻辑。
> - **19.3 & 19.4**: 引入了 R-Tree 式的碰撞检测逻辑（CollisionDetector）和 RDP 简化算法，大幅优化了密集矢量图层的绘制性能和视觉清晰度。
> - **19.5**: 实现了自适应笔刷缩放，解决了传统 GIS 缩放时岩性花纹消失或过大的痛点。"

---

## ✅ 已完成：Phase 19 逐项 TDD 开发 (Completed)

| ID | Task | Files | Priority | Status |
|----|------|-------|----------|--------|
| 19.1 | **3D 地层雕刻 (Horizon Sculpting)**: 基于层位曲面的体数据实时切除（GLSL discard）。 | `geoviz_seismic/renderer_3d.py`, Shader 源码 | 🔴 P0 | ✅ DONE |
| 19.2 | **3D 梯度光照 (Hillshading)**: GPU 端实时计算地震反射面 3D 梯度与阴影。 | `geoviz_seismic/renderer_3d.py` | 🔴 P0 | ✅ DONE |
| 19.3 | **地图防碰撞动态标注 (Collision-aware Labeling)**: 井位和区域标注防重叠。 | `geoviz_map/layers/`, `geoviz_paleo_map/` | 🟡 P1 | ✅ DONE |
| 19.4 | **视口相关矢量路径简化 (LOD)**: 根据比例尺自动简化边界多边形以提升性能。 | `geoviz_paleo_map/layers/` | 🟡 P1 | ✅ DONE |
| 19.5 | **自适应颗粒纹理缩放**: 岩性 SVG 颗粒大小随视口缩放动态调整。 | `PatternEngine`, `geoviz_paleo_map/` | 🟢 P2 | ✅ DONE |

---

## 📦 Packages
| Package | 功能 | 健康度 |
|---------|------|--------|
| geoviz-well-log | ECharts SVG 测井渲染 | ✅ |
| geoviz-seismic | pyqtgraph OpenGL + 属性 | ✅ |
| geoviz-map | QPainter 井位地图 | ✅ |
| geoviz-paleo-map | QPainter 古地理图 + 编辑 | ✅ |
| geoviz-cross-well | 连井对比 | ✅ |
| geoviz-well-tie | 井震结合 — 纯 NumPy | ✅ |
| geoviz-plots | 通用图表与等值线插值渲染 | ✅ |

---

## Phase 26: 全量代码深度审计修复 (Deep Audit Fix)

> 基于 2026-06-03 6-agent 并行逐行审计，发现 9 Critical + 17 High + 18 Medium 问题。

### 26-A — CRITICAL 运行时崩溃修复 (7 项)

| ID | 文件 | 问题 | Status |
|----|------|------|--------|
| 26-A1 | `geoviz_well_log/chart_engine.py:131` | import 不存在的 `utils.py` → `render_well_log_data()` 崩溃 | ✅ |
| 26-A2 | `geoviz_well_log/connection_overlay.py:16` | `_well_names` 未在 `__init__` 初始化 → `AttributeError` | ✅ |
| 26-A3 | `geoviz_seismic/renderer_3d.py:179` | `_uploadHorizonTexture()` 复制粘贴重置 shading → 光照静默关闭 | ✅ |
| 26-A4 | `geoviz_seismic/loader.py:85` | 异常处理引用未赋值 `f` → `UnboundLocalError` 掩盖原始错误 (3处) | ✅ |
| 26-A5 | `geoviz_seismic/well_tie_panel.py:130` | Auto-Tie 按钮未连接 slot → 完全无功能 | ✅ |
| 26-A6 | `src/pages/cross_well/page.py:449` | `self.canvas` 应为 `self._canvas` → Escape 键崩溃 | ✅ |
| 26-A7 | `src/main.py:241` | `time.sleep(1.0)` 阻塞主线程 → 启动动画冻结 | ✅ |

### 26-B — HIGH 数据正确性修复 (8 项)

| ID | 文件 | 问题 | Status |
|----|------|------|--------|
| 26-B1 | `geoviz_seismic/renderer_3d.py:88,184` | `setShading` 重复定义 | ✅ (26-A3 一并修复) |
| 26-B2 | `geoviz_seismic/renderer_3d.py:686` | `clean()` 不释放 horizon/normal 纹理 → GPU 内存泄漏 | ✅ |
| 26-B3 | `geoviz_cross_well/correlation_layer.py:22` | `hash()` 非确定性 → 每次运行颜色不同 | ✅ |
| 26-B4 | `geoviz_cross_well/tops_model.py:42` | 同上 | ✅ |
| 26-B5 | `geoviz_plots/interpolation/idw.py:29` | 空输入返回 zeros 而非 NaN | ✅ |
| 26-B6 | `geoviz_plots/chart/axes.py:14` | `nice_number` 负数崩溃 | ✅ |
| 26-B7 | `geoviz_paleo_map/layers/region_labels.py` | `visible_labels` 未初始化 | ✅ |
| 26-B8 | `src/data/loaders.py:357` | `line_style` 计算后未传入 CurveData | ✅ |

### 26-C — MEDIUM 代码清理 (8 项)

| ID | 问题 | Status |
|----|------|--------|
| 26-C1 | 删除未使用导入 (QtOpenGL, QColor) + 未使用变量 (sqrt_n, t_max) | ✅ |
| 26-C2 | 归档 `src/pages/cross_well/scene_page.py` (598行死代码) + 测试 | ✅ |
| 26-C3 | 归档 `geoviz_well_log/modules.py` + 删除 `tests/test_modules.py` | ✅ |
| 26-C4 | 删除 `vispy` 死依赖 | N/A (不在依赖中) |
| 26-C5 | `main.py` DEBUG print 语句 | 保留 (PyInstaller 部署诊断, stderr-only) |
| 26-C6 | `export_professional.py` 死函数 (3个) + `color_mode` 参数 | 保留 (制图基础设施, 可后续接入) |
| 26-C7 | `CompositePickCmd` 死代码 | 保留 (复合撤销模式, 可后续使用) |
| 26-C8 | 更新文档 | ✅ (见下方) |

---

## Phase 27: UI Redesign Pass 2 — 布局重构与视觉精修

> 基于 UI.html 方案A (蓝铜) 设计参考，进行第二轮全面 UI 调整。
> 设计规范：`docs/superpowers/specs/2026-06-03-ui-redesign-pass2-design.md`

### 设计决策

| 决策项 | 选择 | 说明 |
|--------|------|------|
| 布局方向 | **方案B：可折叠侧边栏 + 全出血内容** | 200px 展开 ↔ 56px 折叠，IDE 风格 |
| 侧边栏默认 | **默认展开 + 可折叠** | ☰ 按钮触发折叠，QSettings 记忆状态 |
| Header | **精修当前 Header** | 48px 高度，集成搜索栏 ⌘K，通知铃铛 |
| Footer | **信息增强** | 32px，GPU 信息、缓存大小、技术数据等宽字体 |
| 内容页面 | **全部 8 页** | 地图、古地理、井剖面、连井、地震3D、平面图件、数据、工具 |

### 27-A — 主框架重构 (3 项)

| ID | Task | Files | Status |
|----|------|-------|--------|
| 27-A1 | **可折叠侧边栏**：200px↔56px 动画过渡，☰ 触发，QSettings 记忆，折叠态 tooltip | `src/app.py` | ✅ |
| 27-A2 | **Header 精修**：48px 高度，SVG logo+渐变文字，⌘K 搜索栏，通知铃铛按钮 | `src/app.py` | ✅ |
| 27-A3 | **Footer 增强**：32px 高度，GPU/缓存信息，技术数据等宽字体，分段分隔线 | `src/app.py` | ✅ |

### 27-B — 设计系统 Token (1 项)

| ID | Task | Files | Status |
|----|------|-------|--------|
| 27-B1 | **全局样式 Token**：8px 间距网格、4 级圆角 (6/8/12/16px)、3 级阴影、150-300ms 动画 | `src/main.py` → `src/utils/global_style.py` | ✅ |

### 27-C — 内容页面适配 (8 项)

| ID | Task | Files | Status |
|----|------|-------|--------|
| 27-C1 | **地图页**：左面板 260px、井列表 8px 圆角+hover、筛选 chip 6px 圆角、浮动控件 L1 阴影 | `src/pages/map/page.py` | ✅ |
| 27-C2 | **古地理页**：编辑面板布局统一、图层控件圆角 | `src/pages/paleo_map/page.py` | ✅ |
| 27-C3 | **井剖面页**：Track header 8px 圆角、拖拽手柄视觉、滚动条 8px 圆角 | `src/pages/well_log/page.py` | ✅ |
| 27-C4 | **连井对比页**：多井布局统一间距、拾取覆盖层光标反馈、关联线平滑贝塞尔 | `src/pages/cross_well/page.py` | ✅ |
| 27-C5 | **地震 3D 页**：切片控件分组面板、色标条 L2 阴影、工具栏统一 Header 风格 | `src/pages/seismic/page.py` | ✅ (已符合) |
| 27-C6 | **平面图件页**：控件面板布局统一 | `src/pages/plots/page.py` | ✅ |
| 27-C7 | **数据管理页**：表格样式统一 | `src/pages/data/page.py` | ✅ |
| 27-C8 | **工具箱页**：工具卡片布局统一 | `src/pages/tools/page.py` | ✅ (已符合) |

### Phase 28: 连井多曲线叠置与交互分层拾取 (v0.14.0)

> 基于 2026-07-04 设计规范与实施计划，完成连井模块多曲线并排刻度、自动吸附与右侧面板交互增强。

| ID | Task | Files | Status |
|----|------|-------|--------|
| 28-A1 | **多刻度表头渲染**：单 Track 内 $K$ 条曲线宽度等分，并排彩色上下限刻度 | `geoviz_well_log/renderer/curve_track.py` | ✅ |
| 28-B1 | **特征极值自动吸附**：$\pm 1.5\text{m}$ 窗口内峰值/谷值自动吸附与深度修正 | `geoviz_cross_well/canvas.py` | ✅ |
| 28-B2 | **悬停吸附实时预览**：鼠标悬停吸附深度虚线与曲线圆点高亮 feedback | `geoviz_cross_well/canvas.py` | ✅ |
| 28-C1 | **右侧可折叠控制面板**：层位管理、吸附模式/窗口、测井曲线叠置勾选 | `src/pages/cross_well/sidebar.py` | ✅ |
| 28-C2 | **页面整合与轨道重建**：280px ↔ 0px 动画折叠与曲线分组变更重构 | `src/pages/cross_well/page.py` | ✅ |

### Phase 29-A: 3D 地震层位曲面交互编辑与体数据属性增强 (v0.15.0)

> 基于 2026-07-04 设计规范与实施计划，实现 3D 射线解算、高斯笔刷局部实时拉伸、ROI 撤销补丁与 GLSL 双重采样贴图。

| ID | Task | Files | Status |
|----|------|-------|--------|
| 29-A1 | **3D 射线求交与网格解算**：逆 MVP 矩阵解算 3D 射线与高程网格求交 | `geoviz_seismic/horizon.py` | ✅ |
| 29-A2 | **高斯变形引擎与 ROI 撤销系统**：NumPy 向量化高斯衰减与轻量 ROI 差异补丁 | `geoviz_seismic/horizon.py` | ✅ |
| 29-A3 | **`InteractiveHorizonGLItem` 渲染**：3D 光标圈、GLSL 双重采样与 VBO 更新 | `geoviz_seismic/interactive_horizon.py` | ✅ |
| 29-A4 | **单元与集成测试套件**：高斯衰减、射线求交、撤销/重做与 OpenGL Item 测试 | `tests/test_seismic_3d_sculpting.py` | ✅ |

### Phase 29-B: 出版级矢量图件排版与标准出图引擎 (v0.16.0)

> 基于 2026-07-04 设计规范与实施计划，实现 WYSIWYG A4/A3/A2 纸张画布、双模板切换（国标规范 vs 学术期刊）、8点手柄交互拖拽与 300 DPI 矢量 PDF/SVG 导出。

| ID | Task | Files | Status |
|----|------|-------|--------|
| 29-B1 | **纸张画布 Scene 与交互图元基类**：A4/A3/A2 尺寸解算与 8 点手柄选择框 | `geoviz_paleo_map/cartography/scene.py`, `items/base_item.py` | ✅ |
| 29-B2 | **国标勘探责任表与多列图例图元**：三栏责任表与多列自动折行图例 | `geoviz_paleo_map/cartography/items/title_block_item.py`, `legend_item.py` | ✅ |
| 29-B3 | **双预设模板与 Cartography Layout Editor**：`GB_EXPLORATION_SPEC` 与 `ACADEMIC_JOURNAL` 预排版 | `geoviz_paleo_map/cartography/templates.py`, `window.py` | ✅ |
| 29-B4 | **300 DPI 矢量 PDF 与 SVG 导出管道**：基于 `QPrinter` 与 `QSvgGenerator` 的无损渲染导出 | `geoviz_paleo_map/cartography/window.py` | ✅ |
| 29-B5 | **单元与集成测试套件**：尺寸计算、模板渲染与 PDF/SVG 文件导出测试 | `tests/test_cartography_layout.py` | ✅ |

### 设计系统规范摘要

**间距 (8px Grid)**：xs=4, sm=8, md=12, lg=16, xl=24

**圆角**：sm=6px (chip), md=8px (button/input/sidebar), lg=12px (card/panel), xl=16px (modal)

**阴影**：L1=`0 1px 3px rgba(0,0,0,0.08)` (hover), L2=`0 2px 8px rgba(0,0,0,0.1)` (panel), L3=`0 8px 24px rgba(0,0,0,0.15)` (modal)

**动画**：fast=150ms (hover), normal=200ms (sidebar/page), slow=300ms (modal), easing=ease

**色板 (Azurite)**：Primary #1f66d4, Background #faf9f5, Surface #ffffff, Border #e5eaf1, Hover #f1f4f9, Active #e9effa



