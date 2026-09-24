# 03 — Reuse matrix (QGIS capability → well-track kernel decision)

Legend: **Reuse** = call through SDK public API as-is. **Adapt** = subclass /
implement QGIS-provided virtuals (no upstream source copied). **Own** = gap;
kernel implements from scratch because the public API demonstrably lacks it
(evidence in 02). **Avoid** = exists but wrong tool; documented to prevent
future re-litigation.

| QGIS class | Direct reuse | Fit for well tracks | Adapter needed | Source port | Decision |
|---|---|---|---|---|---|
| `QgsPlotCanvas` | event plumbing, tool lifecycle, transient tools, context-menu hook | good shell; interaction virtuals empty by design | subclass `WellTrackCanvas` implementing `refresh/panContentsBy/centerPlotOn/scalePlot/zoomToRect/wheelZoom/toMap*/toCanvas*/snapToPlot/crs` | no | **Adapt** (template: `QgsElevationProfileCanvas`) |
| `QgsPlotCanvasItem` | scene item base + auto scene registration | good | subclass for the composite track item + crosshair overlay | no | **Adapt** |
| `QgsPlotToolPan` | calls `canvas->panContentsBy(dx,dy)` | exact fit once canvas implements pan | none (vertical clamping inside canvas) | no | **Reuse** as-is |
| `QgsPlotToolZoom` | marquee/click/Alt-out gestures | exact fit; constrain hooks are C++-only virtuals for exactly this | subclass `WellTrackDepthZoomTool` overriding the 5 hooks (full-width band, depth-only zoom) | no | **Adapt** |
| `QgsPlotToolXAxisZoom` | bound to elevation canvas ctor | no | would need reimplementation | no | **Avoid** |
| `QgsPlotRectangularRubberBand` | z=1000 rect band, Shift/Alt semantics | exact fit | none | no | **Reuse** (via `QgsPlotToolZoom`) |
| `QgsPlotMouseEvent` | `mapPoint()` → our `toMapCoordinates` | exact fit | canvas implements transform | no | **Reuse** |
| `QgsPlotTool` (base) | hover/readout tool | exact fit | subclass `WellTrackCursorTool` | no | **Adapt** |
| `Qgs2DXyPlot::render` | grid/labels pipeline | **wrong direction**: y fixed upward; single axis pair; label reservation left+bottom only | full `render()` override would replicate ~400 upstream lines | no | **Avoid** for composite rendering; per-track chrome drawn by our renderer using the *parts* below |
| `QgsPlotAxis` | grid intervals, `QgsLineSymbol` grid symbols, `QgsTextFormat`, `QgsNumericFormat`, suffix policy | exact fit as the axis-style container | none — held by value per track axis | no | **Reuse** |
| `Qgs2DXyPlot::calculateOptimisedIntervals` | public 1-2-5 label-coverage optimizer | exact fit for depth ruler + value axis intervals | instantiate a private `Qgs2DXyPlot` as the calculator host | no | **Reuse** |
| `QgsPlotDefaultSettings` | default grid/background/chart symbols | exact fit for a QGIS-look default style | none | no | **Reuse** |
| `QgsLineSymbol` / `QgsFillSymbol` / `QgsTextFormat` / `QgsNumericFormat` | rendering primitives through `QgsRenderContext` | grid lines, band fills, axis labels | none | no | **Reuse** |
| `QgsRenderContext::fromQPainter` + `setDevicePixelRatio` | render-context bootstrap | exact fit incl. Hi-DPI | none | no | **Reuse** |
| `QgsLineChartPlot` | line series drawing | series containers copy per render; per-point DD injection; no LOD | — | no | **Avoid** for 1e4+ samples (kernel draws envelope polylines with QPainter pens through the same QgsRenderContext) |
| `QgsXyPlotSeries`/`QgsPlotData` | data model | `QList<std::pair>` by-value copies | — | no | **Avoid** (kernel data = non-owning typed views) |
| `QgsPlotRegistry` | plot-type registry for widget creation | none (bar/line/pie from vector layers) | — | no | **Avoid** — and the kernel deliberately registers no new generic plot type (no second generic registry) |
| `QgsVectorLayerPlotDataGatherer` | QgsTask gather pattern | reference for future async loads | — | no | **Avoid** (no vector-layer coupling in A-line) |
| `QgsApplication::plotRegistry()` | exists (pre-populated) | informational | — | no | **Reuse** nothing; documented only |

## Behavior parity mapping (existing feature → kernel primitive → B-line feature)

| Existing (geoviz_well_log) | A-line primitive | B-line (domain) | Status in A |
|---|---|---|---|
| curve track render | `WellTrackRenderer` + `CurveSeriesView` + LOD | curve domain object maps to view | spec'd |
| depth ruler column | `TrackSpec::Role::DepthRuler` + `calculateOptimisedIntervals` | chooses unit/labels | spec'd |
| track ordering/visibility/width | `WellTrackModel` track list + `TrackLayout` | persists/edits ordering | spec'd |
| merge/split curve tracks | model composition (curves per track) | owns merge policy | out of A scope |
| wheel zoom @ cursor | `WellTrackCanvas::wheelZoom` | — | spec'd |
| drag pan | `QgsPlotToolPan` + `panContentsBy` | — | reused |
| marquee zoom | `WellTrackDepthZoomTool` (vertical band) | — | spec'd |
| multi-canvas depth sync | `WellTrackSynchronizer` | cross-well correlation UI | spec'd |
| hover readout | `WellTrackCursorTool` + hit tester | tooltip formatting | spec'd |
| crosshair overlay | crosshair `QgsPlotCanvasItem` (z=100) | — | spec'd |
| SVG/PDF/PNG export | renderer renders into any QPainter | export service | spec'd (single render path) |
| lithology/facies pattern tracks | generic `DepthIntervalBand` (QBrush fill) | lithology semantics + SVG patterns | A provides brush primitive only |
| marker overlay track | generic `DepthMarkerLine` + `TextAnchor` | tops/horizons semantics | spec'd |
| scrollbar depth virtualization | not in A (host viewport widget, B) | product scroll UX | out of A scope |

## Non-goals enforced by this matrix

- No second generic axis engine: axis *math* is 4 linear/log mappings in one
  file; styling/intervals come from `QgsPlotAxis` + upstream optimizer.
- No second zoom/pan framework: all gestures flow through QGIS tools and
  canvas virtuals.
- No second registry, no second scene/canvas lifecycle.
