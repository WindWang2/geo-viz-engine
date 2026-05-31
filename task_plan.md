# Task Plan: GeoViz Engine — 项目总览与下一步规划

> **更新于 2026-05-31**：基于 CEO + Eng 双重 review 重写。明确区分"已完成 / 待修复 / 下一步"。

## Goal
GeoViz Engine 是一款基于 PySide6 的桌面地质数据可视化引擎。Phase 1–11 已完成，636 tests passed。**核心市场定位**：科研院所 + 中小油田 + 教学（差异化于 Petrel 的轻量、可二次开发、出版级出图）。

## Current State
- **Branch:** main (synced with origin)
- **Tests:** 636 passed, 3 skipped (3 skipped 待整改为 xfail+断言)
- **Latest commit:** `86da1b14 feat(seismic): add Phase 11 curvature attributes`
- **Active phase:** Phase 11 COMPLETE（有 1 个诚信缺陷待修复，见 Phase 11.5）
- **Health rating (Eng review):** B+（健康可生产，少量明确债务）

## Completed Phases

| Phase | Content | Status | Note |
|-------|---------|--------|------|
| 1 | PySide6 骨架、导航、单井剖面、地图、地震3D、数据管理 | ✅ | |
| 2 | 多井对比、相变连通、地层拉平、TVDSS对齐、SVG导出 | ✅ | |
| 3 | 测井引擎独立化、轨道管理器、矢量导出、AI预测集成 | ✅ | |
| 4 | 地震可视化独立化、3D体渲染+2D剖面、SEGY按需切片 | ✅ | |
| 5 | 连井对比拾取工作流（DTW、地震校深） | ✅ | |
| 6 | 地震属性分析（5属性+色标）、沿层位提取 | ✅ | |
| 7 | STFT谱分解、RGB属性融合、属性交叉图 | ✅ | |
| 8 | 井震结合可视化集成（WellTiePanel + auto-tie + overlay） | ✅ | |
| A7 | CheckshotTable → WellTieCalibration 委托去重 | ✅ | |
| 9 | Coherence (C3 eigenstructure) 相干属性 | ✅ | 含真实 GPU 路径 |
| 9b | GPU Acceleration for Coherence | ✅ | 1.5-1.9x speedup |
| 10 | PaleoMap 纹理填充 + 专业图件导出 | ✅ | 13 facies patterns |
| Refactor | seismic_view.py 拆分 | ✅ | 1471 → 1283 行 |
| 11 | Curvature (Dip/Azimuth + 6 kinds) | ⚠️ | GPU 路径未实现（见 11.5） |

## 🔴 Phase 11.5: 收尾与债务清理（最高优先级，必须先于 Phase 12）

**目的：** 修复 Phase 11 遗留的工程债务，恢复 task_plan 与代码的诚信。

### Tasks

| ID | Task | Files | Priority | Status |
|----|------|-------|----------|--------|
| 11.5-A | **实现 `compute_curvature` 的 CuPy GPU 路径**（或删除 `use_gpu` 参数并更新 docstring/task_plan） | `packages/geoviz_seismic/geoviz_seismic/attributes.py:404-483` | 🔴 P0 | ✅ DONE |
| 11.5-B | **抽象 `AttributePipeline` 类**：把 `seismic_view.py:831-867` 的 hardcoded `_FN` 列表 + `if idx>=8` 魔数收敛到一个 dispatch 表（dict[idx → (name, fn, kwargs_resolver, axis)]） | `packages/geoviz_seismic/geoviz_seismic/seismic_view.py` | 🟡 P1 | ✅ DONE |
| 11.5-C | **整改 3 个 skipped 测试**：`test_well_tie_pipeline.py` 的空反射率/单样本/dict 序列化测试改为 xfail + 真实断言，而非 skip | `tests/test_well_tie_pipeline.py` | 🟢 P2 | TODO |
| 11.5-D | **新增 `_apply_attr` idx=8-13 集成测试**：当前曲率/dip/azimuth 的 UI 分支路径无测试覆盖 | `tests/test_seismic_view.py` | 🟢 P2 | ✅ DONE |
| 11.5-E | **同步子包 CHANGELOG**：`geoviz_seismic/CHANGELOG.md` 停留在 0.1.2（5月11日），与根 CHANGELOG 脱钩 | `packages/*/CHANGELOG.md` | 🟢 P2 | TODO |
| 11.5-F | **版本号策略文档化**：在根 README 加注 `VERSION (0.7.0)` vs `CHANGELOG (0.10.0)` 是有意为之 | `README.md` | 🟢 P3 | TODO |

