// Lithology/facies name resolution: category name -> SVG pattern asset key
// and fallback colour. Data parity of pattern_map.py + the fuzzy lookup of
// PatternEngine._fuzzy_lookup / LithologyTrack._fallback_color (exact match
// first, then longest-substring). The SVG files ship with this package
// (assets/patterns, copied from geoviz_well_log); materializing them into
// brushes is the render kernel's job, not ours.
#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace geoviz::well_track {

struct PatternCatalogEntry {
    const char* name;
    const char* value;  // pattern key or "#rrggbb"
};

// "#rrggbb" -> 0xFFrrggbb (opaque). Returns 0 on parse failure.
std::uint32_t parseHexRgba(const std::string& hex);

class PatternCatalog {
public:
    PatternCatalog();

    // Parity of PatternEngine lookup: exact, then longest-substring over
    // PATTERN_MAP keys. Empty when the name matches no pattern.
    std::optional<std::string> patternKeyFor(const std::string& name) const;

    // Parity of LithologyTrack._fallback_color: exact, then longest-substring
    // over FACIES_COLORS, terminal fallback #e0e0e0.
    std::uint32_t fallbackColorFor(const std::string& name) const;

    static const PatternCatalog& builtin();

private:
    std::vector<PatternCatalogEntry> faciesByLength_;
    std::vector<PatternCatalogEntry> patternMapByLength_;
};

}  // namespace geoviz::well_track
