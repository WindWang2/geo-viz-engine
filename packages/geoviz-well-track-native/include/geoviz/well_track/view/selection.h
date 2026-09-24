// Selection state for the well-track view (task §11: curve / track /
// interval selection, optional depth range).
#pragma once

#include <optional>
#include <utility>

#include "geoviz/well_track/domain/ids.h"

namespace geoviz::well_track {

struct SelectionState {
    std::optional<TrackId> track;
    std::optional<CurveId> curve;  // implies the owning track
    std::optional<std::pair<double, double>> depthRange;

    bool isEmpty() const { return !track && !curve && !depthRange; }

    bool operator==(const SelectionState& o) const {
        return track == o.track && curve == o.curve && depthRange == o.depthRange;
    }
    bool operator!=(const SelectionState& o) const { return !(*this == o); }
};

}  // namespace geoviz::well_track
