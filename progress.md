# Progress Log

## Session: 2026-05-29

### Phase 1: 现状盘点与 PR 合并
- **Status:** complete
- Actions taken:
  - PR #18 squash-merged to main
  - README Roadmap updated: Phase 5 ✅, Phase 6 🔄

### Phase 3: Phase 6 需求分析
- **Status:** complete
- Actions taken:
  - 调研地震属性族 + 井震结合工作流
  - 分析 geoviz-seismic 扩展性
  - 确定 package 策略和 sub-phase 划分

### Phase 4: Sub-phase 1 — 扩展属性计算
- **Status:** in_progress
- **Started:** 2026-05-29 23:45
- Actions taken:
  - 扩展 `attributes.py`：新增 5 个属性函数
    - `compute_instantaneous_frequency()` — gradient of unwrapped phase / 2π
    - `compute_rms_amplitude()` — uniform_filter1d windowed RMS
    - `compute_sweetness()` — envelope / sqrt(freq)
    - `compute_relative_impedance()` — cumsum
    - `_analytic_signal()` helper（去重 hilbert 调用）
  - 扩展 `colormap.py`：新增 2 个属性专用色标
    - `viridis` — 感知均匀顺序色标（用于 envelope, RMS, sweetness）
    - `phase_wheel` — 圆形色标（用于相位数据）
  - 扩展 `seismic_view.py` 工具栏 combo box：
    - 7 个选项：振幅/包络/瞬时相位/瞬时频率/RMS振幅/甜点/相对阻抗
    - `_apply_attr()` 重构为 dispatch table
    - `_apply_current_attr()` 简化为复用 `_apply_attr()`
  - 新增 `test_attributes_extended.py`：8 个测试
- Files created/modified:
  - packages/geoviz_seismic/geoviz_seismic/attributes.py (extended)
  - packages/geoviz_seismic/geoviz_seismic/colormap.py (extended)
  - packages/geoviz_seismic/geoviz_seismic/seismic_view.py (extended)
  - tests/test_attributes_extended.py (new)
- Test results: 490 passed, 0 failed

## Test Results
| Test | Scope | Expected | Actual | Status |
|------|-------|----------|--------|--------|
| 8 new attribute tests | Package | All pass | All pass | ✓ |
| 7 horizon extract tests | Package | All pass | All pass | ✓ |
| 15 well-tie tests | Package | All pass | All pass | ✓ |
| 512 full suite | All | All pass | All pass | ✓ |

## Error Log
| Timestamp | Error | Attempt | Resolution |
|-----------|-------|---------|------------|

## 5-Question Reboot Check
| Question | Answer |
|----------|--------|
| Where am I? | Phase 6 COMPLETE, PR #19 merged to main |
| Where am I going? | Phase 7 (Sub-phase 4: 高级可视化) or new task |
| What's the goal? | Phase 6 done. Next: RGB fusion, crossplot, STFT |
| What have I learned? | 沿层位提取用 np.take_along_axis 向量化; 井震结合纯 NumPy 即可实现 |
| What have I done? | Sub-phase 1-3: 5 attrs + 2 colormaps + extract_along_horizon + geoviz-well-tie package |

## Session: 2026-05-29 (continued)

### Phase 5: Sub-phase 2 — 沿层位属性提取
- **Status:** complete
- Actions taken:
  - `horizon.py` 新增 `extract_along_horizon(volume, grid, dt_ms, t0_ms, window)`
  - 支持 single-sample 和 windowed RMS 提取
  - 导出至 `__init__.py`
  - 新增 `test_horizon_extract.py`：7 个测试
- Test results: 497 passed

### Phase 6: Sub-phase 3 — 新建 geoviz-well-tie 包
- **Status:** complete
- Actions taken:
  - 新建 `packages/geoviz_well_tie/` 独立 package
  - `wavelet.py`：Ricker + Ormsby 子波生成
  - `synthetic.py`：反射系数 + 合成地震记录
  - `calibration.py`：WellTieCalibration (T-D 转换, sonic 积分, 深度→TWT 重采样)
  - 接入 workspace (`pyproject.toml`)
  - 新增 `test_well_tie.py`：15 个测试
- Test results: 512 passed

---
*Update after completing each phase or encountering errors*
