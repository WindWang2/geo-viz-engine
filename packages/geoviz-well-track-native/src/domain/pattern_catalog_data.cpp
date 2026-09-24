// Generated from packages/geoviz_well_log/geoviz_well_log/pattern_map.py
// (data-asset parity; regenerate rather than hand-edit).
#include <geoviz/well_track/domain/pattern_catalog.h>

#include <algorithm>
#include <string_view>
#include <vector>

namespace geoviz::well_track {
namespace {
constexpr PatternCatalogEntry kPatternMap[36] = {
    {"砂岩", "sandstone"},
    {"泥岩", "mudstone"},
    {"灰岩", "limestone"},
    {"白云岩", "dolomite"},
    {"页岩", "shale"},
    {"粉砂岩", "siltstone"},
    {"砂坪", "sand-flat"},
    {"泥坪", "mud-flat"},
    {"云质坪", "dolomitic-flat"},
    {"混积潮坪", "dolomitic-flat"},
    {"碎屑岩潮坪", "tidal-flat"},
    {"潮坪", "tidal-flat"},
    {"泥质陆棚", "muddy-shelf"},
    {"砂质陆棚", "sandy-shelf"},
    {"砂泥质陆棚", "sand-mud-shelf"},
    {"碎屑岩浅水陆棚", "clastic-shelf"},
    {"混积浅水陆棚", "mixed"},
    {"陆棚", "shelf"},
    {"混积", "mixed"},
    {"三角洲", "delta"},
    {"滨岸", "shoreface"},
    {"前滨", "shoreface"},
    {"临滨", "shoreface"},
    {"生物礁", "reef"},
    {"礁", "reef"},
    {"蒸发岩", "evaporite"},
    {"膏盐", "evaporite"},
    {"冰川", "glacial"},
    {"冰碛", "glacial"},
    {"火山岩", "volcanic"},
    {"熔岩", "volcanic"},
    {"变质岩", "metamorphic"},
    {"冲积扇", "alluvial"},
    {"洪积扇", "alluvial"},
    {"潟湖", "lagoon"},
    {"局限台地", "lagoon"},
};
constexpr PatternCatalogEntry kFaciesColors[85] = {
    {"砂岩", "#f0d9b5"},
    {"泥岩", "#d4c5a9"},
    {"灰岩", "#b5d4c1"},
    {"白云岩", "#a8cdb8"},
    {"页岩", "#c9bfa0"},
    {"粉砂岩", "#e6c9a8"},
    {"砂坪", "#f0d9b5"},
    {"泥坪", "#d4c5a9"},
    {"云质坪", "#c4d4c0"},
    {"混积潮坪", "#c4d4c0"},
    {"碎屑岩潮坪", "#d4c5a9"},
    {"潮坪", "#d4c5a9"},
    {"混合坪", "#e2d2b5"},
    {"潮汐水道", "#ebd2b0"},
    {"潮汐砂脊", "#ebd2b0"},
    {"潮沟", "#ebd2b0"},
    {"潮道", "#ebd2b0"},
    {"泥裂", "#c0dcc0"},
    {"藻席", "#c0dcc0"},
    {"泥质陆棚", "#d4c5a9"},
    {"砂质陆棚", "#f0d9b5"},
    {"砂泥质陆棚", "#dccfb5"},
    {"碎屑岩浅水陆棚", "#d4c5a9"},
    {"混积浅水陆棚", "#c4d4c0"},
    {"陆棚", "#d9d4c8"},
    {"混积", "#c4d4c0"},
    {"陆棚泥", "#d4c5a9"},
    {"陆棚砂", "#f0d9b5"},
    {"风暴沉积", "#dccfb5"},
    {"三角洲", "#e6c9a8"},
    {"河流", "#f0d9b5"},
    {"河道", "#ebd2b0"},
    {"沼泽", "#c0dcc0"},
    {"三角洲前缘", "#ebd2b0"},
    {"三角洲平原", "#ebd2b0"},
    {"前三角洲", "#dccfb5"},
    {"分流河道", "#ebd2b0"},
    {"天然堤", "#e2d2b5"},
    {"辫状河道", "#ebd2b0"},
    {"深水盆地", "#9bb5cf"},
    {"深海", "#9bb5cf"},
    {"半深海", "#a8c0d8"},
    {"深海平原", "#9bb5cf"},
    {"海底扇", "#abc4d4"},
    {"深海泥", "#9bb5cf"},
    {"浊积岩", "#adc6d9"},
    {"等深积岩", "#9bb5cf"},
    {"碎屑流", "#abc4d4"},
    {"湖", "#92d4f0"},
    {"深湖", "#53b3df"},
    {"半深湖", "#73c3ef"},
    {"浅湖", "#aae2f7"},
    {"湖底泥", "#73c3ef"},
    {"碳酸盐台地", "#b5d4c1"},
    {"局限台地", "#b8d4cc"},
    {"开阔台地", "#b5d4c1"},
    {"台地边缘", "#94d6b5"},
    {"生物礁", "#b5d4c1"},
    {"礁", "#b5d4c1"},
    {"粒屑滩", "#bde3cf"},
    {"滨岸", "#f0d9b5"},
    {"前滨", "#f0d9b5"},
    {"临滨", "#f0d9b5"},
    {"后滨", "#f0d9b5"},
    {"沿岸坝", "#f0d9b5"},
    {"海滩砂", "#f0d9b5"},
    {"冲越扇", "#f0d9b5"},
    {"蒸发岩", "#e8dcc8"},
    {"蒸发盐", "#e8dcc8"},
    {"膏盐", "#e8dcc8"},
    {"冰川", "#c8d8e4"},
    {"冰碛", "#c8d8e4"},
    {"火山岩", "#c4a8a0"},
    {"熔岩", "#c4a8a0"},
    {"变质岩", "#bfb8b0"},
    {"冲积扇", "#e6c9a8"},
    {"洪积扇", "#e6c9a8"},
    {"扇中", "#e6c9a8"},
    {"扇根", "#e6c9a8"},
    {"扇缘", "#e6c9a8"},
    {"泥石流", "#e6c9a8"},
    {"片流沉积", "#e6c9a8"},
    {"潟湖", "#b8d4cc"},
    {"半咸水潟湖", "#b8d4cc"},
    {"超咸水潟湖", "#a0c7c0"},
};
}  // namespace

namespace {
const PatternCatalogEntry* findExact(std::string_view name, const PatternCatalogEntry* table, std::size_t n) {
    for (std::size_t i = 0; i < n; ++i)
        if (name == table[i].name) return &table[i];
    return nullptr;
}
const PatternCatalogEntry* findLongestSubstring(std::string_view name, const PatternCatalogEntry* table, std::size_t n) {
    // table must be sorted by descending key length; first hit wins
    for (std::size_t i = 0; i < n; ++i)
        if (name.find(table[i].name) != std::string_view::npos) return &table[i];
    return nullptr;
}
}  // namespace

PatternCatalog::PatternCatalog() {
    faciesByLength_.assign(kFaciesColors, kFaciesColors + std::size(kFaciesColors));
    std::sort(faciesByLength_.begin(), faciesByLength_.end(),
              [](const PatternCatalogEntry& a, const PatternCatalogEntry& b) {
                  return std::string_view(a.name).size() > std::string_view(b.name).size();
              });
    patternMapByLength_.assign(kPatternMap, kPatternMap + std::size(kPatternMap));
    std::sort(patternMapByLength_.begin(), patternMapByLength_.end(),
              [](const PatternCatalogEntry& a, const PatternCatalogEntry& b) {
                  return std::string_view(a.name).size() > std::string_view(b.name).size();
              });
}

std::optional<std::string> PatternCatalog::patternKeyFor(const std::string& name) const {
    if (const auto* e = findExact(name, kPatternMap, std::size(kPatternMap)))
        return std::string(e->value);
    if (const auto* e = findLongestSubstring(name, patternMapByLength_.data(), patternMapByLength_.size()))
        return std::string(e->value);
    return std::nullopt;
}

std::uint32_t PatternCatalog::fallbackColorFor(const std::string& name) const {
    if (const auto* e = findExact(name, kFaciesColors, std::size(kFaciesColors)))
        return parseHexRgba(e->value);
    if (const auto* e = findLongestSubstring(name, faciesByLength_.data(), faciesByLength_.size()))
        return parseHexRgba(e->value);
    return 0xFFE0E0E0;  // terminal fallback (#e0e0e0), parity with LithologyTrack
}

const PatternCatalog& PatternCatalog::builtin() {
    static const PatternCatalog catalog;
    return catalog;
}
}  // namespace geoviz::well_track
