#include "geoviz/well_track/domain/defaults.h"

#include <array>
#include <unordered_map>

namespace geoviz::well_track {

namespace {

// qpainter_builder.py CURVE_META
constexpr std::uint32_t kAcColor = 0xFF1D4ED8;   // #1d4ed8
constexpr std::uint32_t kGrColor = 0xFF15803D;   // #15803d
constexpr std::uint32_t kRtColor = 0xFFB91C1C;   // #b91c1c
constexpr std::uint32_t kRxoColor = 0xFFEA580C;  // #ea580c

// IntervalTrack._PASTEL_PALETTE
constexpr std::array<std::uint32_t, 8> kPastel = {
    0xFFD4E6F1, 0xFFD5F5E3, 0xFFFDEBD0, 0xFFE8DAEF,
    0xFFFCF3CF, 0xFFFADBD8, 0xFFD1F2EB, 0xFFEBDEF0,
};

// systems_tract.py _TRACT_COLORS (ASCII + Chinese keys)
const std::vector<std::pair<std::string, std::uint32_t>>& tractColors() {
    static const std::vector<std::pair<std::string, std::uint32_t>> table = {
        {"TST", 0xFF93C5FD}, {"海侵体系域", 0xFF93C5FD},
        {"HST", 0xFFFDE047}, {"高位体系域", 0xFFFDE047},
        {"LST", 0xFF70AD47}, {"低位体系域", 0xFF70AD47},
    };
    return table;
}

IntervalShape tractShape(const std::string& category) {
    if (category == "TST" || category == "海侵体系域") return IntervalShape::UpTriangle;
    if (category == "HST" || category == "高位体系域") return IntervalShape::DownTriangle;
    if (category == "LST" || category == "低位体系域") return IntervalShape::Rect;
    return IntervalShape::Rect;
}

}  // namespace

std::optional<CurveStyle> curveMetaStyle(const std::string& curveName) {
    CurveStyle s;
    if (curveName == "AC") {
        s.rgba = kAcColor;
        s.lineStyle = LineStyle::Dashed;
    } else if (curveName == "GR") {
        s.rgba = kGrColor;
        s.lineStyle = LineStyle::Solid;
    } else if (curveName == "RT") {
        s.rgba = kRtColor;
        s.lineStyle = LineStyle::Solid;
    } else if (curveName == "RXO") {
        s.rgba = kRxoColor;
        s.lineStyle = LineStyle::Dashed;
    } else {
        return std::nullopt;
    }
    return s;
}

const std::vector<std::pair<std::vector<std::string>, std::string>>& mergeGroups() {
    static const std::vector<std::pair<std::vector<std::string>, std::string>> groups = {
        {{"AC", "GR"}, "AC/GR"},
        {{"RT", "RXO"}, "RT/RXO"},
    };
    return groups;
}

bool isLogScaleCurve(const std::string& curveName) {
    return curveName == "RT" || curveName == "RXO";
}

std::string displayLabel(const std::string& label) {
    // qpainter_builder.py _LABEL_TO_DISPLAY — only 深度 transforms; the rest
    // map to themselves.
    if (label == "深度") return "深度 (m)";
    return label;
}

std::uint32_t pastelPaletteColor(std::size_t index) {
    return kPastel[index % kPastel.size()];
}

IntervalStyle systemsTractStyle(const std::string& category, std::size_t index) {
    IntervalStyle st;
    st.shape = tractShape(category);
    for (const auto& [k, v] : tractColors()) {
        if (k == category) {
            st.rgba = v;
            return st;
        }
    }
    st.rgba = pastelPaletteColor(index);
    return st;
}

IntervalStyle intervalStyleFor(const IntervalItem& item, std::size_t index) {
    IntervalStyle st;
    st.rgba = pastelPaletteColor(index);
    return st;
}

int defaultTrackWidth(TrackKind kind) {
    switch (kind) {
        case TrackKind::Depth: return 60;
        case TrackKind::Interval: return 50;
        case TrackKind::Lithology: return 80;
        case TrackKind::Facies: return 80;
        case TrackKind::SystemsTract: return 60;
        case TrackKind::Curve: return 140;
        case TrackKind::Image: return 180;
        case TrackKind::Marker: return 0;  // overlay
    }
    return 60;
}

}  // namespace geoviz::well_track
