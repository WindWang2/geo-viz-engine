// Minimal data-source interfaces (task §12: real boundaries only).
// Implementations live on the host side; this package never depends on
// workbench-internal types.
#pragma once

#include <memory>

#include "geoviz/well_track/data/snapshot.h"

namespace geoviz::well_track {

class IWellTrackDataSource {
public:
    virtual ~IWellTrackDataSource() = default;

    virtual WellDescriptor descriptor() const = 0;

    // Returns the current immutable snapshot. Called on the GUI thread; the
    // host is responsible for building snapshots on worker threads and
    // marshalling them over (docs 06 "threading contract").
    virtual SnapshotPtr snapshot() const = 0;
};

// Depth<->time transform for the secondary TWT axis. Product implementations
// live on the host side (parity: CheckshotTable / WellTieCalibration); this
// package consumes the interface only and never re-implements interpolation.
//
// Lifetime contract: instances are host-owned raw pointers. The host must
// clear them via setDepthTransform(nullptr) (or destroy the view) before the
// service object goes away.
class IDepthTransformService {
public:
    virtual ~IDepthTransformService() = default;

    virtual double depthToTwt(double depthM) const = 0;  // NaN when unmapped
    virtual double twtToDepth(double twtMs) const = 0;   // NaN when unmapped
};

}  // namespace geoviz::well_track
