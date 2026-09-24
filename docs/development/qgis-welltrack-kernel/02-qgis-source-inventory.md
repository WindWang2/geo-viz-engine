# 02 — QGIS plot source inventory (exact snapshot: 4.2.0 / final-4_2_0)

All facts below were read from the vendored snapshot at
`paleo-workbench main/third_party/qgis` @ `192422c60` (upstream
`final-4_2_0` @ `ca5812c8`), which is byte-identical in the plot area to what
the installed SDK (`libqgis_core.so.4.2.0`, `libqgis_gui.so.4.2.0`) was built
from. Line references use the snapshot files.

## src/core/plot (6 classes + registry + gatherer)

| Class | File | Role | Key facts for well tracks |
|---|---|---|---|
| `QgsPlot` | qgsplot.h:47 | DD properties + XML base | not a QObject; copy disabled |
| `QgsPlotRenderContext` | qgsplot.h:190 | **empty class** (ctor+dtor only) | carries nothing; real state is in `QgsRenderContext` |
| `QgsAbstractPlotSeries` / `QgsXyPlotSeries` | qgsplot.h:209/262 | series data | `QList<std::pair<double,double>>`, `data()` returns **by value**; per-point copy cost — unusable for 1e5+ samples |
| `QgsPlotData` | qgsplot.h:302 | series container | owns `QgsAbstractPlotSeries*` list |
| `QgsPlotAxis` | qgsplot.h:353 | axis *style* bag | intervals (minor/major/label), `QgsLineSymbol` grid symbols, `QgsTextFormat`, `QgsNumericFormat`, suffix+placement; **no scale, no inversion, no tick query** — ticks are computed inline in `Qgs2DXyPlot::render` |
| `Qgs2DPlot` | qgsplot.h:584 | size(mm)+margins(mm), `render()`/`renderContent()` virtuals | `renderContent()` is the sanctioned extension point (after grid+labels, before border) |
| `Qgs2DXyPlot` | qgsplot.h:686 | min/max + 2 axes + flip | `calculateOptimisedIntervals()` is **public**; y mapping fixed upward (`py = bottom - (v-minY)*yScale`, qgsplot.cpp:660) |
| `QgsLineChartPlot` | qgslinechartplot.h:41 | line series renderer | multi-series symbol rotation; NaN → null QPointF breaks; two container copies per render; per-point DD expression injection |
| `QgsBarChartPlot` / `QgsPieChartPlot` | respective | bar/pie | not relevant to tracks |
| `QgsPlotRegistry` | qgsplotregistry.h | plot *type* registry | `QgsApplication::plotRegistry()` exists (qgsapplication.h:967), pre-populated with bar/line/pie; registry serves QgsPlotWidget creation from vector layers — **no role for a bespoke track canvas; we will not register a new generic type** (explicitly out of scope) |
| `QgsVectorLayerPlotDataGatherer` | qgsvectorlayerplotdatagatherer.h:146 | QgsTask-based feature→series collection | async gather pattern reference only |

`Qgs2DXyPlot::render` flow (qgsplot.cpp:474-867): push expression scope →
startRender symbols → apply DD overrides → optional flip swap → first
grid/label value = `ceil(min/interval)*interval` → `interiorPlotArea()` →
measure max y-label width → background → x grid → y grid → x labels → y
labels → `renderContent()` virtual → border → stopRender.
`interiorPlotArea` (qgsplot.cpp:871-1040) reserves left (y labels + 1 mm) and
bottom (x labels + 0.5 mm); right/top reservations are hardcoded 0.
`calculateOptimisedIntervals` (qgsplot.cpp:1042-1192): targets ~40% label
coverage, 1-2-5 steps.

## src/gui/plot (canvas shell + tools — all installed public headers)

