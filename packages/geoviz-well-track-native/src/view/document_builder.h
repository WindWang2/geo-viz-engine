// Internal: default document rules + column assembly (numeric parity of
// qpainter_builder.py). Not part of the public API.
#pragma once

#include <optional>
#include <string>
#include <vector>

#include "geoviz/well_track/config/view_config.h"
#include "geoviz/well_track/data/snapshot.h"
#include "geoviz/well_track/view/render_surface.h"

namespace geoviz::well_track::docbuild {

// Standard snapshot set ids produced by host adapters (docs 07).
inline const char* kStratSetId = "stratigraphy";
inline const char* kLithoSetId = "lithology";
inline const char* kFaciesSetId = "facies";
inline const char* kTractSetId = "systems_tract";
inline const char* kSeqSetId = "sequence";
inline const char* kTopsSetId = "tops";
inline const char* kPhotosSetId = "core_photos";

// Build the default view config for a snapshot (build_qpainter_tracks parity:
// Depth -> system/series/formation -> lithology -> facies -> systems tract ->
// sequence -> photos -> curve tracks (merge groups first) -> marker overlay).
WellTrackViewConfig buildDefaultDocument(const WellDataSnapshot& snapshot);

// Assemble the surface column for one track entry against *snapshot*.
// depthRange/contentHeight feed the depth-axis ticks. Returns nullopt when
// the column has nothing to show (empty data / unsupported kind).
std::optional<SurfaceTrackColumn> assembleColumn(const TrackConfigEntry& entry,
                                                 const WellDataSnapshot* snapshot,
                                                 const DepthRange& depthRange, int contentHeight,
                                                 const QString& patternAssetDir,
                                                 bool imagesSupported);

// Effective display range for a curve track layer (manual sanity + robust
// fallback, curve_track.py:96-108 parity).
std::pair<std::pair<double, double>, bool> effectiveRange(const XRange& range,
                                                          const CurveBuffer* buffer,
                                                          const std::string& curveName);

}  // namespace geoviz::well_track::docbuild
