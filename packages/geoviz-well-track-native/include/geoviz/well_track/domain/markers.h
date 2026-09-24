// Well tops / formation markers (single-well). Replaces the duck-typed
// markers contract (marker_track.py marker_depth/marker_label) with a
// structural type; adapters normalize host objects into it.
#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace geoviz::well_track {

struct WellTop {
    double depth = 0.0;  // metres MD
    std::string name;
    std::uint32_t rgba = 0;  // 0 -> marker palette color by index (parity)
};

struct MarkerSetData {
    std::vector<WellTop> tops;

    void finalize();  // drop non-finite depths, sort by depth
};

// Cycled overlay palette, parity with marker_track.py _MARKER_COLORS.
std::uint32_t markerPaletteColor(std::size_t index);

}  // namespace geoviz::well_track
