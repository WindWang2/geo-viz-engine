// QgisSurface — the only production implementation of IWellTrackSurface.
// Bridges the frozen seam onto Prompt A's GeoViz::QgisWellTrack
// (geoviz::qgis_welltrack). Built only when GEOVIZ_WELL_TRACK_WITH_QGIS_KERNEL
// is on (docs 04). This file is the single place where A's types are named.
//
// Mapping notes (reconciled against A @ feat/qgis-plot-welltrack-kernel
// ebe9b70f — see docs/14 for the full reconciliation table):
//  * Curve data: A borrows raw arrays (CurveSeriesView); we retain the
//    CurveBufferPtr per track so the borrowed memory outlives every model
//    snapshot referencing it (A's documented contract).
//  * Depth axis: A renders ruler labels natively; the seam's tick list is
//    provided for kernels without native rulers and is not forwarded.
//  * Facies nested sub-columns: A v1 has no sub-column bands; nested rows
//    degrade to the deepest level (parity with Python's non-nested mode).
//  * Markers: attached to every curve track so the dashed tops read as a
//    full-canvas overlay (Python MarkerTrack parity).
//  * Secondary TWT axis: A v1 exposes no secondary-axis API; the transform
//    is accepted and ignored until A grows one (docs 14 open item).
#include <QEvent>
#include <QFileInfo>
#include <QPainter>
#include <QPixmap>
#include <QSvgRenderer>

#include <cmath>
#include <map>
#include <string>
#include <unordered_map>
#include <vector>

#include "geoviz/qgis_welltrack/track_layout.h"
#include "geoviz/qgis_welltrack/well_track_canvas.h"
#include "geoviz/qgis_welltrack/well_track_tools.h"

#include "geoviz/well_track/view/render_surface.h"
#include "geoviz/well_track/view/surface_factory.h"

namespace geoviz::well_track {

namespace {

using ACanvas = geoviz::qgis_welltrack::WellTrackCanvas;
using ATrackId = geoviz::qgis_welltrack::TrackId;  // quint64
using ASeriesId = geoviz::qgis_welltrack::SeriesId;

QColor toColor(std::uint32_t rgba) {
    return QColor((rgba >> 16) & 0xFF, (rgba >> 8) & 0xFF, rgba & 0xFF, (rgba >> 24) & 0xFF);
}

Qt::PenStyle toPenStyle(LineStyle s) {
    switch (s) {
        case LineStyle::Solid: return Qt::SolidLine;
        case LineStyle::Dashed: return Qt::DashLine;
        case LineStyle::Dotted: return Qt::DotLine;
    }
    return Qt::SolidLine;
}

// Tiled pattern brush (pattern_engine.py parity: QSvgRenderer -> 20 px tile).
// Cache is keyed by asset path; GUI-thread single-threaded contract.
QBrush patternBrush(const std::string& assetPath) {
    static std::map<std::string, QBrush> cache;
    const auto it = cache.find(assetPath);
    if (it != cache.end()) return it->second;
    QBrush brush;
    if (QFileInfo::exists(QString::fromStdString(assetPath))) {
        QSvgRenderer renderer(QString::fromStdString(assetPath));
        if (renderer.isValid()) {
            QPixmap tile(20, 20);
            tile.fill(Qt::transparent);
            QPainter p(&tile);
            renderer.render(&p);
            p.end();
            brush = QBrush(tile);
        }
    }
    cache[assetPath] = brush;
    return brush;
}

}  // namespace

class QgisSurface : public IWellTrackSurface {
    Q_OBJECT
public:
    explicit QgisSurface(QWidget* parent = nullptr)
        : canvas_(new ACanvas(parent)), model_(geoviz::qgis_welltrack::WellTrackModel::create()) {
        canvas_->setModel(model_);
        // Kernel-native tools: cursor readout + depth zoom (A owns gestures).
        auto* cursorTool = new geoviz::qgis_welltrack::WellTrackCursorTool(canvas_);
        zoomTool_ = new geoviz::qgis_welltrack::WellTrackDepthZoomTool(canvas_);
        canvas_->setTool(cursorTool);

        canvas_->installEventFilter(this);
        connect(canvas_, &ACanvas::depthRangeChanged, this,
                [this](double shallow, double deep) {
                    // Kernel-side pan/zoom intent; the controller applies the
                    // product rules and writes back via setDepthRange (the
                    // no-op guards on both sides terminate the echo).
                    emit depthRangeRequested(shallow, deep);
                });
        connect(canvas_, &ACanvas::cursorDepthChanged, this, [this](double depth) {
            emit cursorMoved(depth, QString());
        });
    }

    QWidget* widget() override { return canvas_; }

