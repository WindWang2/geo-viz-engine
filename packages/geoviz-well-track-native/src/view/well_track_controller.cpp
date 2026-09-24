#include "geoviz/well_track/view/well_track_controller.h"

#include <algorithm>
#include <cmath>
#include <unordered_set>

#include "document_builder.h"
#include "geoviz/well_track/view/surface_factory.h"

namespace geoviz::well_track {

namespace {
constexpr double kNoOpEps = 1e-9;    // canvas.py:122-132 no-op guard
constexpr double kMinSpan = 1.0;     // interaction.py:85 minimum depth span
constexpr int kMinTrackWidth = 40;   // canvas.py width clamp
constexpr int kMaxTrackWidth = 300;
constexpr double kMarkerTolerancePx = 10.0;  // cross_well _pick_at screen tolerance
}  // namespace

WellTrackController::WellTrackController(IWellTrackSurface* surface, QObject* parent)
    : QObject(parent), surface_(surface) {
    if (surface_) {
        connect(surface_, &IWellTrackSurface::depthRangeRequested, this,
                &WellTrackController::handleDepthRangeRequest);
        connect(surface_, &IWellTrackSurface::fitRequested, this,
                &WellTrackController::handleFitRequest);
        connect(surface_, &IWellTrackSurface::viewportResized, this,
                &WellTrackController::handleViewportResized);
        connect(surface_, &IWellTrackSurface::trackHeaderClicked, this,
                [this](const QString& id) {
                    SelectionState sel;
                    sel.track = TrackId(id.toStdString());
                    setSelection(sel);
                });
        // Single inspection path: cursor movement becomes a structured
        // InspectionResult here; widgets only render it (Round 2).
        connect(surface_, &IWellTrackSurface::cursorMoved, this,
                &WellTrackController::handleCursorMoved);
    }
}

WellTrackController::~WellTrackController() = default;

WellDescriptor WellTrackController::wellDescriptor() const {
    return snapshot_ ? snapshot_->well : WellDescriptor{};
}

void WellTrackController::loadSource(std::shared_ptr<IWellTrackDataSource> source) {
    source_ = std::move(source);
    snapshot_ = source_ ? source_->snapshot() : nullptr;
    lastRevision_ = snapshot_ ? snapshot_->revision : 0;
    resetDocumentFromSnapshot();
}

// Shared tail of loadSource / whole-document replaceSnapshot.
void WellTrackController::resetDocumentFromSnapshot() {
    if (snapshot_) {
        fullRange_ = snapshot_->fullRange.isValid() ? snapshot_->fullRange
                                                    : computeFullRange(*snapshot_);
        config_ = docbuild::buildDefaultDocument(*snapshot_);
    } else {
        fullRange_ = DepthRange{0.0, 1.0};
        config_ = WellTrackViewConfig{};
    }
    if (!selection_.isEmpty()) {
        selection_ = SelectionState{};  // ids from the previous well are void
        emit selectionChanged(selection_);
    }
    viewRange_ = fullRange_;
    rebuildAllColumns();
    if (surface_) {
        surface_->setFullDepthRange(fullRange_.top, fullRange_.bottom);
        surface_->setDepthRange(viewRange_.top, viewRange_.bottom);
    }
    emit viewConfigChanged();
    emit depthRangeChanged(viewRange_.top, viewRange_.bottom);
}

bool WellTrackController::replaceSnapshot(SnapshotPtr snapshot) {
    if (!snapshot) return false;
    if (snapshot->revision < lastRevision_) return false;  // stale worker (L3)

    const bool sameWell =
        snapshot_ && snapshot_->well.id == snapshot->well.id && !config_.tracks.empty();

    if (!sameWell) {
        snapshot_ = std::move(snapshot);
        lastRevision_ = snapshot_->revision;
        resetDocumentFromSnapshot();
        emit snapshotReplaced(lastRevision_);
        return true;
    }

    // --- same well: minimal update (docs 09 granularity) ---
    std::unordered_set<std::string> changedCurves;
    bool structural = snapshot->curves.size() != snapshot_->curves.size();
    for (const auto& [id, buf] : snapshot->curves) {
        const auto it = snapshot_->curves.find(id);
        if (it == snapshot_->curves.end()) {
            structural = true;  // new curve id
            continue;
        }
        if (it->second != buf || (buf && it->second && it->second->revision() != buf->revision())) {
            changedCurves.insert(id.value);
        }
    }
    // Interval/marker/image payloads are small relative to curves; an
    // identity change rebuilds those columns via the structural path.
    if (snapshot->intervalSets.size() != snapshot_->intervalSets.size() ||
        snapshot->markerSets.size() != snapshot_->markerSets.size() ||
        snapshot->imageSets.size() != snapshot_->imageSets.size()) {
        structural = true;
    } else {
        // find() (not at()): same size with a different key set must not
        // throw on the GUI thread.
        for (const auto& [id, set] : snapshot->intervalSets) {
            const auto it = snapshot_->intervalSets.find(id);
            if (it == snapshot_->intervalSets.end() || it->second != set) structural = true;
        }
        for (const auto& [id, set] : snapshot->markerSets) {
            const auto it = snapshot_->markerSets.find(id);
            if (it == snapshot_->markerSets.end() || it->second != set) structural = true;
        }
        for (const auto& [id, set] : snapshot->imageSets) {
            const auto it = snapshot_->imageSets.find(id);
            if (it == snapshot_->imageSets.end() || it->second != set) structural = true;
        }
    }

    snapshot_ = std::move(snapshot);
    lastRevision_ = snapshot_->revision;

    // Drop assignments to vanished curves; drop emptied curve tracks.
    for (auto& entry : config_.tracks) {
        if (entry.kind != TrackKind::Curve) continue;
        const std::size_t before = entry.curves.size();
        entry.curves.erase(std::remove_if(entry.curves.begin(), entry.curves.end(),
                                          [&](const CurveAssignment& a) {
                                              return !snapshot_->curve(a.curveId);
                                          }),
                           entry.curves.end());
        if (entry.curves.size() != before) structural = true;
    }
    const auto removedEnd = std::remove_if(
        config_.tracks.begin(), config_.tracks.end(), [](const TrackConfigEntry& e) {
            return e.kind == TrackKind::Curve && e.curves.empty();
        });
    if (removedEnd != config_.tracks.end()) {
        if (surface_) {
            for (auto it = removedEnd; it != config_.tracks.end(); ++it) {
                surface_->removeTrack(it->id);
            }
        }
        config_.tracks.erase(removedEnd, config_.tracks.end());
        structural = true;
    }

    const DepthRange newFull =
        snapshot_->fullRange.isValid() ? snapshot_->fullRange : computeFullRange(*snapshot_);
    const bool fullChanged = !newFull.nearlyEqual(fullRange_, 1e-9);
    fullRange_ = newFull;

    if (structural) {
        rebuildAllColumns();
    } else {
        for (const auto& entry : config_.tracks) {
            if (entry.kind != TrackKind::Curve) continue;
            for (const auto& a : entry.curves) {
                if (changedCurves.count(a.curveId.value)) {
                    rebuildColumn(entry.id);
                    break;
                }
            }
        }
    }
    if (fullChanged && surface_) {
        surface_->setFullDepthRange(fullRange_.top, fullRange_.bottom);
        setDepthRange(viewRange_.top, viewRange_.bottom);  // re-clamps into new full
    }
    emit snapshotReplaced(lastRevision_);
    return true;
}

bool WellTrackController::setDepthRange(double top, double bottom) {
    if (!applyDepthRange(top, bottom)) return false;
    // Propagate to sync peers: the origin fans out once; each peer applies
    // without re-propagating (QPainterSyncManager echo semantics, N7). We
    // iterate a copy: a depthRangeChanged slot may rewire the peer list
    // (syncWith/unsyncAll) and invalidate the range-for.
    if (!syncing_) {
        pruneSyncPeers();
        const std::vector<QPointer<WellTrackController>> peers = syncPeers_;
        for (auto& peer : peers) {
            if (peer) peer->handlePeerDepthChange(viewRange_.top, viewRange_.bottom);
        }
    }
    return true;
}

// Normalize + no-op guard + clamp into full range + surface write + signal.
bool WellTrackController::applyDepthRange(double top, double bottom) {
    DepthRange r{top, bottom};
    r.normalize();
    if (r.nearlyEqual(viewRange_, kNoOpEps)) return false;  // no-op guard
    if (fullRange_.isValid()) {
        if (r.span() >= fullRange_.span()) {
            r = fullRange_;
        } else {
            if (r.bottom > fullRange_.bottom) {
                const double span = r.span();
                r.bottom = fullRange_.bottom;
                r.top = r.bottom - span;
            }
            if (r.top < fullRange_.top) {
                const double span = r.span();
                r.top = fullRange_.top;
                r.bottom = r.top + span;
            }
        }
    }
    if (!r.isValid()) return false;
    viewRange_ = r;
    if (surface_) surface_->setDepthRange(r.top, r.bottom);
    updateDepthAxisTicks();
    emit depthRangeChanged(r.top, r.bottom);
    return true;
}

void WellTrackController::zoomAt(double anchorDepth, double factor) {
    const double span = viewRange_.span();
    if (span <= 0.0) return;
    const double ratio = std::clamp((anchorDepth - viewRange_.top) / span, 0.0, 1.0);
    const double newSpan = span * (1.0 - factor);
    double newTop = anchorDepth - ratio * newSpan;
    double newBottom = newTop + newSpan;
    newTop = std::max(newTop, fullRange_.top);
    newBottom = std::min(newBottom, fullRange_.bottom);
    if (newBottom - newTop < kMinSpan) newBottom = newTop + kMinSpan;
    setDepthRange(newTop, newBottom);
}

void WellTrackController::panDepth(double delta) {
    double newTop = viewRange_.top + delta;
    double newBottom = viewRange_.bottom + delta;
    if (newTop < fullRange_.top) {
        newBottom += fullRange_.top - newTop;
        newTop = fullRange_.top;
    }
    if (newBottom > fullRange_.bottom) {
        newTop -= newBottom - fullRange_.bottom;
        newBottom = fullRange_.bottom;
    }
    if (newBottom - newTop >= kMinSpan) setDepthRange(newTop, newBottom);
}

void WellTrackController::fitDepth() { setDepthRange(fullRange_.top, fullRange_.bottom); }

void WellTrackController::setDepthTransform(IDepthTransformService* transform) {
    // The transform stays host-owned; it must outlive this controller (see
    // data_source.h lifetime contract) — we never store or free it.
    if (surface_) surface_->setSecondaryAxis(transform);
}

TrackId WellTrackController::addCurveTrack(const std::vector<CurveId>& curveIds) {
    if (!snapshot_) return TrackId{};
    std::vector<CurveId> valid;
    for (const auto& id : curveIds) {
        if (snapshot_->curve(id)) valid.push_back(id);
    }
    if (valid.empty()) return TrackId{};

    TrackConfigEntry e;
    e.id = TrackId("curve:user:" + std::to_string(++userTrackCounter_));
    e.kind = TrackKind::Curve;
    e.width = defaultTrackWidth(TrackKind::Curve);
    e.title = snapshot_->curve(valid.front())->meta().name;
    fillCurveAssignments(e, valid);
    const TrackId id = e.id;
    config_.tracks.push_back(std::move(e));
    rebuildColumn(id);
    emit viewConfigChanged();
    return id;
}

bool WellTrackController::removeTrack(const TrackId& id) {
    const auto it = std::find_if(config_.tracks.begin(), config_.tracks.end(),
                                 [&](const TrackConfigEntry& e) { return e.id == id; });
    if (it == config_.tracks.end()) return false;
    config_.tracks.erase(it);
    if (surface_) surface_->removeTrack(id);
    if (selection_.track == id) {
        selection_.track.reset();
        selection_.curve.reset();
        emit selectionChanged(selection_);
    }
    emit viewConfigChanged();
    return true;
}

bool WellTrackController::moveTrack(const TrackId& id, std::size_t newIndex) {
    if (newIndex >= config_.tracks.size()) return false;
    const auto it = std::find_if(config_.tracks.begin(), config_.tracks.end(),
                                 [&](const TrackConfigEntry& e) { return e.id == id; });
    if (it == config_.tracks.end()) return false;
    if (static_cast<std::size_t>(it - config_.tracks.begin()) == newIndex) return false;
    TrackConfigEntry e = std::move(*it);
    config_.tracks.erase(it);
    config_.tracks.insert(config_.tracks.begin() + static_cast<std::ptrdiff_t>(newIndex),
                          std::move(e));
    rebuildAllColumns();  // order change requires full column sync
    emit viewConfigChanged();
    return true;
}

bool WellTrackController::setTrackVisible(const TrackId& id, bool visible) {
    TrackConfigEntry* e = findTrack(id);
    if (!e) return false;
    if (e->visible == visible) return false;
    e->visible = visible;
    if (visible) {
        rebuildColumn(id);
    } else {
        // Hidden columns leave the layout (data untouched — view state only).
        if (surface_) surface_->removeTrack(id);
    }
    emit viewConfigChanged();
    return true;
}

bool WellTrackController::setTrackWidth(const TrackId& id, int width) {
    TrackConfigEntry* e = findTrack(id);
    if (!e || e->kind == TrackKind::Marker) return false;
    const int clamped = std::clamp(width, kMinTrackWidth, kMaxTrackWidth);
    if (e->width == clamped) return false;
    e->width = clamped;
    rebuildColumn(id);
    emit viewConfigChanged();
    return true;
}

TrackId WellTrackController::mergeCurvesIntoTrack(const std::vector<CurveId>& curveIds,
                                                  const std::string& title) {
    if (!snapshot_ || curveIds.size() < 2) return TrackId{};
    for (const auto& id : curveIds) {
        if (!snapshot_->curve(id)) return TrackId{};
    }

    TrackConfigEntry merged;
    merged.id = TrackId("curve:merge:user:" + std::to_string(++userTrackCounter_));
    merged.kind = TrackKind::Curve;
    merged.title = title.empty() ? "Merged" : title;
    merged.width = defaultTrackWidth(TrackKind::Curve);
    fillCurveAssignments(merged, curveIds);
    for (const auto& a : merged.curves) {
        const CurveBuffer* buf = snapshot_->curve(a.curveId);
        if (buf && isLogScaleCurve(buf->meta().name)) merged.xRange.scale = ScaleKind::Log;
    }
    const TrackId mergedId = merged.id;

    bool placed = false;
    for (auto it = config_.tracks.begin(); it != config_.tracks.end();) {
        if (it->kind != TrackKind::Curve) {
            ++it;
            continue;
        }
        const bool containsMember =
            std::any_of(it->curves.begin(), it->curves.end(), [&](const CurveAssignment& a) {
                return std::find(curveIds.begin(), curveIds.end(), a.curveId) != curveIds.end();
            });
        if (!containsMember) {
            ++it;
            continue;
        }
        if (!placed) {
            // Replace the first member's track in place for visual continuity
            // (and keep its hidden/visible state — merging must not resurrect
            // a hidden track).
            if (surface_) surface_->removeTrack(it->id);
            merged.visible = it->visible;
            *it = merged;  // copy; merged reused for member extraction below
            placed = true;
            ++it;
            continue;
        }
        it->curves.erase(std::remove_if(it->curves.begin(), it->curves.end(),
                                        [&](const CurveAssignment& a) {
                                            return std::find(curveIds.begin(), curveIds.end(),
                                                             a.curveId) != curveIds.end();
                                        }),
                         it->curves.end());
        if (it->curves.empty()) {
            if (surface_) surface_->removeTrack(it->id);
            it = config_.tracks.erase(it);
        } else {
            ++it;
        }
    }
    if (!placed) config_.tracks.push_back(std::move(merged));
    rebuildAllColumns();
    emit viewConfigChanged();
    return mergedId;
}

bool WellTrackController::splitCurveFromTrack(const TrackId& trackId, const CurveId& curveId) {
    TrackConfigEntry* e = findTrack(trackId);
    if (!e || e->kind != TrackKind::Curve || e->curves.size() < 2) return false;
    const auto it = std::find_if(e->curves.begin(), e->curves.end(),
                                 [&](const CurveAssignment& a) { return a.curveId == curveId; });
    if (it == e->curves.end()) return false;
    CurveAssignment a = std::move(*it);
    e->curves.erase(it);

    // The split-off track is always visible — an explicit user action
    // (diverging from merge, which preserves the source track's state).
    TrackConfigEntry single;
    single.id = TrackId("curve:split:" + curveId.value + ":" +
                        std::to_string(++userTrackCounter_));
    single.kind = TrackKind::Curve;
    single.width = defaultTrackWidth(TrackKind::Curve);
    const CurveBuffer* buf = snapshot_ ? snapshot_->curve(curveId) : nullptr;
    single.title = buf ? buf->meta().name : a.curveId.value;
    single.xRange = e->xRange;
    single.curves.push_back(std::move(a));

    const auto pos = std::find_if(config_.tracks.begin(), config_.tracks.end(),
                                  [&](const TrackConfigEntry& t) { return t.id == trackId; });
    config_.tracks.insert(pos + 1, std::move(single));
    rebuildAllColumns();
    emit viewConfigChanged();
    return true;
}

bool WellTrackController::setCurveStyle(const TrackId& trackId, const CurveId& curveId,
                                        const CurveStyle& style) {
    TrackConfigEntry* e = findTrack(trackId);
    if (!e) return false;
    for (auto& a : e->curves) {
        if (a.curveId == curveId) {
            a.style = style;
            rebuildColumn(trackId);  // style-only granularity
            emit viewConfigChanged();
            return true;
        }
    }
    return false;
}

bool WellTrackController::setTrackXRange(const TrackId& trackId, const XRange& range) {
    TrackConfigEntry* e = findTrack(trackId);
    if (!e || e->kind != TrackKind::Curve) return false;
    e->xRange = range;
    rebuildColumn(trackId);
    emit viewConfigChanged();
    return true;
}

InspectionResult WellTrackController::inspectAt(double depth) const {
    InspectionResult r;
    if (!snapshot_ || !std::isfinite(depth)) return r;
    r.depth = depth;
    r.depthUnit = snapshot_->well.depthUnitLabel;
    r.domainLabel = config_.domainLabel.empty() ? snapshot_->well.domainLabel : config_.domainLabel;
    const double dpp = surface_ ? surface_->depthPerPixel() : 0.0;
    const double markerTol = kMarkerTolerancePx * dpp;
    for (const auto& entry : config_.tracks) {
        if (!entry.visible) continue;
        switch (entry.kind) {
            case TrackKind::Curve:
                for (const auto& a : entry.curves) {
                    const CurveBuffer* buf = snapshot_->curve(a.curveId);
                    if (!buf || !a.style.visible) continue;
                    CurveReading rd;
                    rd.trackId = entry.id;
                    rd.curveId = a.curveId;
                    rd.name = a.style.label.empty() ? buf->meta().name : a.style.label;
                    rd.unit = buf->meta().unit;
                    rd.value = buf->valueAt(depth);
                    r.curves.push_back(std::move(rd));
                }
                break;
            case TrackKind::Interval:
            case TrackKind::Lithology:
            case TrackKind::SystemsTract:
            case TrackKind::Facies:
                appendIntervalHits(r, entry, depth);
                break;
            case TrackKind::Marker: {
                if (const MarkerSetData* set = snapshot_->markerSet(entry.markerSet)) {
                    for (const auto& top : set->tops) {
                        const bool hit = dpp > 0.0 ? std::abs(top.depth - depth) <= markerTol
                                                   : top.depth == depth;
                        if (hit) {
                            MarkerHit h;
                            h.trackId = entry.id;
                            h.name = top.name;
                            h.depth = top.depth;
                            r.markers.push_back(std::move(h));
                        }
                    }
                }
                break;
            }
            default:
                break;
        }
    }
    return r;
}

void WellTrackController::appendIntervalHits(InspectionResult& r, const TrackConfigEntry& entry,
                                             double depth) const {
    const IntervalSetData* set = snapshot_->intervalSet(entry.intervals.setId);
    if (!set) return;
    auto pushHit = [&](const IntervalColumn& col) {
        if (const IntervalItem* hit = hitInterval(col, depth)) {
            IntervalHit h;
            h.trackId = entry.id;
            h.trackTitle = entry.title;
            h.columnKey = col.key;
            h.category = hit->category;
            h.description = hit->description;
            r.intervals.push_back(std::move(h));
        }
    };
    if (entry.kind == TrackKind::Facies && entry.intervals.nested) {
        static const char* kNested[3] = {"phase", "sub_phase", "micro_phase"};
        for (const char* key : kNested) {
            if (const IntervalColumn* c = set->column(key)) pushHit(*c);
        }
    } else if (const IntervalColumn* c = set->column(entry.intervals.columnKey)) {
        pushHit(*c);
    }
}

void WellTrackController::setSelection(const SelectionState& selection) {
    if (selection_ == selection) return;
    selection_ = selection;
    emit selectionChanged(selection_);
}

std::optional<double> WellTrackController::snapToExtreme(const CurveId& curveId, double depth,
                                                         double window, SnapMode mode) const {
    if (mode == SnapMode::None || !snapshot_) return std::nullopt;
    const CurveBuffer* buf = snapshot_->curve(curveId);
    if (!buf || buf->empty()) return std::nullopt;
    const auto& d = buf->depths();
    const auto& v = buf->values();
    const auto begin = std::lower_bound(d.begin(), d.end(), depth - window);
    const auto end = std::upper_bound(d.begin(), d.end(), depth + window);
    std::optional<double> bestValue;
    std::optional<double> bestDepth;
    for (auto it = begin; it != end; ++it) {
        const std::size_t i = static_cast<std::size_t>(it - d.begin());
        if (!std::isfinite(v[i])) continue;
        const bool better =
            !bestValue || (mode == SnapMode::Maximum ? v[i] > *bestValue : v[i] < *bestValue);
        if (better) {
            bestValue = v[i];
            bestDepth = d[i];
        }
    }
    return bestDepth;
}

WellTrackViewConfig WellTrackController::viewConfig() const { return config_; }

bool WellTrackController::applyViewConfig(const WellTrackViewConfig& config) {
    std::string err;
    if (!config.validate(&err)) return false;
    config_ = config;
    rebuildAllColumns();
    emit viewConfigChanged();
    return true;
}

void WellTrackController::handleDepthRangeRequest(double top, double bottom) {
    // The kernel already anchored the zoom at the cursor; apply product rules.
    DepthRange r{top, bottom};
    r.normalize();
    if (r.span() < kMinSpan) r.bottom = r.top + kMinSpan;
    setDepthRange(r.top, r.bottom);
}

void WellTrackController::handleFitRequest() { fitDepth(); }

void WellTrackController::handleCursorMoved(double depth, const QString& trackId) {
    (void)trackId;
    InspectionResult r = inspectAt(depth);
    if (!r.isValid()) return;
    emit inspectionChanged(r);
}

void WellTrackController::handleViewportResized(int contentHeight) {
    (void)contentHeight;
    updateDepthAxisTicks();
}

void WellTrackController::handlePeerDepthChange(double top, double bottom) {
    // Peers apply without re-propagating (origin fanned out already).
    syncing_ = true;
    applyDepthRange(top, bottom);
    syncing_ = false;
}

void WellTrackController::fillCurveAssignments(TrackConfigEntry& entry,
                                               const std::vector<CurveId>& curveIds) {
    for (const auto& cid : curveIds) {
        const CurveBuffer* buf = snapshot_->curve(cid);
        if (!buf) continue;
        CurveAssignment a;
        a.curveId = cid;
        a.style = curveMetaStyle(buf->meta().name).value_or(CurveStyle{});
        a.style.label = buf->meta().name;
        entry.curves.push_back(std::move(a));
    }
}

void WellTrackController::rebuildAllColumns() {
    if (!surface_) return;
    std::vector<SurfaceTrackColumn> columns;
    const bool imagesSupported = surface_->supportsImageTracks();
    const int contentHeight = surface_->contentHeight();
    const QString patternDir = defaultPatternAssetDir();
    for (const auto& entry : config_.tracks) {
        if (!entry.visible) continue;  // hidden tracks (incl. marker overlay)
        if (auto col = docbuild::assembleColumn(entry, snapshot_.get(), viewRange_, contentHeight,
                                                patternDir, imagesSupported)) {
            columns.push_back(std::move(*col));
        }
    }
    surface_->setTracks(std::move(columns));
}

void WellTrackController::rebuildColumn(const TrackId& id) {
    if (!surface_) return;
    const TrackConfigEntry* e = findTrack(id);
    if (!e) return;
    if (!e->visible) return;  // hidden tracks stay off the surface (Round 2:
                              // same-well refresh used to resurrect them)
    if (auto col = docbuild::assembleColumn(*e, snapshot_.get(), viewRange_,
                                            surface_->contentHeight(), defaultPatternAssetDir(),
                                            surface_->supportsImageTracks())) {
        surface_->updateTrack(*col);
    }
}

void WellTrackController::updateDepthAxisTicks() {
    for (const auto& e : config_.tracks) {
        if (e.kind == TrackKind::Depth && e.visible) {
            rebuildColumn(e.id);
            break;
        }
    }
}

TrackConfigEntry* WellTrackController::findTrack(const TrackId& id) {
    for (auto& e : config_.tracks) {
        if (e.id == id) return &e;
    }
    return nullptr;
}

const TrackConfigEntry* WellTrackController::findTrack(const TrackId& id) const {
    for (const auto& e : config_.tracks) {
        if (e.id == id) return &e;
    }
    return nullptr;
}

void WellTrackController::pruneSyncPeers() {
    syncPeers_.erase(std::remove_if(syncPeers_.begin(), syncPeers_.end(),
                                    [](const QPointer<WellTrackController>& p) {
                                        return p.isNull();
                                    }),
                     syncPeers_.end());
}

void WellTrackController::addSyncPeer(WellTrackController* peer) {
    if (!peer || peer == this) return;
    pruneSyncPeers();
    if (std::find(syncPeers_.begin(), syncPeers_.end(), peer) == syncPeers_.end()) {
        syncPeers_.push_back(peer);
    }
}

void WellTrackController::clearSyncPeers() { syncPeers_.clear(); }

}  // namespace geoviz::well_track
