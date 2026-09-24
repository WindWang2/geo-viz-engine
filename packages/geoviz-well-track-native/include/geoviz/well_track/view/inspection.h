// Structured inspection results (crosshair readout). Parity of
// CrosshairOverlay._collect_values: interpolated curve values per track plus
// interval and marker hits at the cursor depth.
#pragma once

#include <optional>
#include <string>
#include <vector>

#include "geoviz/well_track/domain/ids.h"

namespace geoviz::well_track {

struct CurveReading {
    TrackId trackId;
    CurveId curveId;
    std::string name;
    std::string unit;
    double value = 0.0;  // NaN inside a gap or outside the curve extent
};

struct IntervalHit {
    TrackId trackId;
    std::string trackTitle;
    std::string columnKey;
    std::string category;
    std::string description;
};

struct MarkerHit {
    TrackId trackId;
    std::string name;
    double depth = 0.0;
};

struct InspectionResult {
    double depth = 0.0;  // NaN when invalid
    std::string depthUnit;
    std::string domainLabel;
    std::vector<CurveReading> curves;
    std::vector<IntervalHit> intervals;
    std::vector<MarkerHit> markers;

    bool isValid() const { return !depthUnit.empty(); }
};

}  // namespace geoviz::well_track
