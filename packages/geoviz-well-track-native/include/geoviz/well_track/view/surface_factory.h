// Surface creation. The registry holds factory callbacks only — never host
// data or documents (task §17: no package singleton retaining host state).
// qgis_surface.cpp self-registers its factory when built with Prompt A,
// so hosts need no conditional code.
#pragma once

#include <memory>
#include <vector>

#include "geoviz/well_track/view/render_surface.h"

namespace geoviz::well_track {

class ISurfaceFactory {
public:
    virtual ~ISurfaceFactory() = default;
    virtual QString name() const = 0;
    // The surface parents its viewport widget to *parent* when non-null.
    virtual IWellTrackSurface* create(QWidget* parent = nullptr) const = 0;
};

class SurfaceRegistry {
public:
    static SurfaceRegistry& instance();

    // Later registrations win (createPreferred uses the most recent).
    void registerFactory(std::shared_ptr<ISurfaceFactory> factory);
    IWellTrackSurface* createPreferred(QWidget* parent = nullptr) const;
    std::vector<QString> registeredNames() const;

private:
    SurfaceRegistry() = default;
    std::vector<std::shared_ptr<ISurfaceFactory>> factories_;
};

// Pattern asset directory resolution for the seam's patternAssetPath fields:
// $GEOVIZ_WELL_TRACK_PATTERN_DIR overrides, else the install-relative share
// directory. Returns empty when unresolved (solid fills are then used).
QString defaultPatternAssetDir();

}  // namespace geoviz::well_track
