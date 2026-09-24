// Curve styling and per-track x-range policy — exactly the fields the current
// product uses (task §8: no speculative styling DSL).
#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <utility>

#include "geoviz/well_track/domain/curve.h"
#include "geoviz/well_track/domain/ids.h"

namespace geoviz::well_track {

// Colors are 0xAARRGGBB (opaque by default). Domain layer stays Qt-free;
// the view seam converts to QColor.
enum class LineStyle : std::uint8_t {
    Solid,
    Dashed,
    Dotted,
};

enum class ScaleKind : std::uint8_t {
    Linear,
    Log,
};

struct CurveStyle {
    std::uint32_t rgba = 0xFF63B3ED;  // #63b3ed (CurveData default)
    double lineWidth = 1.5;           // hardcoded 1.5px in Python; now a field
    LineStyle lineStyle = LineStyle::Solid;
    bool visible = true;
    std::string label;  // empty -> curve display name
};

// X range policy for a curve track. Empty manual => auto (robust range).
struct XRange {
    std::optional<std::pair<double, double>> manual;
    ScaleKind scale = ScaleKind::Linear;

    bool isManual() const { return manual.has_value(); }
    // Log floor parity: curve_track.py clamps lower bound to max(lo, 1e-10)
    // and never feeds non-positive values to log10.
    static constexpr double kLogFloor = 1e-10;
    double clampForScale(double v) const {
        return scale == ScaleKind::Log && v < kLogFloor ? kLogFloor : v;
    }
};

// One curve placed in one track: id + style. Duplicate mnemonics from the
// source data get distinct CurveIds (adapter-side uniquification), so
// duplicate columns all render (parity: builder #584).
struct CurveBinding {
    CurveId curveId;
    CurveStyle style;
};

// Decide the effective display range for a curve.
// Manual ranges are kept when sane; the sanity rule mirrors the Python
// constructor cleanup (curve_track.py:96-108): reject when lo > hi,
// lo <= -100, hi > 1e5 or lo == hi, then fall back to the robust range.
// Returns {effective range, usedRobustFallback}.
std::pair<std::pair<double, double>, bool> resolveXRange(
    const XRange& range, const CurveBuffer& buffer, const std::string& curveName);

}  // namespace geoviz::well_track
