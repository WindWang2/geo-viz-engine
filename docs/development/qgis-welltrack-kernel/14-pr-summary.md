# 14 — PR summary

**PR title:** `feat(plot): add QGIS-native well-track plotting kernel package`

Branch `feat/qgis-plot-welltrack-kernel` ← `main` (base `0f89b9ed`).

## What

New standalone C++20 package `packages/geoviz-qgis-welltrack/`
(`GeoViz::QgisWellTrackCore` + `GeoViz::QgisWellTrack`): a high-performance
well-track / log-curve plotting substrate built on the project's actual QGIS
4.2.0 SDK (vendored `final-4_2_0` @ `ca5812c8`), for use by geo-viz-engine
hosts and paleo-workbench through stable public headers only.

## Why

The existing Python/QPainter stack (`geoviz_well_log`) is behavior-proven
but Python-side; the QGIS plot framework provides a mature canvas/tool/event
substrate yet lacks exactly the pieces well tracks need. This kernel closes
that gap **on QGIS's own extension points** instead of growing a second
in-house framework.

## How (architecture, evidence-linked)

- `WellTrackCanvas : QgsPlotCanvas` implements the upstream-defaulted-empty
  interaction virtuals (pan/scale/zoomToRect/wheelZoom/transforms/snap) —
  the same route QGIS's elevation profile canvas takes. Pan tool is
  upstream's `QgsPlotToolPan` used as-is; marquee depth zoom subclasses
  `QgsPlotToolZoom`'s C++ constrain hooks; transient tools (Space/Ctrl/
  middle-button) come free. (docs 02/03)
- Core (no Widgets): orientation-aware shared depth domain, zero-copy
  strided series views, binary-search visible slicing + extrema-preserving
  min/max envelope with NaN-gap breaks (contract oracle = existing Python
  downsample), track column layout, composite renderer using QGIS
  `QgsPlotAxis`/`QgsTextRenderer`/`QgsLineSymbol` +
  `calculateOptimisedIntervals`, hit testing, multi-canvas depth
  synchronizer with anti-feedback guards.
- License gate: **zero QGIS source copied** — linking-only reuse, ledger in
  docs 04 + `LICENSES/QGIS-LINKING.md` (GPL-2.0+ implications of binary
  distribution flagged).
- Prompt-B boundary: no domain entities; B-line consumes the public API.

## Review & verification record

- 4 review rounds (docs 09–12): 10 P0 + 9 P1 findings, all fixed pre-build —
  including a deterministic upstream hang (`calculateOptimisedIntervals`
  with ≤16 px plots, now guarded + cached) and NaN-only-bin gap bridging.
- Targeted build only (never the wider repo), `-j2`: 48/48 targets.
- ctest: **13/13 suites green** (logic oracles, pixel probes, gesture-level
  tool tests, lifecycle smoke, 50× open/close).
- Perf evidence (docs 13): paint cost flat ~5–7 ms from 1e4 → 1e6 samples
  per curve (envelope output constant ≈ 2 pts/pixel-row/curve); 1.35e8
  samples/s envelope prep single-threaded.
- Offscreen demo PNG smoke passes; interactive demo included.

## Scope guardrails honored

- `packages/geoviz_well_log` and all existing packages untouched.
- No `packages/geoviz_well_track_native` (B-line) code included or required.
- No CI wait, no merge — PR left open for review.