**Acceptance criteria:**
- 11.5-A 完成后：`pytest tests/test_curvature.py::TestCurvatureGpuConsistency` 在有 CuPy 环境真正测试 GPU vs CPU 数值一致性（不再是空 skip）
- 11.5-B 完成后：新增第 15 个属性只需改 1 处（dispatch 表）
- 全程保持 636+ tests 绿

---

## 📋 重写后的 Roadmap（基于 CEO + Eng review 综合判断）

### Phase 12 拆分为 12a + 12b（Eng review 建议降低单 phase 风险）

#### 🥇 Phase 12a: 双 GLVolumeItem 叠加 MVP（中等优先级）
- **Goal:** SeismicView 同时渲染原始振幅体 + 一个属性体（如 coherence）
- **Approach:** 两个独立 GLVolumeItem + alpha 混合（不做纹理共享）
- **Risk:** 中 — pyqtgraph OpenGL 多 volume 在 headless GL Mock 测试历史脆弱
- **Tests:** ~6 (alpha blending, layer toggle, memory)
- **Spike:** 开工前先验证 GLVolumeItem * 2 在当前 pyqtgraph 版本可正常显示

#### Phase 12b: 共享纹理优化（低优先级 stretch）
- **Goal:** 避免双份 GPU 显存占用，写 GLSL shader 让一个纹理多通道显示
- **Risk:** 高 — 需手写 GLSL，与 pyqtgraph 抽象层冲突
- **决策门：** 仅当 12a 真实数据测试发现显存瓶颈时才启动

### 🥇 Phase 14（提前到 P1）：连井剖面自动化 + 报告导出
> **CEO 建议从 P3 提升到 P1** — 投入低、产出高、构成"地图点一下出一本报告"的杀手级 demo

- **场景：** 在井位地图上框选区域 → 自动按地理走向选 N 口井 → 连井剖面 → 井震 tie → 一键 PDF 报告
- **Components:**
  - `auto_section_planner.py`：几何算法（PCA / convex hull / 构造方位）
  - `report_export.py`：复用 Phase 10 的 `export_professional_figure` 出 PDF
  - `cross_well` 接收外部 wells 列表（API 微调）
- **Tests:** ~12（几何 + 报告渲染快照）
- **Risk:** 低 — 纯几何 + UI，cross_well + paleo_map 出图能力已就绪

### 🆕 Phase 15（新增，CEO 建议）：Project 工程文件 + Pilot 部署
> **CEO review 核心观点：当前所有 Phase 都是 demo，无 Project 概念无法 daily use**

- **Goal:** 引入 `.gvz` 工程文件（JSON-friendly，Git-friendly），可保存：
  - 加载的多井 / 多体 / 多层位 / 多相图引用
  - 用户拾取、相图编辑、属性配置、视图状态
- **Tasks:**
  - 设计 schema（参考 Petrel .pet 但简化）
  - Open/Save UI（与现有 DataPage 集成）
  - 找 1 家油田/院所做 pilot 反推 schema 缺漏
- **Risk:** 中 — schema 决策影响所有后续 phase；建议先 spike 写 RFC

### ⏸ Phase 13（CWT/时频 RGB）—— 暂缓
> CEO + Eng 一致建议：算法重、用户少、ROI 低；CWT 内存 O(N·scales) 需 spike 设计

