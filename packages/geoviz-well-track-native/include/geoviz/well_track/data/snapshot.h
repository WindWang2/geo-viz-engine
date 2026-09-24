// Immutable well data snapshot — the single data handoff boundary between
// the host and this package (docs 07). Built by the host adapter (possibly
// on a worker thread), consumed on the GUI thread, shared by views without
// copying. Big arrays live here; view/track configuration does not.
#pragma once

#include <map>
#include <memory>
#include <optional>
#include <string>
#include <vector>

#include "geoviz/well_track/domain/curve.h"
#include "geoviz/well_track/domain/depth.h"
#include "geoviz/well_track/domain/ids.h"
#include "geoviz/well_track/domain/images.h"
#include "geoviz/well_track/domain/intervals.h"
#include "geoviz/well_track/domain/markers.h"

namespace geoviz::well_track {

struct WellDescriptor {
    WellId id;
    std::string displayName;
    std::string depthUnitLabel = kDefaultDepthUnit;     // display only, "m"
    double datumElevation = 0.0;                        // passthrough metadata
    std::string domainLabel = kDefaultDepthDomainLabel; // "MD" / "TVDSS" label
};

// Preview-decimation provenance (parity of WellLogData.total_rows/decimated).
struct Provenance {
    std::uint64_t totalRows = 0;
    bool decimated = false;
};

struct WellDataSnapshot {
    WellDescriptor well;
    std::uint64_t revision = 0;  // host-managed, monotonically increasing

    DepthRange fullRange;  // covers every curve/interval/marker

    // Deterministic iteration order (std::map on purpose).
    std::map<CurveId, CurveBufferPtr> curves;
    std::map<IntervalSetId, std::shared_ptr<const IntervalSetData>> intervalSets;
    std::map<MarkerSetId, std::shared_ptr<const MarkerSetData>> markerSets;
    std::map<ImageSetId, std::shared_ptr<const ImageSetData>> imageSets;

    std::optional<Provenance> provenance;

    const CurveBuffer* curve(const CurveId& id) const {
        const auto it = curves.find(id);
        return it == curves.end() ? nullptr : it->second.get();
    }
    const IntervalSetData* intervalSet(const IntervalSetId& id) const {
        const auto it = intervalSets.find(id);
        return it == intervalSets.end() ? nullptr : it->second.get();
    }
    const MarkerSetData* markerSet(const MarkerSetId& id) const {
        const auto it = markerSets.find(id);
        return it == markerSets.end() ? nullptr : it->second.get();
    }
    const ImageSetData* imageSet(const ImageSetId& id) const {
        const auto it = imageSets.find(id);
        return it == imageSets.end() ? nullptr : it->second.get();
    }

    bool empty() const {
        return curves.empty() && intervalSets.empty() && markerSets.empty() && imageSets.empty();
    }
};

using SnapshotPtr = std::shared_ptr<const WellDataSnapshot>;

// Host-side convenience: derive a full range from curve depth extents.
// Adapters may also pass the known top/bottom from the source file.
DepthRange computeFullRange(const WellDataSnapshot& snapshot);

}  // namespace geoviz::well_track