| Class | File | Key facts |
|---|---|---|
| `QgsPlotCanvas` | qgsplotcanvas.h:54 | `QGraphicsView` shell. Owns scene + 3 transient tools. Event chain: mouse→`QgsPlotTool::plot*Event`→(mid-button→transient pan; right+flag→context menu)→QGraphicsView; wheel→tool→virtual `wheelZoom()`; Space/Ctrl+Space transient tools; gestures→tool. **Virtuals `refresh/panContentsBy/centerPlotOn/scalePlot/zoomToRect/snapToPlot/toMapCoordinates/toCanvasCoordinates/wheelZoom` are default-empty** — subclass implements (this is by design; `QgsElevationProfileCanvas` is the in-tree full implementation). Signals: `toolChanged`, `plotAreaChanged`, `contextMenuAboutToShow`, `willBeDeleted`. No setPlot, no linking. |
| `QgsPlotCanvasItem` | qgsplotcanvasitem.h:39 | abstract scene item; adds itself to canvas scene; `paint(QPainter*)` pure virtual; does **not** call plot->render itself |
| `QgsPlotTool` | qgsplottool.h:58 | QObject; auto-unset on destroy via `willBeDeleted`; default handlers `ignore()`; `activate()` checks QAction + sets cursor; flags: `ShowContextMenu` only |
| `QgsPlotToolPan` | qgsplottoolpan.h:31 | drag → `canvas()->panContentsBy(dx,dy)`; mid-click → `centerPlotOn`; OpenHand/ClosedHand cursors — **reusable as-is once the canvas implements panContentsBy** |
| `QgsPlotToolZoom` | qgsplottoolzoom.h:34 | marquee via `QgsPlotRectangularRubberBand`; click → `zoomInClickOn`/`zoomOutClickOn` (default: center+×2 / center+×0.5); drag → `canvas()->zoomToRect(constrainBounds(finish()))`. **C++-only protected virtuals `constrainStartPoint/constrainMovePoint/constrainBounds/zoomOutClickOn/zoomInClickOn` are the sanctioned specialization hooks** |
| `QgsPlotToolXAxisZoom` | qgsplottoolxaxiszoom.h | hard-bound to `QgsElevationProfileCanvas*` in ctor — not directly reusable; pattern to imitate for a depth-axis zoom tool via `QgsPlotToolZoom` hooks |
| `QgsPlotMouseEvent` | qgsplotmouseevent.h:39 | QMouseEvent subclass; `mapPoint()` = `canvas->toMapCoordinates(pos)`; `snappedPoint()` lazily calls `canvas->snapToPlot` |
| `QgsPlotRubberBand` / `QgsPlotRectangularRubberBand` | qgsplotrubberband.h:38/123 | rect band as QGraphicsRectItem z=1000; Shift=square, Alt=center; `finish()` returns QRectF and removes item |
| transient tools | qgsplottransienttools.h | Space-pan, Ctrl+Space-zoom, mid-button pan; auto-restore previous tool |
| `QgsPlotWidget` | qgsplotwidget.h | property panel (QgsPanelWidget) for bar/line/pie plot settings — **not a canvas**; no role here |

## Reference implementation inside QGIS: `QgsElevationProfileCanvas`

`src/gui/elevation/qgselevationprofilecanvas.cpp` is the only full
`QgsPlotCanvas` subclass in-tree and therefore the architectural template this
kernel follows:

- `QgsElevationProfilePlotItem : Qgs2DXyPlot, QgsPlotCanvasItem` (line 53) —
  the plot object itself is the scene item.
- `updateRect()` syncs `setSize(canvas->rect().size())` on resize/first paint
  (67-79, 1274-1308).
- Hand-written `canvasPointToPlotPoint` / `plotPointToCanvasPoint` (187-208) —
  QGIS provides **no public plot↔pixel API**; the in-tree answer is linear
  inversion around `interiorPlotArea()`.
- Whole-canvas QImage cache at `rect * devicePixelRatioF` with
  `setDevicePixelRatio`, painted through `QgsRenderContext::fromQPainter` +
  `rc.setDevicePixelRatio` (239-271).
- Canvas virtuals implemented: `panContentsBy` (negated drag, 473-492),
  `centerPlotOn` (494-515), `scalePlot` around center (753-785),
  `zoomToRect` pixel→range (787-812), `wheelZoom` cursor-anchored with
  settings zoom factor + Ctrl fine-zoom (814-868), coordinate transforms
  (1310-1360). Crosshair item z=100 (431); rubberband z=1000 upstream.

## Header/install status

- All 10 gui/plot headers are in `QGIS_GUI_HDRS` and installed
  (`src/gui/CMakeLists.txt:1435-1444`); all 6 core/plot headers in
  `QGIS_CORE_HDRS` (`src/core/CMakeLists.txt:1805-1810`). The SDK consumes
  them from the source tree via `PwbQgis::Sdk` include closure, which is what
  this package mirrors.

## Gaps that a well-track plot must fill itself (each is a public-API dead end)

1. **Depth (y) axis inversion** — no `setInverted` anywhere in the plot API;
   the grid loop `for (y = ceil(min/int)*int; y <= max; y += int)` collapses
   if min>max. Well tracks need depth increasing downward.
2. **Multi-column layout** — one `Qgs2DXyPlot` = exactly one x/y axis pair
   with shared interior margins; N track columns need an outer layout.
3. **Shared depth viewport** — no canvas linking API; only `plotAreaChanged`.
4. **Plot↔pixel transforms / hit-testing** — none public; `snapToPlot` is an
   empty virtual waiting for an implementation.
5. **Big-sample LOD** — series containers copy per render; no decimation.
6. **Vertical-only zoom semantics** — `QgsPlotToolXAxisZoom` is bound to the
   elevation canvas; the zoom hooks exist but a depth-axis variant must be
   written (subclassing, not copying).

These six gaps define exactly the surface our kernel implements; everything
else (canvas event plumbing, tool lifecycle, rubber band, transient tools,
axis styling objects, interval optimization, text/numeric formatting, symbol
rendering) is reused through the SDK's public API.
