#include "geoviz/well_track/domain/markers.h"

#include <algorithm>
#include <cmath>

namespace geoviz::well_track {

namespace {
// marker_track.py _MARKER_COLORS
constexpr std::uint32_t kMarkerPalette[] = {
    0xFF0EA5E9, 0xFFF59E0B, 0xFF10B981, 0xFFEF4444, 0xFF8B5CF6, 0xFF14B8A6,
};
}  // namespace

std::uint32_t markerPaletteColor(std::size_t index) {
    constexpr std::size_t n = std::size(kMarkerPalette);
    return kMarkerPalette[index % n];
}

void MarkerSetData::finalize() {
    tops.erase(std::remove_if(tops.begin(), tops.end(),
                              [](const WellTop& t) { return !std::isfinite(t.depth); }),
               tops.end());
    std::stable_sort(tops.begin(), tops.end(),
                     [](const WellTop& a, const WellTop& b) { return a.depth < b.depth; });
}

}  // namespace geoviz::well_track
