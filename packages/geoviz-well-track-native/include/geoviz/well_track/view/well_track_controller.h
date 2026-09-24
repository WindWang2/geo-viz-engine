// WellTrackController — the product brain. Owns the live track document
// (WellTrackViewConfig) + view state (depth window), drives the render
// surface through the frozen seam. See docs 06/08 for the full contract.
#pragma once

#include <optional>
#include <vector>

#include <QPointer>
#include <QObject>

#include "geoviz/well_track/config/view_config.h"
#include "geoviz/well_track/data/data_source.h"
#include "geoviz/well_track/domain/depth.h"
#include "geoviz/well_track/view/inspection.h"
#include "geoviz/well_track/view/render_surface.h"
#include "geoviz/well_track/view/selection.h"

namespace geoviz::well_track {

enum class SnapMode {
    None,
    Maximum,  // deepest-value maximum inside the window
    Minimum,
};

class WellTrackController : public QObject {
    Q_OBJECT
public:
    // The surface must outlive the controller or be destroyed together with
    // it (both are children of WellTrackWidget in the product assembly).
    WellTrackController(IWellTrackSurface* surface, QObject* parent = nullptr);
    ~WellTrackController() override;

    // --- document / data ---
    void loadSource(std::shared_ptr<IWellTrackDataSource> source);
    // Same-well data refresh; older revisions are rejected (stale worker
    // guard, docs 08 path 7 / L3).
    bool replaceSnapshot(SnapshotPtr snapshot);
    SnapshotPtr snapshot() const { return snapshot_; }
    WellDescriptor wellDescriptor() const;

    // --- depth / navigation ---
    bool setDepthRange(double top, double bottom);  // normalize + no-op guard
    DepthRange depthRange() const { return viewRange_; }
    DepthRange fullRange() const { return fullRange_; }
    void zoomAt(double anchorDepth, double factor);  // ZoomPanHandler semantics
    void panDepth(double delta);
    void fitDepth();
    void setDepthTransform(IDepthTransformService* transform);

    // --- track management ---
    TrackId addCurveTrack(const std::vector<CurveId>& curveIds);
    bool removeTrack(const TrackId& id);
    bool moveTrack(const TrackId& id, std::size_t newIndex);
    bool setTrackVisible(const TrackId& id, bool visible);
    bool setTrackWidth(const TrackId& id, int width);  // clamps [40,300]
    TrackId mergeCurvesIntoTrack(const std::vector<CurveId>& curveIds, const std::string& title);
    bool splitCurveFromTrack(const TrackId& trackId, const CurveId& curveId);
    bool setCurveStyle(const TrackId& trackId, const CurveId& curveId, const CurveStyle& style);
    bool setTrackXRange(const TrackId& trackId, const XRange& range);

    // --- inspection / selection ---
    InspectionResult inspectAt(double depth) const;
    void setSelection(const SelectionState& selection);
    SelectionState selection() const { return selection_; }

    // Extreme snap within ±window metres of *depth* (cross_well picking
    // parity: _get_snapped_depth, 1.5 m default window).
    std::optional<double> snapToExtreme(const CurveId& curveId, double depth, double window,
                                        SnapMode mode) const;

    // --- view config ---
    WellTrackViewConfig viewConfig() const;
    bool applyViewConfig(const WellTrackViewConfig& config);  // validate + swap + resync

    // Shared-depth group wiring (used by WellTrackWidget::syncWith).
    void addSyncPeer(WellTrackController* peer);
    void clearSyncPeers();

    const std::vector<TrackConfigEntry>& tracks() const { return config_.tracks; }

signals:
    void depthRangeChanged(double top, double bottom);
    void viewConfigChanged();
    void selectionChanged(const geoviz::well_track::SelectionState& selection);
    void snapshotReplaced(std::uint64_t revision);
    void inspectionChanged(const geoviz::well_track::InspectionResult& result);

public slots:
    // Wired to the surface's viewport intent signals.
    void handleDepthRangeRequest(double top, double bottom);
    void handleFitRequest();
    void handleCursorMoved(double depth, const QString& trackId);
    void handleViewportResized(int contentHeight);

    // Wired by syncWith: peer propagation (guards prevent echo storms).
    void handlePeerDepthChange(double top, double bottom);

private:
    void resetDocumentFromSnapshot();
    bool applyDepthRange(double top, double bottom);
    void appendIntervalHits(InspectionResult& r, const TrackConfigEntry& entry,
                            double depth) const;
    void fillCurveAssignments(TrackConfigEntry& entry, const std::vector<CurveId>& curveIds);
    void rebuildAllColumns();
    void rebuildColumn(const TrackId& id);
    void updateDepthAxisTicks();
    TrackConfigEntry* findTrack(const TrackId& id);
    const TrackConfigEntry* findTrack(const TrackId& id) const;
    void pruneSyncPeers();

    QPointer<IWellTrackSurface> surface_;
    std::shared_ptr<IWellTrackDataSource> source_;
    SnapshotPtr snapshot_;
    WellTrackViewConfig config_;
    DepthRange viewRange_{0.0, 1.0};
    DepthRange fullRange_{0.0, 1.0};
    std::uint64_t lastRevision_ = 0;
    std::uint64_t userTrackCounter_ = 0;
    SelectionState selection_;
    std::vector<QPointer<WellTrackController>> syncPeers_;
    bool syncing_ = false;
};

}  // namespace geoviz::well_track
