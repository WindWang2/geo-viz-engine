// Recording test double for the frozen render seam (docs 04). It records
// seam calls and answers geometry queries with a simple deterministic
// layout, so controller/widget logic is testable without the QGIS kernel.
// This is a contract test double, NOT a rendering engine.
#pragma once

#include <QWidget>

#include <algorithm>
#include <cmath>
#include <limits>
#include <map>
#include <vector>

#include "geoviz/well_track/view/render_surface.h"

namespace geoviz::well_track::testing {

struct MockSurfaceCall {
    enum Kind {
        SetTracks,
        UpdateTrack,
        RemoveTrack,
        SetDepthRange,
        SetFullDepthRange,
        SetSecondaryAxis,
    } kind;
    QString trackId;
    double a = 0.0, b = 0.0;
    int count = 0;
};

class MockSurface : public IWellTrackSurface {
    Q_OBJECT
public:
    explicit MockSurface(QWidget* parent = nullptr)
        : IWellTrackSurface(parent), stub_(new QWidget(parent)) {
        stub_->setMinimumSize(600, 400);
        stub_->setObjectName(QStringLiteral("mock-viewport"));
    }

    QWidget* widget() override { return stub_; }

    void setTracks(std::vector<SurfaceTrackColumn> columns) override {
        columns_ = std::move(columns);
        calls_.push_back({MockSurfaceCall::SetTracks, QString(), 0, 0,
                          static_cast<int>(columns_.size())});
        relayout();
    }
    void updateTrack(const SurfaceTrackColumn& column) override {
        // Seam contract: insert-or-replace (upsert).
        bool replaced = false;
        for (auto& c : columns_) {
            if (c.trackId == column.trackId) {
                c = column;
                replaced = true;
                break;
            }
        }
        if (!replaced) columns_.push_back(column);
        calls_.push_back({MockSurfaceCall::UpdateTrack, QString::fromStdString(column.trackId.value)});
    }
    void removeTrack(const TrackId& trackId) override {
        columns_.erase(std::remove_if(columns_.begin(), columns_.end(),
                                      [&](const SurfaceTrackColumn& c) {
                                          return c.trackId == trackId;
                                      }),
                       columns_.end());
        calls_.push_back({MockSurfaceCall::RemoveTrack, QString::fromStdString(trackId.value)});
    }

    void setDepthRange(double top, double bottom) override {
        calls_.push_back({MockSurfaceCall::SetDepthRange, QString(), top, bottom});
        depthTop_ = top;
        depthBottom_ = bottom;
    }
    void setFullDepthRange(double top, double bottom) override {
        calls_.push_back({MockSurfaceCall::SetFullDepthRange, QString(), top, bottom});
        fullTop_ = top;
        fullBottom_ = bottom;
    }
    void setSecondaryAxis(IDepthTransformService* transform) override {
        calls_.push_back({MockSurfaceCall::SetSecondaryAxis, QString()});
        secondaryAxis_ = transform;
    }

    SurfaceHit trackAt(const QPointF& pos) const override {
        SurfaceHit hit;
        int x = 0;
        for (const auto& c : columns_) {
            if (pos.x() >= x && pos.x() < x + c.width) {
                hit.valid = true;
                hit.trackId = c.trackId;
                hit.depth = depthAt(pos);
                return hit;
            }
            x += c.width;
        }
        return hit;
    }
    std::optional<CurveId> hitCurve(const QPointF& pos, double tolerancePx) const override {
        const SurfaceHit hit = trackAt(pos);
        if (!hit.valid) return std::nullopt;
        int x = 0;
        for (const auto& c : columns_) {
            if (c.trackId == hit.trackId) {
                for (const auto& layer : c.curves) {
                    if (layer.data) {
                        const double v = layer.data->valueAt(hit.depth);
                        if (std::isfinite(v) && layer.xRange.manual) {
                            const auto [lo, hi] = *layer.xRange.manual;
                            const double frac = (v - lo) / (hi - lo);
                            const double layerX = x + 10 + frac * (c.width - 20);
                            if (std::abs(pos.x() - layerX) <= tolerancePx) return layer.curveId;
                        }
                    }
                }
            }
            x += c.width;
        }
        return std::nullopt;
    }
    double depthAt(const QPointF& pos) const override {
        const double content = contentHeight();
        if (content <= 0) return std::numeric_limits<double>::quiet_NaN();
        const double y = pos.y() - kHeaderHeight;
        if (y < 0 || y > content) return std::numeric_limits<double>::quiet_NaN();
        return depthTop_ + (y / content) * (depthBottom_ - depthTop_);
    }
    int yPosForDepth(double depth) const override {
        if (!std::isfinite(depth)) return -1;
        const double span = depthBottom_ - depthTop_;
        if (span <= 0) return -1;
        if (depth < depthTop_ || depth > depthBottom_) return -1;  // outside view
        const double y = (depth - depthTop_) / span * contentHeight();
        return static_cast<int>(y) + kHeaderHeight;
    }
    double depthPerPixel() const override {
        const double content = contentHeight();
        return content > 0 ? (depthBottom_ - depthTop_) / content : 0.0;
    }
    int contentHeight() const override {
        return std::max(stub_->height() - kHeaderHeight, 0);
    }
    QRectF trackGeometry(const TrackId& trackId) const override {
        int x = 0;
        for (const auto& c : columns_) {
            if (c.trackId == trackId) {
                return QRectF(x, 0, c.width, stub_->height());
            }
            x += c.width;
        }
        return QRectF();
    }
    bool supportsImageTracks() const override { return supportsImages_; }

    // --- test helpers ---
    void relayout() {}
    const std::vector<MockSurfaceCall>& calls() const { return calls_; }
    void clearCalls() { calls_.clear(); }
    const std::vector<SurfaceTrackColumn>& columns() const { return columns_; }
    void setSupportsImages(bool on) { supportsImages_ = on; }
    void emitViewportResized(int h) { emit viewportResized(h); }
    void emitCursor(double depth) {
        emit cursorMoved(depth, columns_.empty() ? QString() : QString::fromStdString(columns_.front().trackId.value));
    }
    void emitDepthRequest(double top, double bottom) { emit depthRangeRequested(top, bottom); }
    void emitFit() { emit fitRequested(); }

    static constexpr int kHeaderHeight = 56;

private:
    QWidget* stub_ = nullptr;
    std::vector<SurfaceTrackColumn> columns_;
    std::vector<MockSurfaceCall> calls_;
    double depthTop_ = 0.0, depthBottom_ = 100.0;
    double fullTop_ = 0.0, fullBottom_ = 100.0;
    IDepthTransformService* secondaryAxis_ = nullptr;
    bool supportsImages_ = false;
};

}  // namespace geoviz::well_track::testing
