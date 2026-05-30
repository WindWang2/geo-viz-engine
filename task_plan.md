# Task Plan: GeoViz Engine — 项目总览与下一步规划

## Goal
GeoViz Engine 是一款基于 PySide6 的地质数据可视化桌面引擎。Phase 1–8 已全部完成并推送到 main。当前处理遗留工程项。

## Current State
- **Branch:** main (synced with origin)
- **Tests:** 617 passed, 3 skipped
- **Latest commit:** `8ca37621 feat: export new public APIs (export_vector_svg, export_professional_figure)`
- **Active phase:** Phase 10 — PaleoMap 纹理填充渲染 + 专业图件导出
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
| Phase 10 | PaleoMap 纹理填充渲染 + 专业图件导出 | ✅ — 13 图案 SVG + PatternEngine 扩展 + 矢量 SVG 导出 + 出版级图框 (617 tests) |

## Unimplemented Features (Future)

| Priority | Feature | Complexity |
|----------|---------|------------|
| Tier 3 | Curvature 曲率属性 | 中 — 需先实现 dip/azimuth |
| Tier 3 | 3D 属性体渲染 | 中 — Renderer3D 双体支持 |

## Key Decisions (Historical)
| Decision | Rationale |
|----------|-----------|
| 属性分析扩展现有 geoviz-seismic | attributes.py 已有骨架，工具栏已有 combo，ProfileVD 支持任意数据 |
| 井震结合新建 geoviz-well-tie | 数据模型不同（井路径、合成记录），遵循独立 package 模式 |
| CheckshotTable 委托 WellTieCalibration | 消除 np.interp 重复，array 输入免费获得，依赖方向合理 (cross-well → well-tie) |
| 不引入 bruges 库 | 自行实现 Ricker/Ormsby，纯 NumPy，零额外依赖 |
| VERSION 保持 0.7.0 | 用户选择不随 CHANGELOG 同步版本号 |

## Notes
- 601 tests 全绿
- cross-well 现依赖 well-tie（纯 NumPy，零 Qt）
- VERSION (0.7.0) 与 CHANGELOG (0.10.0) 不同步 — 用户有意为之
