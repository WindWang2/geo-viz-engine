#include "geoviz/well_track/domain/pattern_catalog.h"

#include <cstdlib>

namespace geoviz::well_track {

std::uint32_t parseHexRgba(const std::string& hex) {
    if (hex.size() != 7 || hex[0] != '#') return 0;
    const auto nib = [](char c) -> int {
        if (c >= '0' && c <= '9') return c - '0';
        if (c >= 'a' && c <= 'f') return c - 'a' + 10;
        if (c >= 'A' && c <= 'F') return c - 'A' + 10;
        return -1;
    };
    const int r = nib(hex[1]) * 16 + nib(hex[2]);
    const int g = nib(hex[3]) * 16 + nib(hex[4]);
    const int b = nib(hex[5]) * 16 + nib(hex[6]);
    if (r < 0 || g < 0 || b < 0) return 0;
    return 0xFF000000u | (static_cast<std::uint32_t>(r) << 16) |
           (static_cast<std::uint32_t>(g) << 8) | static_cast<std::uint32_t>(b);
}

}  // namespace geoviz::well_track