- **前置条件：** 必须先有 Phase 15 pilot 用户反馈"需要时频分析"才启动
- **Pre-Phase spike：** "CWT 内存 / 性能 POC + chunking 设计文档"

### 🆕 Phase 16（候选）：AI 辅助解释
- 自动断层识别、相预测、井曲线智能补全
- **风险高**：模型 / 数据 / 标注成本未知
- **决策门：** Pilot 用户提出明确需求后启动

---

## 📦 Packages (6 independent pip-installable packages)

| Package | 功能 | 健康度 | 备注 |
|---------|------|--------|------|
| geoviz-well-log | ECharts SVG 测井渲染 | ✅ | |
| geoviz-seismic | pyqtgraph OpenGL + 属性 | ⚠️ | seismic_view.py 1294 行待抽象（11.5-B） |
| geoviz-map | QPainter 井位地图 | ✅ | |
| geoviz-paleo-map | QPainter 古地理图 + 编辑 | ✅ | |
| geoviz-cross-well | 连井对比 → 依赖 well-tie | ✅ | |
| geoviz-well-tie | 井震结合 — 纯 NumPy | ✅ | 3 个 skipped 测试待整改（11.5-C） |

**架构健康：** 无循环依赖；src/pages 全是薄壳；最大单文件 `seismic_view.py` 1294 行（已 refactor 一轮）。

---

## 🔑 Key Decisions（历史 + 新增）

| Decision | Rationale |
|----------|-----------|
| 属性扩展现有 geoviz-seismic | attributes.py 已有骨架，工具栏已有 combo |
| 井震结合新建 geoviz-well-tie | 数据模型不同，遵循独立 package 模式 |
| 不引入 bruges 库 | 自行实现 Ricker/Ormsby，纯 NumPy |
| VERSION 0.7.0 vs CHANGELOG 0.10.0 | 用户有意为之；需在 README 文档化（11.5-F） |
| **新：Phase 11.5 优先于 Phase 12** | Eng review 发现 `compute_curvature` GPU 参数被静默忽略；技术债不还，后续 phase 越垒越歪 |
| **新：Phase 14 提前到 P1** | CEO 评估为最高 ROI 的差异化亮点 |
| **新：Phase 15 (Project 文件 + Pilot) 加入** | CEO 核心结论：无 Pilot 验证，所有 Phase 都是空中楼阁 |
| **新：Phase 13 暂缓** | CWT 内存风险高 + 用户需求未验证 |

---

## ⚠️ 风险与隐患（CEO + Eng 综合）

| 类别 | 风险 | 应对 |
|------|------|------|
| 🔴 工程诚信 | `compute_curvature` use_gpu 假承诺 | Phase 11.5-A 强制修复 |
| 🔴 用户验证 | 迄今 0 真实项目落地 | Phase 15 强制 Pilot |
| 🟡 依赖脆弱 | CuPy / pyqtgraph OpenGL 在 Windows 装机环境 | README 明确 NumPy-only 安装路径 |
| 🟡 测试盲区 | SeismicView 14 项 combo UI 集成 + RGB fusion 无测 | Phase 11.5-D |
| 🟡 版本管理 | 子包 CHANGELOG 与根脱钩 | Phase 11.5-E |
| 🟢 商业模式 | 开源 / 商用未决 | 待 Pilot 反馈后评估 |
| 🟢 性能基线 | 缺真实 SEGY 大数据 E2E | Phase 12a 之前补一份 benchmark 套件 |

---

## Notes
- 636 tests passed, 3 skipped — full suite green
- cross-well 依赖 well-tie（纯 NumPy，零 Qt）
- Phase 11 shipped: `86da1b14` — 但带 GPU 假承诺缺陷
- 下一步动作：等待用户选择从 Phase 11.5 哪个 task 开始（推荐 11.5-A，最高诚信价值）
