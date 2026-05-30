# TODOS

## Open

- **Phase 2 遗留: DTW ghost picks UX** — DTW 自动对比建议以虚线"幽灵拾取"展示，目前缺少点击接受/右键拒绝的交互完善。
- **Phase 2 遗留: SeismicTie 双轴显示** — 连井对比中地震校深的 TWT/MD 双轴显示待完善。

## Completed

- **A7: SeismicTie / WellTieCalibration dedup** — `CheckshotTable` 委托 `WellTieCalibration`，消除重复 `np.interp`。cross-well → well-tie 依赖（纯 NumPy）。
- Phase 8: Well-seismic tie visualization integration (v0.10.0, 2026-05-30)
- Phase 7: STFT spectral decomposition, RGB fusion, attribute crossplot (v0.9.0, 2026-05-30)
- Phase 6: Seismic attribute analysis + well-seismic tie core library (v0.8.0, 2026-05-29)
- Phase 5: Cross-well picking workflow (v0.8.0, 2026-05-29)
