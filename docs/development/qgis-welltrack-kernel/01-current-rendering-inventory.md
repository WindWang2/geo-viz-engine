# 01 — Current rendering inventory (geo-viz-engine baseline)

Sources audited: `packages/geoviz_well_log/**`, `packages/geoviz_plots/**`,
`packages/geoviz_cross_well/**`, `src/pages/well_log/page.py`,
`native/map_edit_core/`, `tests/**`. Full file walk done at baseline SHA
`0f89b9ed`. This document records what exists so the new C++ kernel can reuse
*behavior*, not code.

## geoviz_well_log (primary reference; pure QPainter main path)

Architecture: `WellLogData` (pydantic) → `build_qpainter_tracks()` →
`list[BaseTrack]` → `WellLogCanvas.set_tracks()` → `LayoutCoordinator` →
`paint_all(QPainter*)`. Display, SVG, PDF and PNG export all go through the
single `paint_all` path (hover overlays never enter exports).

- **Track types**: depth ruler, curves, intervals, lithology, facies,
  systems-tract, markers (zero-width overlay), image (core photos), plus a
  legacy ECharts WebEngine line (`chart_engine.py`, historical).
- **Curve pipeline** (`renderer/curve_track.py`): constructor copies values to
  sorted `np.float64` arrays (drops non-finite *depths*, stable argsort);
  viewport clip via `np.searchsorted` with ±5% margin; min-max LOD via
  injectable provider (`renderer/downsample.py`, explicitly reserved as a C++
  acceleration hook, issue #845); QPainterPath cache keyed by quantized
  `(pixel_height, round(w), round(span), round(top/q), round(bottom/q))`,
  `q = span/pixel_height`; screen-space simplification for >1000 points;
  `build_curve_path` breaks subpaths at non-finite values.
- **LOD contract** (behavior oracle for the C++ kernel): floor binning
  `step = n // pixel_height`, partial tail bin; per bin emit the bin's min and
  max samples **in original index order**; a bin containing non-finite values
  additionally emits the first non-finite-index sample so the polyline breaks
  instead of bridging.
- **Depth axis**: increases downward (geology convention); *no* inversion
  switch on the main canvas; reversal only exists in the `section/` line
  (`DatumTransformer`, datum-shift mode). Ticks: `nice_depth_interval` picks
  1/2/5×10^k with on-screen spacing ≥ 20 px; ruler target spacing 60 px.
- **Zoom/pan**: two coexisting implementations — canvas `wheelEvent`
  (factor 0.88/1.14, cursor pivot, min span 1.0, no full-range clamp) and
  `ZoomPanHandler` eventFilter (factor 0.2, clamped to full range, double-click
  reset). Pan: left/middle drag, `delta_depth = -(dy/content_h)*span`.
- **Multi-canvas depth sync**: `QPainterSyncManager` — canvas emits
  `depth_range_changed(top,bottom)` → other canvases `blockSignals(True)` +
  `set_depth_range` with `_is_syncing` re-entrancy guard and a `<1e-9` no-op
  guard that prevents cascade invalidation.
- **Track layout**: fixed pixel widths (defaults 60/50/80/140/180, clamped
  40–300), draggable separators (6 px hot zone, ±clamp), per-curve-scale
  header band (`max(56, 28+18*n)`), group header 32 px, overlay tracks last.
- **Track orchestration** (merge AC/GR, RT/RXO groups; ordering; visibility;
  merge/split) lives in the *page controller*, not the canvas — same split the
  new kernel enforces (B owns orchestration).
- **Cross-well picking**: 10 px screen tolerance converted to depth tolerance
  by the current depth scale; extremum snap (`argmax/argmin` in window).
- **Hover readout**: bisect + linear interpolation on sorted copies (not
  nearest-sample) for the value readout; nearest-sample for picking.

## geoviz_plots

- `chart/plot_widget.py`: general 2D line/scatter widget; cKDTree hover snap;
  `view_changed/point_hovered` signals; same `render_plot` used for export.
- `chart/series.py`: `lttb_downsample` (largest-triangle-three-buckets),
  threshold ~2000, NaN pre-filtered, endpoints kept.
- `chart/axes.py`: Heckbert `nice_number` 1/2/5 tick generator.
- Everything else in the package (kriging/factor/surface/geomodel/...) is
  unrelated to track rendering.

## geoviz_cross_well

Reuses `WellLogCanvas` + `QPainterSyncManager` for multi-well correlation;
adds `DatumTransformer` (absolute / datum_shift), `SeismicTie` (MD↔TWT),
picking overlay, DTW engine. Depth mapping helpers
(`_y_to_depth` header-inset aware) live here.

## native/map_edit_core (only existing C++ in repo)

setuptools + pybind11 extension; **no CMake anywhere in the repo** — the new
package establishes the CMake convention. Compiler-flag lesson kept:
`-fno-finite-math-only` under `-ffast-math` so NaN/Inf checks are not
optimized away (geometry code must observe NaN).

## What the new kernel deliberately does NOT duplicate

- No second generic 2D chart widget (geoviz_plots stays).
- No ECharts/web line, no lithology/facies semantic tracks, no LAS/XML
  loading, no pattern SVG engine, no correlation/DTW — those are either
  existing Python features (reference only) or Prompt-B domain layer.
- The kernel is the *substrate*: shared numeric depth domain, N track columns,
  curves, generic bands/markers, transforms, hit-test, LOD, QGIS-native
  canvas/tool stack.
