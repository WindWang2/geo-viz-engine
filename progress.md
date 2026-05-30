# Progress Log — GeoViz Engine

## Project Status: Phase 1–8 COMPLETE, Legacy cleanup IN PROGRESS

### Session: 2026-05-30 (Phase 8 + Legacy)

#### Reviews Completed
- CEO Review: CLEAN — 6/6 proposals accepted, Well-Seismic Tie Visualization selected (SELECTIVE EXPANSION mode)
- Eng Review (Run 3): 22 findings — 7 critical, 8 high, 7 medium

#### Sub-phase 1: Core Library + Spatial Reference + Overlay API (DONE ✅)
- 8 files modified across geoviz-well-tie and geoviz-seismic packages
- 44 new tests, all green → 572 total
- Key additions: generate_synthetic_twt, resample_to_seismic_grid, BinGridGeometry, auto_tie, ProfileVD overlay API, read_trace

#### Sub-phase 2: WellTiePanel + SeismicView Integration (DONE ✅)
- `well_tie_panel.py` — WellTiePanel widget with wavelet controls, auto-tie, export
- `seismic_view.py` — toolbar toggle button + lazy panel creation
- 17 new tests, all green → 589 total

#### Phase 8 Shipped (DONE ✅)
- Committed: `75988c04` + `5af8ec15` (docs)
- Pushed to origin/main

#### A7: CheckshotTable / WellTieCalibration Dedup (DONE ✅)
- `CheckshotTable` refactored: delegates to `WellTieCalibration` instead of own `np.interp`
- New: `CheckshotTable.calibration` property exposes underlying `WellTieCalibration`
- Side benefit: `interpolate_twt` / `interpolate_depth` now support array inputs
- TDD: 4 red → all green + 5 regression = 9 new tests
- Dependency: cross-well now depends on well-tie (pure NumPy, zero Qt)
- 589 passed, 0 failed

## Test Results History
| Date | Tests | Status |
|------|-------|--------|
| 2026-05-29 (Phase 4) | 490 passed | ✅ |
| 2026-05-29 (Phase 5) | 497 passed | ✅ |
| 2026-05-29 (Phase 6) | 512 passed | ✅ |
| 2026-05-30 (Phase 7) | 528 passed | ✅ |
| 2026-05-30 (Phase 8.1) | 572 passed | ✅ |
| 2026-05-30 (Phase 8.2) | 589 passed | ✅ |
| 2026-05-30 (A7 dedup) | 589 passed | ✅ |

## 5-Question Reboot Check
| Question | Answer |
|----------|--------|
| Where am I? | A7 dedup DONE, Phase 2 legacy items remaining |
| Where am I going? | Commit A7 dedup, then Phase 2 legacy (DTW ghost picks UX, SeismicTie dual-axis) |
| What's the goal? | Clear all deferred engineering review items |
| What have I learned? | CheckshotTable can delegate to WellTieCalibration via dataclass `__post_init__` |
| What have I done? | A7 dedup — 1 file changed, 9 new tests, 589 green |

## Pending Items
- Commit A7 dedup work
- Phase 2 遗留项：DTW ghost picks UX、SeismicTie 双轴显示

## Errors Encountered
| Error | Resolution |
|-------|------------|
| depth_to_twt TypeError on array input | np.ndim check — float for scalar, array for array |
| BinGridGeometry il/xl swapped | il = (-dx*sin + dy*cos)/spacing (inline along azimuth from north) |
| QPainter.drawPolyline(*args) TypeError | drawPolyline(QPolygonF(list)) — PySide6 takes single QPolygonF |
| set_clip_percentile empty if body | Restored original method body lost during overlay insertion |
| Reflectivity N-1 vs depth N mismatch | Build midpoint WellTieCalibration at (depths[:-1]+depths[1:])/2 |
| Auto-tie sign convention | Positive shift = synthetic late (should move down), test updated |

---
*Update after completing each phase or encountering errors*
