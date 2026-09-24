// Default document rules — numeric parity of qpainter_builder.py
// (CURVE_META, _MERGE_GROUPS, _LOG_SCALE_CURVES, _LABEL_TO_DISPLAY, track
// order and widths) plus interval/marker palettes from the track classes.
#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "geoviz/well_track/domain/curve_style.h"
#include "geoviz/well_track/domain/intervals.h"
#include "geoviz/well_track/domain/markers.h"

namespace geoviz::well_track {

enum class TrackKind : std::uint8_t {
    Depth,        // depth-axis label column
    Curve,        // one or more curve bindings
    Interval,     // generic categorical column (system/series/formation/sequence)
    Lithology,    // SVG pattern filled
    Facies,       // nested phase/sub_phase/micro_phase or single deepest column
    SystemsTract, // TST/HST/LST shapes
    Marker,       // zero-width full-canvas overlay
    Image,        // core photo / text description segments
};

// Builder colour/line overrides (CURVE_META).
std::optional<CurveStyle> curveMetaStyle(const std::string& curveName);

// _MERGE_GROUPS: (member names, merged track title). A curve may appear in
// at most one group; ungrouped curves get one track each.
const std::vector<std::pair<std::vector<std::string>, std::string>>& mergeGroups();

// _LOG_SCALE_CURVES (RT/RXO).
bool isLogScaleCurve(const std::string& curveName);

// _LABEL_TO_DISPLAY display-name mapping.
std::string displayLabel(const std::string& label);

// Pastel palette cycled by interval index (IntervalTrack._PASTEL_PALETTE).
std::uint32_t pastelPaletteColor(std::size_t index);

// Systems-tract colour/shape by category name (systems_tract.py tables);
// unknown names fall back to pastel palette / Rect.
IntervalStyle systemsTractStyle(const std::string& category, std::size_t index);

// Style resolution for one interval of a generic column.
IntervalStyle intervalStyleFor(const IntervalItem& item, std::size_t index);

// Default track width per kind (qpainter_builder widths).
int defaultTrackWidth(TrackKind kind);

}  // namespace geoviz::well_track
