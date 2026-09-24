// Core-photo / borehole image segments (ImageTrack parity). Borehole 2D
// image segments are modelled but rendering is kernel-capability gated —
// the seam reports image support availability (see render_surface.h).
#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace geoviz::well_track {

struct ImageSegment {
    double depthTop = 0.0;
    double depthBottom = 0.0;
    std::string title;
    std::string imagePath;  // host-resolved path (core photos)
};

struct ImageSetData {
    std::vector<ImageSegment> segments;

    void finalize();  // drop zero-span segments, sort by depthTop
};

}  // namespace geoviz::well_track
