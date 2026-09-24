// Depth domain primitives. The rendering domain is MD (metres) — see
// docs/development/native-welltrack-workbench/00-baseline.md ("Depth domain").
// TVDSS values are host-computed and fed through the same MD axis; the
// domain label is display metadata only.
#pragma once

#include <string>
#include <vector>

namespace geoviz::well_track {

// Vertical window [top, bottom] in metres, top < bottom after normalize().
// Parity: renderer/track_base.py set_depth_range (auto-swap + zero-span guard).
struct DepthRange {
    double top = 0.0;
    double bottom = 1.0;

    void normalize();  // swap if inverted; if top == bottom -> bottom = top + 1
    double span() const { return bottom - top; }
    bool contains(double depth) const { return depth >= top && depth <= bottom; }
    bool isValid() const;

    // Parity of the canvas no-op guard (canvas.py:122-132): range changes
    // smaller than eps must not emit signals or invalidate caches.
    bool nearlyEqual(const DepthRange& o, double eps = 1e-9) const;
};

// Smallest 1/2/5 * 10^k step whose on-screen spacing is at least minPx
// pixels. Parity: renderer/track_base.py nice_depth_interval.
double niceDepthInterval(double span, double rectHeight, double minPx = 20.0);

// Tick depths for the depth-axis column, from top to bottom, step taken
// from niceDepthInterval. The first tick is the smallest multiple of the
// step that is >= top.
std::vector<double> depthTicks(double top, double bottom, double rectHeight, double minPx = 20.0);

// "MD" / "TVDSS" display labels carried from the host data loader.
inline constexpr const char* kDefaultDepthDomainLabel = "MD";
inline constexpr const char* kDefaultDepthUnit = "m";

}  // namespace geoviz::well_track
