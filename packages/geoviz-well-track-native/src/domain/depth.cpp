#include "geoviz/well_track/domain/depth.h"

#include <cmath>

namespace geoviz::well_track {

void DepthRange::normalize() {
    if (top > bottom) std::swap(top, bottom);
    if (top == bottom) bottom = top + 1.0;  // zero-span guard (track_base.py:112)
}

bool DepthRange::isValid() const {
    return std::isfinite(top) && std::isfinite(bottom) && bottom > top;
}

bool DepthRange::nearlyEqual(const DepthRange& o, double eps) const {
    return std::abs(top - o.top) <= eps && std::abs(bottom - o.bottom) <= eps;
}

double niceDepthInterval(double span, double rectHeight, double minPx) {
    if (span <= 0.0 || rectHeight <= 0.0) return 1.0;
    const double raw = (span / rectHeight) * minPx;
    const int exp = raw > 0.0 ? static_cast<int>(std::floor(std::log10(raw))) : 0;
    const double base = std::pow(10.0, exp);
    for (double n : {1.0, 2.0, 5.0}) {
        const double candidate = n * base;
        if (candidate >= raw) return candidate;
    }
    return 10.0 * base;
}

std::vector<double> depthTicks(double top, double bottom, double rectHeight, double minPx) {
    std::vector<double> ticks;
    if (!(bottom > top) || rectHeight <= 0.0) return ticks;
    const double step = niceDepthInterval(bottom - top, rectHeight, minPx);
    if (!(step > 0.0)) return ticks;
    // First multiple of step at or above top.
    double d = std::ceil(top / step) * step;
    // Guard float drift at the boundary.
    if (d < top) d += step;
    for (; d <= bottom; d += step) ticks.push_back(d);
    return ticks;
}

}  // namespace geoviz::well_track
