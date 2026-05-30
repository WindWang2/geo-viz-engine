# TODOS

## Open

- **A7: SeismicTie / WellTieCalibration dedup** — `geoviz-cross-well/seismic_tie.py` 和 `geoviz-well-tie/calibration.py` 有重复的 T-D 插值逻辑。应统一到 `geoviz-well-tie` 包，cross-well 包改为 import。（Deferred from Phase 8 eng review）
- **Phase 2 遗留: DTW ghost picks UX** — DTW 自动对比建议以虚线"幽灵拾取"展示，目前缺少点击接受/右键拒绝的交互完善。
- **Phase 2 遗留: SeismicTie 双轴显示** — 连井对比中地震校深的 TWT/MD 双轴显示待完善。

## Completed

- Phase 8: Well-seismic tie visualization integration (v0.10.0, 2026-05-30)
- Phase 7: STFT spectral decomposition, RGB fusion, attribute crossplot (v0.9.0, 2026-05-30)
- Phase 6: Seismic attribute analysis + well-seismic tie core library (v0.8.0, 2026-05-29)
- Phase 5: Cross-well picking workflow (v0.8.0, 2026-05-29)
