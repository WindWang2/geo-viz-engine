# 08 — Test plan

Framework: Qt Test (`QTEST_MAIN`/`QTest`), registered with CTest. Core tests
run on `QT_QPA_PLATFORM=offscreen` and only need `QApplication` + a
process-wide `QgsApplication::init()+initQgis()` (symbol/text registries);
GUI tests use the same offscreen platform. Recipe mirrors
`native/qgis_render_bridge` (setPrefixPath → SDK output dir; exactly-once
guard).

## Core (pure logic)

| Suite | Pinned behavior |
|---|---|
| test_depth_domain | y↔depth both orientations round-trip; outside-range values land outside rect; degenerate span → center + `isValid()==false`; NaN propagation |
| test_curve_view | Float32/Float64/strided/unaligned reads equal packed doubles; empty view; `validateDepthMonotonic` catches NaN/reorder (returns first violating index) |
| test_axis_transform | linear + log mapping round-trip; log floor clamp (values ≤0); degenerate range → center; NaN → NaN (no clamp-to-edge) |
| test_visible_slice | equals brute-force linear scan for random monotone arrays incl. margins; empty view; single sample; range fully outside; range spanning all; ±5% margin present |
| test_envelope | per-bin min/max == brute force min/max for random walks (extrema preservation); index-order emission (min-before-max when argmin<argmax and vice versa); NaN bin → breakAfter and no bridging; small-n passthrough; bins>samples; empty slice; global window extremes always present |
| test_track_layout | fixed+stretch mix sums to width; separators drawn between visible tracks; hidden tracks excluded but indices stable; depth ruler fixed width; header band height; `trackAtX` boundaries (left edge in, gap out) |
| test_renderer | offscreen QImage: background/curve color pixels present; two curves distinct colors; **NaN gap probe**: no curve-colored pixel column between two finite segments (anti-bridging); band rect pixel probe; marker line probe; stats fields populated (rawSamples>0, envelopePoints<=4*bins*curves); QSvgGenerator export produces non-empty SVG containing path elements; repeated render idempotent (image hash equal) |
| test_hit_testing | exact hit on sample; nearest within tolerance; miss beyond tolerance; multi-track x-disambiguation; NaN samples skipped; empty model → no hit |

## GUI (QgsPlotCanvas stack)

| Suite | Pinned behavior |
|---|---|
| test_canvas_core | construct with model → grab() non-empty; `setDepthDomain` no-op (<1e-9) emits nothing (spy count 0) and does not invalidate cache; resize → item re-layout (content rect grows); repeated show/hide + destroy ×50 no crash (leak/UAF smoke) |
| test_canvas_navigation | `panContentsBy(0,dy)` pans depth by `-dy*span/h` and clamps at full extent edges; `scalePlot` around center; `zoomToRect` maps rect→window, tiny/inverted rect no-op; `wheelZoom` anchors cursor depth (depth under cursor before == after); `toMapCoordinates`/`toCanvasCoordinates` round-trip within 1e-6; `snapToPlot` finds synthetic sample; `crs()` invalid |
| test_canvas_tools | `QgsPlotToolPan` drag → depthRangeChanged; `WellTrackDepthZoomTool` marquee rect → zoomToRect equivalence (constrainBounds returns full-width); cursor tool move → cursorDepthChanged + sampleHovered; toolChanged signal; transient middle-button pan does not crash |
| test_synchronizer | two canvases: A pan → B matches exactly; no ping-pong (each emits once per gesture); removeCanvas stops sync; canvas destroy mid-sync no crash |

## Performance evidence (manual table, sanity-asserted only)

test_perf (not in default ctest label `ci`? — included but tolerant): synthetic
random-walk curves at 1e4/1e5/1e6 samples × 4 curves × 4 tracks; measures prep
µs, paint µs, envelope points; asserts envelope bound and 1e6 render < 5 s;
prints table for 13-final-build-evidence.md. No FPS claims.

## Review gates before build

- Every pinned behavior above maps to a named test function (checked in
  review 3).
- Oracle reuse: envelope/brute-force equivalence mirrors the Python contract
  tests (`packages/geoviz_well_log/tests/test_downsample.py`) so the two
  stacks are behaviorally comparable when B-line migrates.
