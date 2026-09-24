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

// Transparent overlay that *paints* the column-boundary handles. Input is
// fully transparent: the actual drag handling lives in WellTrackWidget's
// eventFilter on the kernel viewport (an overlay widget sitting above the
// viewport would otherwise swallow wheel/mouse events before the kernel
// tools ever see them — Round 2 finding).
class SplitterOverlay : public QWidget {
    Q_OBJECT
public:
    explicit SplitterOverlay(QWidget* parent = nullptr);

    // Boundary list in this-overlay coordinates.
    void setBoundaries(const std::vector<QPair<TrackId, QRectF>>& boundaries);
    const std::vector<QPair<TrackId, QRectF>>& boundaries() const { return boundaries_; }
    static constexpr int kHitZonePx = 6;

protected:
    void paintEvent(QPaintEvent* event) override;

private:
    std::vector<QPair<TrackId, QRectF>> boundaries_;
};

}  // namespace geoviz::well_track
