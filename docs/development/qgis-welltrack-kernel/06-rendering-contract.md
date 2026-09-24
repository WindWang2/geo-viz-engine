# 06 — Rendering contract

## Single render path

`WellTrackRenderer::render(QPainter*, rect, model, depthDomain)` is the only
painting code. Screen path: canvas scene item → cached QImage → blit. Export
path: host constructs `QSvgGenerator`/`QPrinter`/`QImage`, calls the same
`render`. Crosshair/cursor overlays are separate scene items and therefore
never appear in exports (same doctrine as `WellLogCanvas.paint_all`).

## Frame pipeline

```
model snapshot (shared_ptr, generation g)
  → computeTrackLayout(model, targetRect, options)          [cache: size/visibility/widths/g]
  → per visible CurveTrack:
      axis label layout (TrackAxisSpec + QgsTextFormat)      [cache: axis config + width]
      per curve:
        visibleSlice(view, depthDomain, ±5% margin)          O(log n)
        buildEnvelope(view, slice, bins=contentHeight)       O(slice)
                                                             [cache: (g, curve, bins,
                                                              quantized depth window)]
        transform → QPolygonF subpaths (break at NaN/breakAfter)
  → paint order: background → grid (QgsPlotAxis symbols) → bands → fills →
     lines → markers → depth marker lines → texts → headers+scale labels →
     depth ruler → separators → border
  → RenderStats filled (counts + QElapsedTimer µs)
```

## Coordinate transforms (all linear, all in one place)

- Depth: `y = contentRect.top + normalize(depth) * contentRect.height`;
  orientation flips only `normalize`. `normalize` uses
  `(d - topEdge)/(bottomEdge - topEdge)` in *screen order*, where topEdge is
  `shallow` for `IncreasingDown` and `deep` for `IncreasingUp`. Degenerate
  span (==) → all depths map to center; `isValid()` guards callers.
- Value: `x = left + (mapToUnit(v) - mapToUnit(min)) / (mapToUnit(max) -
  mapToUnit(min)) * width`; `Log10` clamps to `logFloor` (default 1e-10,
  reference behavior from `curve_track.py:159-165`); degenerate range →
  center. NaN → gap (never clamped to an edge).
- Canvas↔plot: canvas position minus `contentTopLeft()` then inverted through
  the same two transforms; `toMapCoordinates` returns
  `QgsPoint(valueAtX, depthAtY)` for the track under x; outside any track →
  x-component NaN. Documented: "canvas coordinates" = viewport-local pixels
  (scene coords are identical: the view is unscaled/unscrolled, matching the
  upstream elevation canvas).

## Clipping and gaps

- Every curve/fill/band draw is wrapped in `painter->save();
  setClipRect(contentRect, Qt::IntersectClip); ...; painter->restore()`.
- NaN values and `breakAfter` envelope flags close the current subpath; a new
  subpath starts at the next finite sample. No bridging lines across gaps
  (pinned by test_renderer gap probe).
- Curves spanning the full depth range draw outside contentRect are clipped
  by the same rect (no manual bounds math on the hot path).

## Hi-DPI

Renderer works in painter (logical) units exclusively. DPR is handled once at
the scene item: cache QImage is `rect * devicePixelRatioF()` with
`setDevicePixelRatio`, painted via `QgsRenderContext::fromQPainter` +
`setDevicePixelRatio` (upstream elevation pattern). Export devices
(QSvgGenerator/QPrinter at set DPI) need nothing special.

## Depth ruler & grid intervals

Interval selection delegates to `Qgs2DXyPlot::calculateOptimisedIntervals`
(public API) hosted by an internal `Qgs2DXyPlot` instance configured with the
current depth span + ruler text format; resulting major interval feeds both
grid lines and ruler labels (1-2-5 steps, label-coverage optimized — replaces
the Python `nice_depth_interval` heuristic with the QGIS equivalent).

## Interaction semantics (canvas virtuals)

- `panContentsBy(dx,dy)`: `Δdepth = -dy * span / contentHeight` (drag paper,
  not viewport — upstream semantic); `dx` ignored (no horizontal pan in v1).
- `scalePlot(f)`: zoom around content center; `f` in (0, ∞), clamped so span
  stays within `[minSpan=1e-9, 1e12]`.
- `zoomToRect(rect)`: depth window = depths at rect top/bottom; rect height <
  2 px or inverted → no-op; x-extent ignored (depth-only zoom).
- `wheelZoom`: anchor = cursor depth; factor from wheel delta; Ctrl = fine
  (upstream elevation behavior), unbounded range but clamped span as above.
- `centerPlotOn(x,y)`: center depth at y.
- `snapToPlot(point)`: nearest sample within 10 px via hit tester; empty
  `QgsPointXY()` on miss (upstream contract).
- All of the above funnel through one `applyDepthRange(shallow, deep,
  origin)` private that validates, applies the `<1e-9` no-op guard, bumps
  item cache, emits `depthRangeChanged` — the only mutation path (single
  writer discipline).

## Ownership & lifetime

- Model: `shared_ptr` owned by host; canvas holds a copy; renderer/hit-tester
  take `const&` only. Series views borrow host memory — the host guarantees
  buffer lifetime ≥ model snapshot lifetime (documented; debug-build check
  helper provided).
- Scene items: parented to canvas (`QgsPlotCanvasItem` registers itself);
  canvas destructor deletes items before base (Qt ownership + explicit
  `deleteLater` discipline on crosshair).
- Tools: `QObject` children of canvas (`SIP_TRANSFERTHIS` pattern is C++ ctor
  parent here); QGIS auto-unset handles tool destruction order.
- Synchronizer: `QPointer` list; disconnects on `destroyed`.

## Threading

- Core pure-data functions (`visibleSlice`, `buildEnvelope`, layout) are
  thread-safe given immutable view buffers — hosts may pre-warm LOD on
  workers. GUI objects, painter, canvas, and model *mutations* are
  main-thread only. Renderer itself is reentrant across threads only on
  separate painters (documented; not exercised in v1 beyond tests).
