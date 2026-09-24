// WellTrackWidget — host-agnostic product component (task §10). Composes
// the kernel viewport, product overlays (crosshair/inspection readout,
// column splitters), status bar and empty/error states. Layout and product
// interactions live here; painting primitives live in the kernel.
#pragma once

#include <memory>

#include <QPointer>
#include <QWidget>

#include "geoviz/well_track/view/inspection.h"
#include "geoviz/well_track/view/well_track_controller.h"

class QLabel;

namespace geoviz::well_track {

class CrosshairOverlay;
class SplitterOverlay;

class WellTrackWidget : public QWidget {
    Q_OBJECT
public:
    // Takes ownership of *surface* (reparented). A null surface yields the
    // "no render kernel" error state — the widget stays constructible so
    // hosts degrade gracefully (docs 04: no fallback engine).
    WellTrackWidget(IWellTrackSurface* surface, std::shared_ptr<IWellTrackDataSource> source,
                    QWidget* parent = nullptr);
    ~WellTrackWidget() override;

    WellTrackController* controller() const { return controller_.get(); }

    // Shared-depth group (parity of QPainterSyncManager, echo-guarded).
    void syncWith(WellTrackWidget* other);
    void unsyncAll();

    InspectionResult inspectAtCursor() const;

signals:
    void inspectionChanged(const geoviz::well_track::InspectionResult& result);

protected:
    void resizeEvent(QResizeEvent* event) override;
    bool eventFilter(QObject* watched, QEvent* event) override;

private:
    bool handleSplitterPress(const QPointF& pos);
    void handleSplitterDrag(const QPointF& pos);
    void handleSplitterRelease();
    void updateOverlaysGeometry();
    void setStatusFromInspection(const InspectionResult& result);
    void refreshEmptyState();

    QPointer<IWellTrackSurface> surface_;  // child-owned (QObject child of this)
    std::unique_ptr<WellTrackController> controller_;
    CrosshairOverlay* crosshair_ = nullptr;  // child widget
    SplitterOverlay* splitter_ = nullptr;    // child widget (paint-only)
    QLabel* statusLabel_ = nullptr;
    QLabel* emptyLabel_ = nullptr;
    InspectionResult lastInspection_;
    TrackId splitterDragTrack_;  // active boundary owner while dragging
    int splitterLastX_ = 0;
    bool splitterDragging_ = false;
};

}  // namespace geoviz::well_track
