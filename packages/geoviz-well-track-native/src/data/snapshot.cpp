#include "geoviz/well_track/data/snapshot.h"

#include <limits>

namespace geoviz::well_track {

DepthRange computeFullRange(const WellDataSnapshot& snapshot) {
    double top = std::numeric_limits<double>::infinity();
    double bottom = -std::numeric_limits<double>::infinity();
    for (const auto& [id, buf] : snapshot.curves) {
        if (!buf || buf->empty()) continue;
        top = std::min(top, buf->depths().front());
        bottom = std::max(bottom, buf->depths().back());
    }
    for (const auto& [id, set] : snapshot.intervalSets) {
        if (!set) continue;
        for (const auto& col : set->columns) {
            for (const auto& it : col.items) {
                top = std::min(top, it.top);
                bottom = std::max(bottom, it.bottom);
            }
        }
    }
    for (const auto& [id, set] : snapshot.markerSets) {
        if (!set) continue;
        for (const auto& t : set->tops) {
            top = std::min(top, t.depth);
            bottom = std::max(bottom, t.depth);
        }
    }
    DepthRange r{top, bottom};
    if (!r.isValid()) r = DepthRange{0.0, 1.0};
    r.normalize();
    return r;
}

}  // namespace geoviz::well_track
