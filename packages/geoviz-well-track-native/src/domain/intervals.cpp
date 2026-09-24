#include "geoviz/well_track/domain/intervals.h"

#include <algorithm>
#include <cmath>

namespace geoviz::well_track {

void IntervalColumn::finalize() {
    // Drop non-finite bounds first: a NaN top breaks strict weak ordering in
    // the sort below, a NaN bottom poisons maxLength_ for the whole column.
    sorted_.clear();
    sorted_.reserve(items.size());
    for (const auto& it : items) {
        if (std::isfinite(it.top) && std::isfinite(it.bottom) && it.bottom > it.top) {
            sorted_.push_back(it);
        }
    }
    std::stable_sort(sorted_.begin(), sorted_.end(),
                     [](const IntervalItem& a, const IntervalItem& b) { return a.top < b.top; });
    maxLength_ = 0.0;
    for (const auto& it : sorted_) {
        maxLength_ = std::max(maxLength_, it.bottom - it.top);
    }
}

const IntervalColumn* IntervalSetData::column(const std::string& key) const {
    for (const auto& c : columns) {
        if (c.key == key) return &c;
    }
    return nullptr;
}

void IntervalSetData::finalize() {
    for (auto& c : columns) c.finalize();
}

const IntervalItem* hitInterval(const IntervalColumn& column, double depth) {
    // Candidates must satisfy top <= depth < bottom. All candidates lie at or
    // below the insertion point of *depth* in the top-sorted copy; items whose
    // (depth - top) already exceeds the longest interval cannot overlap.
    const auto& items = column.sorted_;
    if (items.empty() || !(column.maxLength_ >= 0.0)) return nullptr;
    auto it = std::upper_bound(items.begin(), items.end(), depth,
                               [](double d, const IntervalItem& i) { return d < i.top; });
    const IntervalItem* best = nullptr;
    double bestLen = -1.0;
    for (auto rev = it; rev-- != items.begin();) {
        if (depth - rev->top > column.maxLength_) break;
        if (rev->top <= depth && depth < rev->bottom) {
            const double len = rev->bottom - rev->top;
            if (len > bestLen) {
                bestLen = len;
                best = &*rev;
            }
        }
    }
    return best;
}

}  // namespace geoviz::well_track
