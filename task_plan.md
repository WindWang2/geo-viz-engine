# Task Plan: GeoViz Engine Phase 6 (地震属性分析 + 井震结合)

## Goal
在 geoviz-seismic 包中扩展地震属性分析功能（Tier 1 瞬时属性族），并新建 geoviz-well-tie 包实现井震结合工作流（合成地震记录、井震标定）。

## Current Phase
Phase 6 (Sub-phase 3 — 新建 geoviz-well-tie 包)

## Phases

### Phase 1: 现状盘点与 PR 合并 ✅
- [x] PR #18 合并到 main
- [x] 更新 README Roadmap Phase 5 为 ✅
- [x] 回到 main 分支
- **Status:** complete

### Phase 2: Phase 5 遗留项评估
- [ ] 确认 cross-well 功能无遗漏
- [ ] DTW ghost picks UX 评估
- [ ] SeismicTie 双轴显示完整性
- **Status:** pending（可选，不阻塞 Phase 6）

### Phase 3: Phase 6 需求分析 ✅
- [x] 调研地震属性分析功能需求
- [x] 调研井震结合功能需求
- [x] 评估现有 geoviz-seismic 包扩展性
- [x] 确定 sub-phases 划分
- **Status:** complete

### Phase 4: Phase 6 Sub-phase 1 — 扩展属性计算 ✅
- [x] 扩展 `attributes.py`：instantaneous frequency, RMS, sweetness, relative impedance
- [x] 扩展 `ColormapManager`：属性专用色标 (viridis, phase_wheel)
- [x] 扩展工具栏 combo box：新增属性选项（7 个：振幅/包络/瞬时相位/瞬时频率/RMS振幅/甜点/相对阻抗）
- [x] 新增 tests（8 个新测试，全部通过）
- [x] 提交并推送到 feat/seismic-attributes 分支
- **Status:** complete

### Phase 5: Phase 6 Sub-phase 2 — 沿层位属性提取 ✅
- [x] `horizon.py` 新增 `extract_along_horizon(volume, grid, dt_ms, t0_ms, window)` 函数
- [x] 支持 single-sample 和 windowed RMS 提取
- [x] 导出至 `__init__.py`
- [x] 新增 tests（7 个测试，全部通过）
- **Status:** complete

### Phase 6: Phase 6 Sub-phase 3 — 新建 geoviz-well-tie 包 ✅
- [x] Package scaffold（pyproject.toml, __init__.py, README.md）
- [x] Ricker + Ormsby 子波生成（wavelet.py）
- [x] 反射系数计算（sonic × density → impedance → reflectivity, synthetic.py）
- [x] 合成地震记录生成（reflectivity ⊛ wavelet, synthetic.py）
- [x] 井震标定（WellTieCalibration: T-D 转换, sonic 积分, 深度→TWT 重采样, calibration.py）
- [x] 新增 tests（15 个测试，全部通过）
- [ ] 与 geoviz-seismic / geoviz-well-log 集成（可视化面板 — 后续 phase）
- **Status:** complete（核心库完成，可视化集成留待后续）

### Phase 7: Phase 6 Sub-phase 4 — 高级可视化
- [ ] RGB 属性融合（三频段/三属性 → R/G/B）
- [ ] 属性交叉图（attribute crossplot）
- [ ] 可选：Spectral Decomposition (STFT)
- **Status:** pending

## Key Questions
1. ~~Phase 6 优先做地震属性分析还是井震结合？~~ → 先做属性计算（Sub-phase 1），再做井震结合（Sub-phase 3）
2. ~~Phase 6 是否需要新的独立 package？~~ → 属性分析扩展现有包，井震结合新建 `geoviz-well-tie`
3. ~~是否引入 `bruges` 库？~~ → 不引入，自行实现 Ricker/Ormsby，纯 NumPy，零额外依赖
4. Sub-phase 划分是否合理？→ 待用户确认

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 属性分析扩展现有 geoviz-seismic | attributes.py 已有骨架，工具栏已有 combo，ProfileVD 支持任意数据 |
| 井震结合新建 geoviz-well-tie | 数据模型不同（井路径、合成记录），遵循独立 package 模式 |
| Tier 1 属性优先 | 纯 NumPy/SciPy，改动最小，用户立即可用 |
| 沿层位提取作为独立 sub-phase | 需要扩展 HorizonParser，但与属性计算逻辑正交 |
| RGB 融合放最后 | 需要新的 QImage 合成逻辑，优先级低于核心属性 |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|

## Notes
- Phase 5 已完成，PR #18 已合并
- 现有 attributes.py 已有 envelope + phase
- 485 tests 全绿
- 项目版本: 0.8.0
