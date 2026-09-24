// Immutable curve samples. This is the data side of the curve concept —
// styling and x-ranges live in curve_style.h / config entries, never here.
#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "geoviz/well_track/domain/ids.h"

namespace geoviz::well_track {

struct CurveMetadata {
    std::string name;  // display mnemonic, e.g. "GR"
    std::string unit;  // unit label, may be empty (parity: CurveData.unit)
};

// Sorted-by-depth sample storage for one curve. Construction performs the
// one-time cleanup the Python side does inside CurveTrack (curve_track.py
// 121-137): stable sort by depth, drop samples with non-finite depth, keep
// non-finite values as gaps (NaN holes).
class CurveBuffer {
public:
    CurveBuffer() = default;

    // depths.size() must equal values.size().
    CurveBuffer(std::vector<double> depths, std::vector<double> values,
                CurveMetadata meta, std::uint64_t revision = 0);

    std::size_t size() const { return depths_.size(); }
    bool empty() const { return depths_.empty(); }
    const std::vector<double>& depths() const { return depths_; }
    const std::vector<double>& values() const { return values_; }
    const CurveMetadata& meta() const { return meta_; }
    std::uint64_t revision() const { return revision_; }

    // Linear interpolation at *depth* (bisect). Returns NaN when the depth is
    // outside [first, last] (no extrapolation) or when a bracketing sample is
    // a gap. Parity: CrosshairOverlay._collect_values readout semantics.
    double valueAt(double depth) const;

private:
    std::vector<double> depths_;
    std::vector<double> values_;
    CurveMetadata meta_;
    std::uint64_t revision_ = 0;
};

using CurveBufferPtr = std::shared_ptr<const CurveBuffer>;

}  // namespace geoviz::well_track
