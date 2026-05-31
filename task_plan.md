# Task Plan: GeoViz Engine — 项目总览与下一步规划

## Goal
GeoViz Engine 是一款基于 PySide6 的地质数据可视化桌面引擎。Phase 1–8 已全部完成并推送到 main。当前处理遗留工程项。

## Current State
- **Branch:** main (synced with origin)
- **Tests:** 636 passed, 3 skipped
- **Latest commit:** `3e3b5ce6 refactor: split seismic_view.py into focused modules`
- **Active phase:** Phase 11 — Curvature COMPLETE; awaiting user direction for next phase
- **Design spec:** `docs/superpowers/specs/2026-05-30-paleo-map-texture-export-design.md`
- **Implementation plan:** `docs/superpowers/plans/2026-05-30-paleo-map-texture-export.md`

## Completed Phases (Summary)

| Phase | Content | Status |
|-------|---------|--------|
| Phase 1 | PySide6 骨架、导航、单井剖面、地图、地震3D、数据管理 | ✅ |
| Phase 2 | 多井对比、相变连通、地层拉平、TVDSS对齐、SVG导出 | ✅ |
| Phase 3 | 测井引擎独立化、轨道管理器、矢量导出、AI预测集成 | ✅ |
| Phase 4 | 地震可视化独立化、3D体渲染+2D剖面、SEGY按需切片 | ✅ |
| Phase 5 | 连井对比拾取工作流（层位顶面、手动拾取、DTW、地震校深） | ✅ |
| Phase 6 | 地震属性分析（5属性+色标）、沿层位提取、井震结合包 | ✅ |
| Phase 7 | STFT谱分解、RGB属性融合、属性交叉图 | ✅ |
| Phase 8 | 井震结合可视化集成（WellTiePanel + auto-tie + overlay） | ✅ |
| A7 Dedup | CheckshotTable → WellTieCalibration 委托去重 | ✅ |

## Packages (6 independent pip-installable packages)

| Package | 功能 | 文件数 |
|---------|------|--------|
| geoviz-well-log | ECharts SVG 测井渲染 | ~12 modules |
| geoviz-seismic | pyqtgraph OpenGL 地震可视化 + 属性计算 | ~12 modules |
| geoviz-map | QPainter 井位地图 (Web Mercator) | ~6 modules |
| geoviz-paleo-map | QPainter 古地理图 (Plate Carrée) + 编辑 | ~14 modules |
| geoviz-cross-well | 连井对比 (DTW、层位拾取、地震校深) → 依赖 well-tie | ~6 modules |
| geoviz-well-tie | 井震结合 (合成地震记录、标定) — 纯 NumPy | ~4 modules |

## Completed Legacy Items

- **Phase 2 遗留: DTW ghost picks UX** ✅ — 左键点击 DTW 幽灵拾取调用 `accept_dtw_pick()`，右键拒绝
- **Phase 2 遗留: SeismicTie 双轴显示** ✅ — `PickingOverlay._paint_twt_axis()` 在 TWT 域渲染 TWT 刻度标签

## Completed Features (Latest)

| Phase | Feature | Status |
|-------|---------|--------|
| Phase 9 | Coherence (C3 eigenstructure) 相干属性 | ✅ — `compute_coherence_c3` + GPU加速 + 12 tests |
| Phase 9b | GPU Acceleration for Coherence | ✅ — CuPy offload, 1.5-1.9x speedup, numerically identical |
| Phase 10 | PaleoMap 纹理填充渲染 + 专业图件导出 | ✅ — 13 图案 SVG + PatternEngine 扩展 + 矢量 SVG 导出 + 出版级图框 (617 tests) |
| Refactor | seismic_view.py 拆分 | ✅ — workers/colorbar/dialogs 提取，1471→1283 行，617 tests |
| Phase 11 | Curvature 曲率属性 (dip/azimuth + 6 kinds) | ✅ — `compute_dip`/`compute_azimuth`/`compute_curvature` + UI 集成 + 19 tests (636 total) |

## Roadmap: Future Phases

### Phase 11: Curvature 曲率属性 (Tier 3)
**Goal:** 实现地层曲率分析，用于裂缝预测和构造解释。
- **Pre-req:** Dip/Azimuth 计算（结构张量或平面拟合）
- **Curvature types:** Gaussian, Mean, Maximum, Minimum, Dip, Strike
- **Integration:** `attributes.py` 新增 `compute_curvature_*` 系列函数
- **GPU support:** CuPy offload (reuse Phase 9b chunking pattern)
- **Tests:** ~15 new tests
- **Complexity:** 中

### Phase 12: 3D 属性体渲染 (Tier 3)
**Goal:** Renderer3D 支持同时渲染原始地震体 + 属性体（如 coherence 体）。
- **Dual-volume rendering:** 原始振幅体 + 属性体叠合显示
- **Blending modes:** 叠加、透明融合、属性体作为染色层
- **UI:** SeismicView 工具栏新增体选择/融合控制
- **Performance:** 共享纹理内存，避免双份 GPU 显存占用
- **Tests:** ~10 new tests (headless GL  mock)
- **Complexity:** 中

### Phase 13: 谱分解进阶 (可选)
**Goal:** 多窗口 STFT、连续小波变换 (CWT)、时频谱 RGB 融合。
- **Complexity:** 高 — 算法密集，需充分调研

### Phase 14: 连井剖面自动化 (可选)
**Goal:** 基于地理距离/构造走向自动生成连井剖面线。
- **Complexity:** 低-中 — 主要是几何计算 + UI 交互

## Key Decisions (Historical)
| Decision | Rationale |
|----------|-----------|
| 属性分析扩展现有 geoviz-seismic | attributes.py 已有骨架，工具栏已有 combo，ProfileVD 支持任意数据 |
| 井震结合新建 geoviz-well-tie | 数据模型不同（井路径、合成记录），遵循独立 package 模式 |
| CheckshotTable 委托 WellTieCalibration | 消除 np.interp 重复，array 输入免费获得，依赖方向合理 (cross-well → well-tie) |
| 不引入 bruges 库 | 自行实现 Ricker/Ormsby，纯 NumPy，零额外依赖 |
| VERSION 保持 0.7.0 | 用户选择不随 CHANGELOG 同步版本号 |

## Notes
- 617 tests passed, 3 skipped — full suite green
- cross-well 现依赖 well-tie（纯 NumPy，零 Qt）
- VERSION (0.7.0) 与 CHANGELOG (0.10.0) 不同步 — 用户有意为之
- Phase 10 shipped: `8ca37621` — 13 facies patterns + vector SVG export + professional figure export
- Refactor shipped: `3e3b5ce6` — seismic_view.py split into workers/colorbar/dialogs modules
