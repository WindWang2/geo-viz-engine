# Task Plan: GeoViz Engine — 项目总览与下一步规划

## Goal
GeoViz Engine 是一款基于 PySide6 的地质数据可视化桌面引擎。Phase 1–7 已全部完成并合并到 main。下一步规划待用户定义。

## Current State
- **Branch:** main (所有 feature 分支已合并)
- **Tests:** 528 passed, 3 skipped
- **Merged PRs:** #16, #17, #18, #19, #20
- **Latest commit:** `43c2e373 Merge pull request #20 from WindWang2/feat/advanced-viz`

## Completed Phases (Summary)

| Phase | Content | PR | Status |
|-------|---------|-----|--------|
| Phase 1 | PySide6 骨架、导航、单井剖面、地图、地震3D、数据管理 | — | ✅ |
| Phase 2 | 多井对比、相变连通、地层拉平、TVDSS对齐、SVG导出 | — | ✅ |
| Phase 3 | 测井引擎独立化、轨道管理器、矢量导出、AI预测集成 | — | ✅ |
| Phase 4 | 地震可视化独立化、3D体渲染+2D剖面、SEGY按需切片 | — | ✅ |
| Phase 5 | 连井对比拾取工作流（层位顶面、手动拾取、DTW、地震校深） | #18 | ✅ |
| Phase 6 | 地震属性分析（5属性+色标）、沿层位提取、井震结合包 | #19 | ✅ |
| Phase 7 | STFT谱分解、RGB属性融合、属性交叉图 | #20 | ✅ |

## Packages (6 independent pip-installable packages)

| Package | 功能 | 文件数 |
|---------|------|--------|
| geoviz-well-log | ECharts SVG 测井渲染 | ~12 modules |
| geoviz-seismic | pyqtgraph OpenGL 地震可视化 + 属性计算 | ~12 modules |
| geoviz-map | QPainter 井位地图 (Web Mercator) | ~6 modules |
| geoviz-paleo-map | QPainter 古地理图 (Plate Carrée) + 编辑 | ~14 modules |
| geoviz-cross-well | 连井对比 (DTW、层位拾取、地震校深) | ~6 modules |
| geoviz-well-tie | 井震结合 (合成地震记录、标定) | ~4 modules |

## Potential Next Steps (待用户选择)

### Option A: Phase 8 — 高级地震分析
- Coherence (C3 eigenstructure) 相干属性
- Curvature 曲率属性（需先算 dip/azimuth）
- 3D 属性体渲染（Renderer3D 双体支持）

### Option B: Phase 8 — 井震结合可视化集成
- geoviz-well-tie 与 SeismicView 的可视化面板集成
- 合成地震记录与实际地震剖面对比显示
- 井震标定交互（stretch/squeeze）

### Option C: Phase 8 — 地图/古地图增强
- 地图性能优化（已有 PaintScheduler + LayerPixmapCache）
- 古地图编辑模式完善
- GeoJSON 拓扑编辑高级功能

### Option D: Phase 8 — 工程化 / 发布
- PyInstaller 打包测试
- 文档完善（API docs、用户手册）
- CI/CD pipeline

## Key Decisions (Historical)
| Decision | Rationale |
|----------|-----------|
| 属性分析扩展现有 geoviz-seismic | attributes.py 已有骨架，工具栏已有 combo，ProfileVD 支持任意数据 |
| 井震结合新建 geoviz-well-tie | 数据模型不同（井路径、合成记录），遵循独立 package 模式 |
| Tier 1 属性优先 | 纯 NumPy/SciPy，改动最小，用户立即可用 |
| RGB 融合放 Phase 7 | 需要新的 QImage 合成逻辑，优先级低于核心属性 |
| 不引入 bruges 库 | 自行实现 Ricker/Ormsby，纯 NumPy，零额外依赖 |

## Errors Encountered
| Error | Resolution |
|-------|------------|
| STFT Zxx indexing axis error (Phase 7) | Zxx shape is (n_traces, n_freqs, n_frames); mask on axis 1 not 2 |
| istft missing axis parameter (Phase 7) | scipy.signal.istft 不支持 axis 参数，移除 |
| ndarray.moveaxis AttributeError (Phase 7) | moveaxis 是 numpy 模块函数，不是 ndarray 方法 |

## Notes
- Phase 2 遗留项（cross-well 功能确认、DTW ghost picks UX、SeismicTie 双轴显示）仍为 pending
- geoviz-well-tie 核心库完成，可视化集成留待后续
- 528 tests 全绿

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | CLEAN | 6 proposals, 6 accepted, 0 deferred |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | issues_found | findings from prior review |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 3 | issues_open | 22 findings: 7 critical, 8 high, 7 medium |
| Design Review | `/plan-design-review` | UI/UX gaps | 2 | issues_open | 3 unresolved decisions (stale — from prior branch) |
| DX Review | `/plan-devex-review` | Developer experience gaps | 1 | success | 7 findings, 7 fixes applied |

### Eng Review Summary (Run 3 — Phase 8 Well-Seismic Tie)

**Architecture (9 issues):** SeismicVolumeMeta lacks spatial reference (blocker), no overlay API in ProfileVD, render_rgba zeros _data, attribute transform breaks raw data path, dt unit mismatch (sec vs ms), toolbar overcrowding, code duplication with cross-well SeismicTie, no read_trace() convenience method.

**Data Flow (3 bugs):** Reflectivity length N-1 vs depth array N mismatch, missing resample-to-seismic-grid function, dt unit mismatch between wavelet (sec) and calibration (ms).

**Tests (6 gaps):** No ProfileWidget tests, no attribute rendering tests, no well-tie pipeline integration test, no synthetic edge cases, no cross-well tests, no overlay rendering tests. Estimated +25-35 tests needed.

**Performance (4 issues):** Image rebuild on every viewport change, synthetic resample on every slider drag (needs debounce), QPainter polyline for deep wells (needs subsampling).

**VERDICT:** CEO CLEARED. Eng review found 7 critical issues that must be resolved before implementation. Priority order: (1) Fix A1 spatial reference, (2) Fix data flow bugs 1-3, (3) Implement overlay API + WellTiePanel, (4) Add test coverage.
