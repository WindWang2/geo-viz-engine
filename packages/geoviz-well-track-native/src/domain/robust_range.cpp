#include "geoviz/well_track/domain/robust_range.h"

#include <algorithm>
#include <cmath>
#include <optional>
#include <vector>

namespace geoviz::well_track {

double percentile(const double* sortedValues, std::size_t count, double q) {
    // numpy default linear interpolation between closest ranks.
    if (count == 0) return std::numeric_limits<double>::quiet_NaN();
    if (count == 1) return sortedValues[0];
    const double pos = (q / 100.0) * static_cast<double>(count - 1);
    const std::size_t lo = static_cast<std::size_t>(std::floor(pos));
    const std::size_t hi = std::min(lo + 1, count - 1);
    const double frac = pos - static_cast<double>(lo);
    return sortedValues[lo] + frac * (sortedValues[hi] - sortedValues[lo]);
}

namespace {

// Python math.isclose defaults: rel_tol 1e-9, abs_tol 0.0.
bool isClose(double a, double b) {
    return std::abs(a - b) <= 1e-9 * std::max(std::abs(a), std::abs(b));
}

double roundTo(double v, int decimals) {
    const double scale = std::pow(10.0, decimals);
    return std::round(v * scale) / scale;
}

std::pair<double, double> generalQuantileRange(const std::vector<double>& valid) {
    double p2 = 0.0, p98 = 0.0;
    {
        std::vector<double> sorted(valid);
        std::sort(sorted.begin(), sorted.end());
        p2 = percentile(sorted.data(), sorted.size(), 2.0);
        p98 = percentile(sorted.data(), sorted.size(), 98.0);
    }
    if (isClose(p2, p98) || p2 >= p98) {
        const auto [vmin, vmax] = std::minmax_element(valid.begin(), valid.end());
        if (isClose(*vmin, *vmax)) return {*vmin, *vmin + 10.0};
        p2 = *vmin;
        p98 = *vmax;
    }
    const double span = p98 - p2;
    double vmin = p2 - 0.05 * span;
    double vmax = p98 + 0.05 * span;
    if (span > 10.0) {
        vmin = std::floor(vmin * 10.0) / 10.0;
        vmax = std::ceil(vmax * 10.0) / 10.0;
    } else {
        vmin = roundTo(vmin, 2);
        vmax = roundTo(vmax, 2);
    }
    return {vmin, vmax};
}

bool nameContainsAny(const std::string& upper, std::initializer_list<const char*> keys) {
    for (const char* k : keys) {
        if (upper.find(k) != std::string::npos) return true;
    }
    return false;
}

}  // namespace

std::pair<double, double> computeRobustDisplayRange(const double* values, std::size_t count,
                                                    const std::string& curveName, double nullValue) {
    if (values == nullptr) return {0.0, 100.0};

    std::vector<double> valid;
    valid.reserve(count);
    const bool maskNull = std::isfinite(nullValue);
    for (std::size_t i = 0; i < count; ++i) {
        const double v = values[i];
        if (!std::isfinite(v)) continue;
        // np.isclose defaults: atol=1e-3 *plus* rtol=1e-5 * |null|.
        if (maskNull && std::abs(v - nullValue) <= 1e-3 + 1e-5 * std::abs(nullValue)) continue;
        valid.push_back(v);
    }
    if (valid.empty()) return {0.0, 100.0};

    std::string upper;
    upper.reserve(curveName.size());
    for (char c : curveName) upper.push_back(static_cast<char>(std::toupper(static_cast<unsigned char>(c))));
    // strip
    const std::size_t b = upper.find_first_not_of(" \t\r\n");
    const std::size_t e = upper.find_last_not_of(" \t\r\n");
    if (b != std::string::npos) upper = upper.substr(b, e - b + 1);

    std::vector<double> sorted(valid);
    std::sort(sorted.begin(), sorted.end());
    const double* s = sorted.data();
    const std::size_t n = sorted.size();

    std::optional<std::pair<double, double>> preset;
    if (nameContainsAny(upper, {"GR", "\xe4\xbc\xbd\xe9\xa9\xac"})) {  // GR / 伽马
        const double p1 = percentile(s, n, 1.0);
        const double p99 = percentile(s, n, 99.0);
        // Python writes max(0.0, min(p1, 0.0)) which is identically 0.0.
        preset = std::make_pair(0.0, std::max(150.0, roundTo(p99 + 10.0, 1)));
    } else if (nameContainsAny(upper, {"RHOB", "DEN", "\xe5\xaf\x86\xe5\xba\xa6"})) {  // 密度
        const double p1 = percentile(s, n, 1.0);
        const double p99 = percentile(s, n, 99.0);
        preset = std::make_pair(std::max(1.5, roundTo(p1 - 0.05, 2)),
                                std::min(3.0, roundTo(p99 + 0.05, 2)));
    } else if (nameContainsAny(upper, {"NPHI", "CNL", "\xe4\xb8\xad\xe5\xad\x90"})) {  // 中子
        const double p1 = percentile(s, n, 1.0);
        const double p99 = percentile(s, n, 99.0);
        preset = std::make_pair(std::max(-0.05, roundTo(p1 - 0.02, 2)),
                                std::min(1.0, roundTo(p99 + 0.02, 2)));
    }

    // Inverted preset (other-unit data) falls back to the general path (#113).
    if (preset && preset->first <= preset->second) return *preset;
    return generalQuantileRange(valid);
}

}  // namespace geoviz::well_track