    void setTracks(std::vector<SurfaceTrackColumn> columns) override {
        model_ = geoviz::qgis_welltrack::WellTrackModel::create();
        trackIds_.clear();
        seriesIds_.clear();
        retained_.clear();
        // Two passes: first the non-marker columns (layout), then marker
        // rows get attached to every curve track (full-canvas overlay look).
        std::vector<const SurfaceTrackColumn*> markerColumns;
        for (const auto& col : columns) {
            if (col.kind == SurfaceColumnKind::MarkerOverlay) {
                markerColumns.push_back(&col);
                continue;
            }
            std::shared_ptr<geoviz::qgis_welltrack::TrackSpec> spec = buildSpec(col);
            if (spec && model_->adoptTrack(spec)) {
                trackIds_[col.trackId.value] = spec->id;
            }
        }
        for (const auto* col : markerColumns) {
            attachMarkers(*col);
        }
        canvas_->setModel(model_);
    }

    void updateTrack(const SurfaceTrackColumn& column) override {
        const auto it = trackIds_.find(column.trackId.value);
        if (it == trackIds_.end()) {
            // Upsert contract: unknown ids are appended.
            auto spec = buildSpec(column);
            if (spec && model_->adoptTrack(spec)) {
                trackIds_[column.trackId.value] = spec->id;
                canvas_->refresh();
            }
            return;
        }
        auto spec = model_->track(it->second);
        if (!spec) return;
        fillSpec(*spec, column);
        model_->touch();
        canvas_->refresh();
    }

    void removeTrack(const TrackId& trackId) override {
        const auto it = trackIds_.find(trackId.value);
        if (it == trackIds_.end()) return;
        model_->removeTrack(it->second);
        trackIds_.erase(it);
        canvas_->refresh();
    }

    void setDepthRange(double top, double bottom) override {
        canvas_->setDepthDomain(geoviz::qgis_welltrack::makeDomain(top, bottom));
    }

    void setFullDepthRange(double top, double bottom) override {
        // A derives the full extent from the model's data (canvas.cpp
        // setModel -> depthExtent); nothing to push. Kept for seam parity.
        (void)top;
        (void)bottom;
    }

    void setSecondaryAxis(IDepthTransformService* transform) override {
        // A v1 has no secondary-axis primitive; accepted, ignored (docs 14).
        (void)transform;
    }

    SurfaceHit trackAt(const QPointF& pos) const override {
        SurfaceHit hit;
        const auto& layout = canvas_->lastLayout();
        const int idx = layout.trackAtX(pos.x());
        if (idx < 0) return hit;
        const auto& g = layout.tracks[static_cast<std::size_t>(idx)];
        const auto it = std::find_if(trackIds_.begin(), trackIds_.end(),
                                     [&](const auto& kv) { return kv.second == g.trackId; });
        if (it == trackIds_.end()) return hit;
        hit.valid = true;
        hit.trackId = TrackId(it->first);
        hit.depth = canvas_->depthAt(pos);
        return hit;
    }

    std::optional<CurveId> hitCurve(const QPointF& pos, double tolerancePx) const override {
        const auto result = canvas_->hitTest(pos, tolerancePx);
        if (!result.hit || result.curveId == 0) return std::nullopt;
        const auto it = seriesIds_.find(result.curveId);
        if (it == seriesIds_.end()) return std::nullopt;
        return CurveId(it->second);
    }

    double depthAt(const QPointF& pos) const override { return canvas_->depthAt(pos); }

    int yPosForDepth(double depth) const override {
        const auto& layout = canvas_->lastLayout();
        const QRectF content = layout.contentArea;
        if (!content.isValid() || !canvas_->depthDomain().isValid()) return -1;
        const double y = canvas_->depthDomain().yForDepth(depth, content);
        if (!std::isfinite(y) || y < content.top() || y > content.bottom()) return -1;
        return static_cast<int>(y);
    }

    double depthPerPixel() const override {
        const auto& layout = canvas_->lastLayout();
        const auto& domain = canvas_->depthDomain();
        if (!layout.contentArea.isValid() || !domain.isValid() || domain.span() <= 0) return 0.0;
        return domain.span() / layout.contentArea.height();
    }

    int contentHeight() const override {
        const auto& layout = canvas_->lastLayout();
        return layout.contentArea.isValid() ? static_cast<int>(layout.contentArea.height()) : 0;
    }

    QRectF trackGeometry(const TrackId& trackId) const override {
        const auto it = trackIds_.find(trackId.value);
        if (it == trackIds_.end()) return QRectF();
        const auto* g = canvas_->lastLayout().geometryForTrackId(it->second);
        return g ? g->columnRect : QRectF();
    }

    bool supportsImageTracks() const override { return false; }  // A v1 gap

protected:
    bool eventFilter(QObject* watched, QEvent* event) override {
        if (watched == canvas_ && event->type() == QEvent::Resize) {
            emit viewportResized(contentHeight());
        }
        return IWellTrackSurface::eventFilter(watched, event);
    }

private:
    std::shared_ptr<geoviz::qgis_welltrack::TrackSpec> buildSpec(const SurfaceTrackColumn& col) {
        auto spec = std::make_shared<geoviz::qgis_welltrack::TrackSpec>();
        spec->id = ++nextTrackId_;
        fillSpec(*spec, col);
        return spec;
    }

