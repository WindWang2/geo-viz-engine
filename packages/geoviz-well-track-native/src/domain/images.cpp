#include "geoviz/well_track/domain/images.h"

#include <algorithm>

namespace geoviz::well_track {

void ImageSetData::finalize() {
    segments.erase(std::remove_if(segments.begin(), segments.end(),
                                  [](const ImageSegment& s) { return !(s.depthBottom > s.depthTop); }),
                   segments.end());
    std::stable_sort(segments.begin(), segments.end(),
                     [](const ImageSegment& a, const ImageSegment& b) { return a.depthTop < b.depthTop; });
}

}  // namespace geoviz::well_track
