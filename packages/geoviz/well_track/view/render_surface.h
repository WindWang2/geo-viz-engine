// The frozen render-kernel seam (docs 04). Everything in this package draws
// through IWellTrackSurface; the only production implementation is
// QgisSurface (src/view/qgis_surface.cpp, built when GeoViz::QgisWellTrack
// from Prompt A is available). No QGIS types cross this boundary.
//
// Division of responsibility:
//   * the surface owns the viewport widget, input events, depth<->pixel
//     mapping, column painting, hit testing and the render substrate;
//   * the controller owns product rules (clamping, min span, no-op guards),
//     layout configuration and inspection semantics.
//
// All methods are GUI-thread only. Column payloads are plain value structs;
// curve payloads share immutable CurveBufferPtr (zero-copy handoff).
#pragma once

#include <optional>
#include <string>
#include <vector>

#include <QColor>
#include <QObject>
#include <QPointF>
#include <QRectF>
#include <QString>

#include "geoviz/well_track/domain/curve.h"
#include "geoviz/well_track/domain/curve_style.h"
#include "geoviz/well_track/domain/ids.h"
#include "geoviz/well_track/domain/images.h"
#include "geoviz/well_track/domain/intervals.h"
#include "geoviz/well_track/data/data_source.h"

namespace geoviz::well_track {

enum class SurfaceColumnKind : std::uint8_t {
    DepthAxis,      // tick labels column (ticks computed by the controller)
    Curve,          // one or more curve layers + range grid labels
    Interval,       // categorized rows (rect/triangle, solid or pattern)
    MarkerOverlay,  // full-canvas dashed top lines
    Image,          // image segments (capability-gated)
};

struct SurfaceCurveLayer {
    CurveId curveId;
    CurveBufferPtr data;  // may be null while a reload is in flight
    std::string label;
    QColor color;
    double lineWidth = 1.5;
    LineStyle lineStyle = LineStyle::Solid;
    XRange xRange;  // effective range already resolved by the controller
};

struct SurfaceIntervalRow {
    double top = 0.0;
    double bottom = 0.0;
    std::string label;
    std::uint32_t fillRgba = 0xFFD4E6F1;
    std::string patternAssetPath;  // empty -> solid fill; kernel materializes
    IntervalShape shape = IntervalShape::Rect;
    int subColumn = -1;            // facies nested: 0/1/2; -1 for full width
    int subColumnCount = 1;
};

struct SurfaceMarkerRow {
    double depth = 0.0;
    std::string label;
    QColor color;
};

struct SurfaceTick {
    double depth = 0.0;
    std::string text;
};

struct SurfaceHeaderEntry {
    std::uint32_t swatchRgba = 0;
    bool hasSwatch = false;
    std::string line1;  // e.g. curve name
    std::string line2;  // e.g. "min~max unit"
};

struct SurfaceTrackColumn {
    TrackId trackId;
    SurfaceColumnKind kind = SurfaceColumnKind::Curve;
    std::string title;
    int width = 60;
    SurfaceHeaderEntry header;

    std::vector<SurfaceCurveLayer> curves;
    std::vector<SurfaceIntervalRow> intervals;
    std::vector<SurfaceMarkerRow> markers;
    std::vector<SurfaceTick> ticks;  // DepthAxis
    std::vector<ImageSegment> images;
};

struct SurfaceHit {
    bool valid = false;
    TrackId trackId;
    double depth = 0.0;
};

class IWellTrackSurface : public QObject {
    Q_OBJECT
public:
    explicit IWellTrackSurface(QObject* parent = nullptr) : QObject(parent) {}
    ~IWellTrackSurface() override = default;

    // Viewport widget; the surface keeps ownership (widget parented to it or
    // to the host-provided parent). Must be non-null once created.
    virtual QWidget* widget() = 0;

    // --- column sync (controller -> surface) ---
    virtual void setTracks(std::vector<SurfaceTrackColumn> columns) = 0;
    virtual void updateTrack(const SurfaceTrackColumn& column) = 0;
    virtual void removeTrack(const TrackId& trackId) = 0;

    // --- viewport state ---
    virtual void setDepthRange(double top, double bottom) = 0;
    virtual void setFullDepthRange(double top, double bottom) = 0;
    virtual void setSecondaryAxis(IDepthTransformService* transform) = 0;

    // --- queries (controller <- surface) ---
    virtual SurfaceHit trackAt(const QPointF& pos) const = 0;
    virtual std::optional<CurveId> hitCurve(const QPointF& pos, double tolerancePx) const = 0;
    virtual double depthAt(const QPointF& pos) const = 0;  // NaN outside content
    virtual int yPosForDepth(double depth) const = 0;     // -1 when unknown
    virtual double depthPerPixel() const = 0;              // 0 when unknown
    virtual int contentHeight() const = 0;                 // 0 when unknown
    // Column geometry in surface-widget coordinates (for overlays).
    virtual QRectF trackGeometry(const TrackId& trackId) const = 0;
    // Capability probe: image segment rendering (v1 kernels may refuse).
    virtual bool supportsImageTracks() const = 0;

signals:
    // Viewport intent raised by kernel-native tools. The controller applies
    // product rules (clamp / min span / no-op) before writing back.
    void depthRangeRequested(double top, double bottom);
    void fitRequested();
    void cursorMoved(double depth, const QString& trackId);
    void trackHeaderClicked(const QString& trackId);
    void viewportResized(int contentHeight);
};

}  // namespace geoviz::well_track
