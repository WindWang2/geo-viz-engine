# 09 — Review rounds 1 & 2 (API-only + static implementation)

Reviewer: independent subagent (fresh context), 2026-09-24, against commit
`9a078ac4`. Baseline docs 03/05/06/07 were given as the review contract; all
QGIS API usage was checked against the vendored 4.2.0 snapshot sources.

## Round 1 (API-only) findings

- Contract self-consistency: OK (borrowed-buffer contract, generation
  discipline, thread-safety notes all present and coherent).
- Domain leakage: **none** — no WellId/HorizonId/Lithology/Facies/
  PaleoProject/WellRepository anywhere in the kernel (example demo curve
  names GR/RHOB are host-side data, acceptable).
- Dependency direction: source-level clean (core has no QtWidgets/QGIS gui
  includes); one build-graph violation found (P1-4 below).
- Deviations from 05: all within the "names may drift" tolerance
  (fitDepth dropped its parameter; contentTopLeft/contentRect replaced by
  lastLayout(); accessor-ized TrackAxisSpec::style; added
  adoptTrack/tracksForEdit/depthExtent/interpolateAtDepth helpers).

## Round 2 (static implementation) — findings and dispositions

| # | Sev | Finding | Disposition |
|---|---|---|---|
| P0-1 | compile error | `QPointer` on `QgsPlotCanvasItem` (QGraphicsItem, not QObject) | FIXED: raw pointers (upstream elevation-canvas pattern) ebe9b70f |
| P0-2 | compile error | `QgsPlotTool` ctor takes `(canvas, QString name)`; QCursor passed | FIXED: name via ctor, `setCursor()` after |
| P0-3 | compile error | `setToolName()` doesn't exist on QgsPlotTool | FIXED (same commit) |
| P1-1 | correctness | envelope cache keyed only on generation+seriesId → stale envelopes across models sharing generation numbers | FIXED: model-pointer identity guard + cache clear on change |
| P1-2 | correctness | SeriesId collisions share cache slots; partnerId=0 could self-match | FIXED: (trackId, seriesId) key; partner lookup skips 0/self; uniqueness documented on CurveSpec |
| P1-3 | correctness | zoomInClickOn kept span (only recentered) instead of halving | FIXED: ± span/4 |
| P1-4 | packaging | core target transitively pulled QGIS gui + QtWidgets via SDK interface | FIXED: `GeoVizQgis::SdkCore` core-only closure; gui target keeps full SDK |
| P1-5 | packaging | `TrackLayoutResult` out-of-line members unexported | FIXED: struct export macro |
| P2 batch | quality | clampedTo edge-pair normalization, curve_lod.h contract wording, separator comment, pan speed using widget height, missing `rc.setDevicePixelRatio`, fragile includes, hit-result half-fill on reject, adoptTrack id minting, queue-connection metatype, dead slot | FIXED (batch); adopted-track id bump; `qRegisterMetaType` in canvas ctor |

Also verified by the reviewer (no action): all overridden QgsPlotCanvas
virtuals and QgsPlotToolZoom hooks match the 4.2.0 signatures verbatim;
QgsTextRenderer/QgsLineSymbol/QgsNumericFormat/QgsPlotAxis usage correct;
`calculateOptimisedIntervals` early-exit and degenerate-axis pitfalls
avoided; NaN-gap contract (including NaN-only bins — fixed pre-review during
self-audit) correct; painter save/restore and clip pairing complete;
ownership chain (scene→items, tools as canvas QObject children, auto-unset)
matches upstream semantics.

Verdict after fixes: cleared to proceed to rounds 3/4.
