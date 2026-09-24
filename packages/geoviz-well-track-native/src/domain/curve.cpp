#include "geoviz/well_track/domain/curve.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <numeric>
#include <stdexcept>

namespace geoviz::well_track {

CurveBuffer::CurveBuffer(std::vector<double> depths, std::vector<double> values,
                         CurveMetadata meta, std::uint64_t revision)
    : meta_(std::move(meta)), revision_(revision) {
    if (depths.size() != values.size()) {
        throw std::invalid_argument("CurveBuffer: depths/values size mismatch");
    }
    // One-time cleanup parity (curve_track.py:121-137): stable argsort by
    // depth, drop non-finite depths, keep NaN values as gaps.
    std::vector<std::size_t> order(depths.size());
    std::iota(order.begin(), order.end(), std::size_t{0});
    std::stable_sort(order.begin(), order.end(),
                     [&](std::size_t a, std::size_t b) { return depths[a] < depths[b]; });
    depths_.reserve(order.size());
    values_.reserve(order.size());
    for (std::size_t i : order) {
        if (std::isfinite(depths[i])) {
            depths_.push_back(depths[i]);
            values_.push_back(values[i]);
        }
    }
}

double CurveBuffer::valueAt(double depth) const {
    if (depths_.size() < 2) {
        if (depths_.size() == 1 && depth == depths_.front()) return values_.front();
        return std::numeric_limits<double>::quiet_NaN();
    }
    if (depth < depths_.front() || depth > depths_.back()) {
        return std::numeric_limits<double>::quiet_NaN();  // no extrapolation
    }
    const auto it = std::upper_bound(depths_.begin(), depths_.end(), depth);
    const std::size_t hi = static_cast<std::size_t>(it - depths_.begin());
    const std::size_t lo = hi - 1;
    if (depth == depths_[lo]) return values_[lo];
    if (depth == depths_[hi]) return values_[hi];
    const double vLo = values_[lo];
    const double vHi = values_[hi];
    if (!std::isfinite(vLo) || !std::isfinite(vHi)) {
        return std::numeric_limits<double>::quiet_NaN();  // gap
    }
    const double t = (depth - depths_[lo]) / (depths_[hi] - depths_[lo]);
    return vLo + t * (vHi - vLo);
}

}  // namespace geoviz::well_track
