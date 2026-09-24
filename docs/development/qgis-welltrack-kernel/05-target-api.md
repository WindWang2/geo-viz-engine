# 05 — Target public API (frozen at review 0)

Namespace `geoviz::qgis_welltrack`. Two libraries:

- `GeoViz::QgisWellTrackCore` — Qt6::Core/Gui + QGIS Core only. Pure data +
  layout + LOD + renderer + hit-testing. No QtWidgets, no QgsPlotCanvas. Can
  render into any `QPainter` (window, `QSvgGenerator`, `QPrinter`, `QImage`).
- `GeoViz::QgisWellTrack` — QtWidgets + QGIS Gui. `WellTrackCanvas`
  (subclass of `QgsPlotCanvas`), tools, crosshair overlay, synchronizer.

Dependency rule: gui → core, never the reverse; nothing depends on
paleo-workbench, on `packages/geoviz_well_track_native` (B-line), on Python,
or on PySide6.

## Core value types (headers are the contract; names may drift, duties may not)

```cpp
// depth_domain.h
enum class DepthOrientation { IncreasingDown, IncreasingUp };  // well default: Down
struct DepthDomain {                       // the shared vertical viewport
    double shallow = 0.0, deep = 1.0;      // depth units; shallow is the top edge when Down
    DepthOrientation orientation = DepthOrientation::IncreasingDown;
    bool isValid() const;                  // finite, non-degenerate after normalization
    double normalize(double d) const;      // → [0,1] across the viewport; NaN outside handling documented
    double depthAtFraction(double t) const;
    double depthAtY(double y, const QRectF &contentRect) const;
    double yForDepth(double depth, const QRectF &contentRect) const;   // may be outside rect (clip at caller)
    double fullSpan...                     // (shallow→deep numeric span, absolute)
};

// curve_data.h — non-owning sample view; no QObject, no copies
enum class SampleFormat { Float32, Float64 };
struct CurveSeriesView {
    const void *depths = nullptr;  const void *values = nullptr;
    qsizetype count = 0;
    SampleFormat format = SampleFormat::Float64;
    qsizetype depthStrideBytes = 0;  // 0 → natural element size
    qsizetype valueStrideBytes = 0;
    double depthAt(qsizetype i) const;   // memcpy-loaded (unaligned/stride safe)
    double valueAt(qsizetype i) const;
    bool isEmpty() const;
};
// Contract: depths strictly usable with binary search → non-decreasing
// (ascending). NaN depths are a caller bug; `validateDepthMonotonic()` is
// provided (debug + opt-in runtime check returning first violation index).

// curve_lod.h — visible-range slicing + extrema-preserving envelope
struct VisibleSlice { qsizetype begin = 0, end = 0; };            // [begin, end)
VisibleSlice visibleSlice(const CurveSeriesView &v, double fromDepth, double toDepth,
                          double marginFraction = 0.05);
struct EnvelopeSample { double depth; double value; bool breakAfter; };
// Bin = one screen depth-row. Per bin, emits min and max sample in original
// index order (oracle: geoviz_well_log downsample.py contract); a bin with
// NaN emits a trailing break marker so polylines never bridge gaps.
void buildEnvelope(const CurveSeriesView &v, VisibleSlice slice, int bins,
                   std::vector<EnvelopeSample> &out);
```

## Model (render snapshot; cheap shared ownership; no QObject)

