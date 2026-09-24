// Robust display range — numeric parity of geoviz_well_log/robust_scale.py
// (P2~P98 quantiles with GR / RHOB / NPHI presets and #113 inverted-preset
// fallback). Oracle: tests/test_robust_scale_units.py.
#pragma once

#include <cstdint>
#include <limits>
#include <string>
#include <utility>

namespace geoviz::well_track {

// nullValue: pass a finite sentinel (e.g. -999.25) to mask LAS NULLs;
// NaN disables the mask.
std::pair<double, double> computeRobustDisplayRange(const double* values,
                                                    std::size_t count,
                                                    const std::string& curveName = "",
                                                    double nullValue =
                                                        std::numeric_limits<double>::quiet_NaN());

// numpy-compatible linear-interpolation percentile over a *sorted* copy.
double percentile(const double* sortedValues, std::size_t count, double q);

}  // namespace geoviz::well_track
