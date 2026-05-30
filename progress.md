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

#### Phase 2 Legacy: DTW Ghost Picks + Dual-Axis (DONE ✅)
- `_handle_pick_click`: left-click on DTW ghost pick now calls `accept_dtw_pick()` (source → manual)
- `_paint_twt_axis`: PickingOverlay renders TWT scale labels when domain="TWT" and seismic_tie loaded
- 8 new tests (DTW accept model 4 + dual-axis 4), all green
- 43 cross-well tests total, 589 full suite

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
| 2026-05-30 (Phase 9) | 600 passed | ✅ |
| 2026-05-30 (Phase 9b) | 601 passed | ✅ |

## 5-Question Reboot Check
| Question | Answer |
|----------|--------|
| Where am I? | Phase 10 design DONE, spec committed; awaiting implementation approval |
| Where am I going? | Implement facies texture rendering + professional figure export per approved spec |
| What's the goal? | PaleoMap with sedimentary facies fills (Q/HS 1011-2016 Appendix O) + true vector SVG + publishing-grade figure export |
| What have I learned? | PatternEngine composite brush pipeline; QSvgGenerator limitations (raster patterns); spec has 16 facies types (not 24); CMYK mapping viable for small palettes |
| What have I done? | A7 dedup + Phase 2 legacy + Phase 9 Coherence + Phase 10 design + implementation plan — 601 green, all pushed |

#### Phase 9: Coherence (C3 eigenstructure) (DONE ✅)
- `compute_coherence_c3` — C3 eigenstructure coherence via power iteration
- 11 tests (shape, value range, window params, edge handling), all green
- Adaptive chunking for memory efficiency (~100 MB target per chunk)
- 600 total tests passed

#### Phase 9b: GPU Acceleration for Coherence (DONE ✅)
- Added `use_gpu` parameter to `compute_coherence_c3`
- CuPy power-iteration offload per-chunk with automatic fallback to CPU
- GPU path numerically identical to CPU (max diff ~1.2e-06, float32)
- Benchmark speedup: ~1.5-1.9x on RTX 4090 (15 GB)
  - (50, 50, 200): 4.0s → 2.1s (1.9x)
  - (100, 100, 300): 25.9s → 16.8s (1.5x)
  - (200, 200, 400): 136.3s → 87.3s (1.6x)
- 12 coherence tests (including new `TestCoherenceC3GpuConsistency`)
- Full suite: 601 passed

### Session: 2026-05-30 (Phase 10 — PaleoMap Texture + Export Design)

#### Design Completed
- Reviewed Q/HS 1011-2016 spec (Appendix O 沉积相图式, Appendix M 岩石图式)
- Explored existing PatternEngine, FaciesStyleResolver, FaciesPolygonsLayer, save_export.py
- Presented 2-3 approaches for both subsystems; user approved
- Design spec written: `docs/superpowers/specs/2026-05-30-paleo-map-texture-export-design.md`
- Spec self-reviewed and fixed (pattern count 24→16, existing patterns not moved)
- Committed: `fee0051d`

#### Design Decisions
- Extend PatternEngine with `get_facies_brush()` + new `facies/` SVG subdir
- QSvgGenerator for true vector SVG export
- Professional figure wrapper with standardized frame (title, scale bar, north arrow, legend, grid)
- CMYK via lookup table (small known palette)
- Directional patterns (物源方向) deferred to Phase 2

#### Implementation Plan Completed
- Plan written: `docs/superpowers/plans/2026-05-30-paleo-map-texture-export.md`
- 10 tasks, 50+ steps covering: pattern SVGs (13 files), PatternEngine extension, style resolver, vector SVG export, professional figure export, comprehensive tests (target 620+)
- Plan self-reviewed: spec coverage complete, no placeholders, types consistent
- Committed: `24d5710e`

## Pending Items
- Phase 10 implementation ready — awaiting user trigger

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