    void fillSpec(geoviz::qgis_welltrack::TrackSpec& spec, const SurfaceTrackColumn& col) {
        spec.title = QString::fromStdString(col.title);
        spec.role = col.kind == SurfaceColumnKind::DepthAxis
                        ? geoviz::qgis_welltrack::TrackRole::DepthRuler
                        : geoviz::qgis_welltrack::TrackRole::CurveTrack;
        spec.visible = true;
        spec.fixedWidth =
            col.kind == SurfaceColumnKind::DepthAxis
                ? std::optional<double>{}  // A's default ruler width (72)
                : std::optional<double>(static_cast<double>(col.width));

        spec.curves.clear();
        spec.bands.clear();
        spec.markers.clear();
        spec.texts.clear();

        std::vector<CurveBufferPtr>& keep = retained_[col.trackId.value];
        keep.clear();
        for (const auto& layer : col.curves) {
            geoviz::qgis_welltrack::CurveSpec curve;
            const ASeriesId sid = ++nextSeriesId_;
            curve.id = sid;
            curve.label = QString::fromStdString(layer.label);
            curve.style.lineColor = layer.color;
            curve.style.lineWidthF = layer.lineWidth;
            curve.style.penStyle = toPenStyle(layer.lineStyle);
            if (layer.data && !layer.data->empty()) {
                keep.push_back(layer.data);  // borrowed memory lifetime
                curve.data = geoviz::qgis_welltrack::makeDoubleView(
                    layer.data->depths().data(), layer.data->values().data(),
                    static_cast<qsizetype>(layer.data->size()));
            }
            seriesIds_[sid] = layer.curveId.value;
            if (layer.xRange.manual) {
                spec.axis.minimum = layer.xRange.manual->first;
                spec.axis.maximum = layer.xRange.manual->second;
            }
            spec.axis.scale = layer.xRange.scale == ScaleKind::Log
                                  ? geoviz::qgis_welltrack::ValueScale::Log10
                                  : geoviz::qgis_welltrack::ValueScale::Linear;
            spec.curves.push_back(std::move(curve));
        }

        // Nested facies degrade to the deepest populated level.
        int deepestSub = -1;
        for (const auto& row : col.intervals) deepestSub = std::max(deepestSub, row.subColumn);
        for (const auto& row : col.intervals) {
            if (row.subColumnCount > 1 && row.subColumn != deepestSub) continue;
            geoviz::qgis_welltrack::DepthIntervalBand band;
            band.top = row.top;
            band.bottom = row.bottom;
            band.label = QString::fromStdString(row.label);
            if (!row.patternAssetPath.empty()) {
                band.fill = patternBrush(row.patternAssetPath);
            }
            if (band.fill.style() == Qt::NoBrush) {
                band.fill = QBrush(toColor(row.fillRgba));
            }
            spec.bands.push_back(std::move(band));
        }

        for (const auto& m : col.markers) {
            geoviz::qgis_welltrack::DepthMarkerLine line;
            line.depth = m.depth;
            line.color = m.color;
            line.pen = Qt::DashLine;
            line.widthF = 1.5;
            line.label = QString::fromStdString(m.label);
            spec.markers.push_back(std::move(line));
        }
    }

    void attachMarkers(const SurfaceTrackColumn& markerColumn) {
        if (markerColumn.markers.empty()) return;
        for (auto& track : model_->tracks()) {
            if (track->role != geoviz::qgis_welltrack::TrackRole::CurveTrack) continue;
            for (const auto& m : markerColumn.markers) {
                geoviz::qgis_welltrack::DepthMarkerLine line;
                line.depth = m.depth;
                line.color = m.color;
                line.pen = Qt::DashLine;
                line.widthF = 1.5;
                line.label = QString::fromStdString(m.label);
                track->markers.push_back(std::move(line));
            }
        }
        model_->touch();
    }

    ACanvas* canvas_ = nullptr;
    std::shared_ptr<geoviz::qgis_welltrack::WellTrackModel> model_;
    geoviz::qgis_welltrack::WellTrackDepthZoomTool* zoomTool_ = nullptr;
    ATrackId nextTrackId_ = 1;
    ASeriesId nextSeriesId_ = 1;
    std::unordered_map<std::string, ATrackId> trackIds_;
    std::unordered_map<ASeriesId, std::string> seriesIds_;
    std::map<std::string, std::vector<CurveBufferPtr>> retained_;
};

namespace {
class QgisSurfaceFactory final : public ISurfaceFactory {
public:
    QString name() const override { return QStringLiteral("qgis-welltrack"); }
    IWellTrackSurface* create(QWidget* parent) const override { return new QgisSurface(parent); }
};

// Self-registration: hosts get the QGIS kernel by default merely by linking
// this build of GeoViz::WellTrackNative (no conditional host code).
const bool kFactoryRegistered = [] {
    SurfaceRegistry::instance().registerFactory(std::make_shared<QgisSurfaceFactory>());
    return true;
}();
}  // namespace

// Archive keep-alive: static-library linking drops unreferenced objects,
// which would silently discard the self-registration initializer above.
// SurfaceRegistry::createPreferred() calls this, forcing the object in.
bool qgisSurfaceFactorySelfRegister() { return kFactoryRegistered; }

}  // namespace geoviz::well_track

#include "qgis_surface.moc"
