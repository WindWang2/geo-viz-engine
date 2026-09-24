// Internal product overlays for WellTrackWidget. These draw *product* UI
// only (crosshair readout line + column splitters); they hold no viewport
// math of their own — geometry comes from the kernel surface queries.
#pragma once

#include <QWidget>

#include "geoviz/well_track/view/inspection.h"
#include "geoviz/well_track/view/render_surface.h"

class QPainter;

namespace geoviz::well_track {

// Transparent overlay drawing the crosshair line + inspection panel
// (parity of CrosshairOverlay: dashed line + rounded info panel).
class CrosshairOverlay : public QWidget {
    Q_OBJECT
public:
    explicit CrosshairOverlay(QWidget* parent = nullptr);

    void setInspection(const InspectionResult& result, int y);
    void clearInspection();

protected:
    void paintEvent(QPaintEvent* event) override;

private:
    bool visible_ = false;
    int y_ = 0;
    InspectionResult result_;
};

// Transparent overlay with 6px hit zones at column boundaries (parity of
// the canvas splitter: drag boundary, widths trade off, clamp [40,300]).
class SplitterOverlay : public QWidget {
    Q_OBJECT
public:
    explicit SplitterOverlay(QWidget* parent = nullptr);

    // Boundary list in this-overlay coordinates.
    void setBoundaries(const std::vector<QPair<TrackId, QRectF>>& boundaries);

signals:
    void widthDeltaRequested(const geoviz::well_track::TrackId& trackId, int deltaPx);

protected:
    void paintEvent(QPaintEvent* event) override;
    void mousePressEvent(QMouseEvent* event) override;
    void mouseMoveEvent(QMouseEvent* event) override;
    void mouseReleaseEvent(QMouseEvent* event) override;

private:
    static constexpr int kHitZonePx = 6;

    std::vector<QPair<TrackId, QRectF>> boundaries_;
    int activeIndex_ = -1;
    int lastX_ = 0;
};

}  // namespace geoviz::well_track