```cpp
// curve_style.h
enum class ValueScale { Linear, Log10 };
enum class FillMode { None, ToBaseline, BetweenSeries };
enum class MarkerShape { None, Circle, Square, Diamond, Cross };
struct CurveStyle {
    Qt::GlobalColor/QColor lineColor; double lineWidthF = 1.0;
    Qt::PenStyle penStyle = Qt::SolidLine;
    MarkerShape marker = MarkerShape::None; double markerSizeF = 3.0;
    FillMode fill = FillMode::None; double fillBaseline = 0.0; // axis units
    QColor fillColor; qreal fillOpacity = 0.25;
    // BetweenSeries: partner curve identified by CurveSpec::partnerId
};

// axis_spec.h — value axis per track; styling delegated to QGIS QgsPlotAxis
struct TrackAxisSpec {
    double minimum = 0.0, maximum = 1.0;
    ValueScale scale = ValueScale::Linear;
    double logFloor = 1e-10;                 // log-domain clamp (reference behavior)
    std::unique_ptr<QgsPlotAxis> style;      // QGIS: grid symbols, text format, numeric format, suffix
    double mapToUnit(double v) const;        // Linear → v, Log10 → clamped log10
    double mapFromUnit(double u) const;
    double xForValue(double v, const QRectF &r) const;   // + clamp, degenerate → center
    double valueForX(double x, const QRectF &r) const;
};

// track_model.h
enum class TrackRole { CurveTrack, DepthRuler };
struct CurveSpec { quint64 id; QString label; CurveSeriesView data; CurveStyle style;
                   quint64 partnerId = 0; /* fill-between */ };
struct DepthIntervalBand { double top, bottom; QBrush fill; QString label; QColor labelColor; };
struct DepthMarkerLine  { double depth; QColor color; Qt::PenStyle pen; double widthF;
                          QString label; Qt::AnchorAnchor... /* label side */ };
struct TextAnchor       { double depth; QString text; /* side/rotation */ };
struct TrackSpec {
    quint64 id;  QString title;  TrackRole role = TrackRole::CurveTrack;
    bool visible = true;
    std::optional<double> fixedWidth;       // else stretch
    TrackAxisSpec axis;                     // CurveTrack only
    std::vector<CurveSpec> curves;          // series views stay non-owning!
    std::vector<DepthIntervalBand> bands;
    std::vector<DepthMarkerLine> markers;   // horizontal lines at depth
    std::vector<TextAnchor> texts;
};
class WellTrackModel {                       // ref-counted snapshot holder
public:
    static std::shared_ptr<WellTrackModel> create();
    TrackSpec *appendTrack(); void removeTrack(quint64 id); TrackSpec *track(quint64 id);
    quint64 generation() const;              // bumped by every mutation; cache key input
    ... copyTrackOrder / visibility helpers ...
private: std::vector<std::shared_ptr<TrackSpec>> mTracks; quint64 mGeneration = 1;
};
```

Series data lifetime rule (documented in headers): `CurveSeriesView` borrows
caller-owned memory; the model snapshot is only as alive as the buffers it
views. Hosts either keep buffers alive or call `setModel` with a new snapshot
before releasing them. The kernel never copies sample arrays on the render
path.

## Layout

```cpp
// track_layout.h
struct TrackLayoutOptions { double headerHeight = 40; double separatorWidth = 1;
                            QMarginsF outerMargins{1,1,1,1}; int depthRulerWidth = 72; };
struct TrackGeometry { int trackIndex; bool visible; QRectF columnRect;   // full column
                       QRectF headerRect; QRectF contentRect; };
struct TrackLayoutResult {
    std::vector<TrackGeometry> tracks;     // visible tracks, x-ascending
    QRectF contentArea;                    // union of contentRects (depth area)
    int trackAtX(double x) const;          // -1 if none; index into `tracks`
    const TrackGeometry *geometryForTrackId(quint64 id) const;
};
TrackLayoutResult computeTrackLayout(const WellTrackModel &m, const QRectF &targetRect,
                                     const TrackLayoutOptions &o = {});
```

## Renderer (core; single render path for screen and export)

```cpp
// welltrack_renderer.h
struct RenderStats { qsizetype rawSamplesInSlices = 0, envelopePoints = 0;
                     int polylines = 0, subpathBreaks = 0; qint64 prepUsec = 0, paintUsec = 0; };
class WellTrackRenderer {
public:
    explicit WellTrackRenderer();
    void setStyle(const KernelStyle &s);         // QGIS-default look via QgsPlotDefaultSettings
    void render(QPainter *p, const QRectF &targetRect, const WellTrackModel &model,
                const DepthDomain &depth, RenderStats *stats = nullptr);
    // draws: backgrounds → per-track grid (QgsPlotAxis symbols via QgsRenderContext)
    // → bands → fills → curve lines/markers → markers/texts → headers/scales
    // → depth ruler → separators/border. Every track content clipped to contentRect.
    // Hi-DPI: caller ensures painter device DPR; renderer is DPR-agnostic (painter units).
};
```

## Hit testing

```cpp
// hit_testing.h
struct HitResult { bool hit = false; quint64 trackId = 0, curveId = 0; qsizetype sampleIndex = -1;
                   double depth = 0, value = 0; double screenDistPx = 0; };
HitResult hitTestNearestSample(const WellTrackModel &m, const TrackLayoutResult &l,
                               const DepthDomain &d, QPointF pos, double tolerancePx = 10.0);
```

## GUI

```cpp
// well_track_canvas.h
class WellTrackCanvas : public QgsPlotCanvas {
    Q_OBJECT
public:
    explicit WellTrackCanvas(QWidget *parent = nullptr);
    ~WellTrackCanvas() override;
    void setModel(std::shared_ptr<WellTrackModel> model);
    std::shared_ptr<WellTrackModel> model() const;
    void setDepthDomain(const DepthDomain &d);          // validates; <1e-9 no-op guard
    DepthDomain depthDomain() const;
    void zoomToDepth(double shallow, double deep);
    void fitDepth(const WellTrackModel *m = nullptr);   // to model extent
    double depthAt(const QPointF &canvasPos) const;
    QPointF contentTopLeft() const;                      // header/ruler offsets honored
    QRectF contentRect() const;
    // QgsPlotCanvas virtuals implemented (the QGIS-blessed adaptation surface):
    void refresh() override;  void panContentsBy(double dx, double dy) override;  // vertical→depth
    void centerPlotOn(double x, double y) override;     void scalePlot(double f) override;
    void zoomToRect(const QRectF &rect) override;       // canvas-px rect → depth window (x ignored)
    QgsPoint toMapCoordinates(const QgsPointXY &) const override;  // (track value at x, depth at y)
    QgsPointXY toCanvasCoordinates(const QgsPoint &) const override;
    QgsPointXY snapToPlot(QPoint point) override;       // nearest sample (hit tester)
    QgsCoordinateReferenceSystem crs() const override;  // invalid CRS
signals:
    void depthRangeChanged(double shallow, double deep);   // after any zoom/pan/set
    void cursorDepthChanged(double depth);                 // NaN = left content area
    void sampleHovered(geoviz::qgis_welltrack::HitResult hit); // registered metatype
protected:
    void wheelZoom(QWheelEvent *e) override;            // cursor-anchored vertical zoom
protected:
    void resizeEvent(QResizeEvent *e) override;         // → item updateRect (upstream pattern)
    // scene composition (z-order per upstream convention): content item z=0, crosshair z=100
    // rubberband from QGIS tools sits at z=1000
};

// well_track_tools.h
class WellTrackDepthZoomTool : public QgsPlotToolZoom {   // marquee→depth window; click=×2/×0.5
protected: QPointF constrainStartPoint(QPointF) const override;   // x→plot area horizontal center band start
           QPointF constrainMovePoint(QPointF) const override;    // free x (band shows full width)
           QRectF constrainBounds(const QRectF &) const override; // x→full width; min height guard
           void zoomInClickOn(QPointF) override;  void zoomOutClickOn(QPointF) override; };
class WellTrackCursorTool : public QgsPlotTool {          // readout + crosshair
    void plotMoveEvent(QgsPlotMouseEvent *e) override; void plotReleaseEvent(...) override;
    void deactivate() override; };

// depth_synchronizer.h
class WellTrackSynchronizer : public QObject {
public: explicit WellTrackSynchronizer(QObject *parent = nullptr);
    void addCanvas(WellTrackCanvas *c);  void removeCanvas(WellTrackCanvas *c);
    // anti-feedback: single dispatcher flag + per-canvas blockSignals-free no-op guard
};
```

Pan tool: **used as-is** (`QgsPlotToolPan`) — QGIS owns the gesture; the
canvas's `panContentsBy` restricts it to the depth axis. Transient tools
(Space pan, Ctrl+Space zoom, middle-button pan) come free from
`QgsPlotCanvas`.

## Explicit non-API

- No `WellId`/`HorizonId`/`Lithology`/`Facies`/project/repo types (B-line owns).
- No MD/TVD/TVDSS/TWT conversion — kernel is unit-agnostic numeric depth.
- No persistence, no config files, no Python bindings in v1.
- No new plot-type registration in `QgsPlotRegistry`.
