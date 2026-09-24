// Host entry point (task §14). Creates the product widget from a data
// source, wiring the preferred render kernel from the surface registry.
#pragma once

#include <memory>

#include <QWidget>

#include "geoviz/well_track/data/data_source.h"

namespace geoviz::well_track {

class WellTrackWidget;

class WellTrackViewFactory {
public:
    // Uses SurfaceRegistry::createPreferred. Returns a widget in error state
    // ("no render kernel") when no kernel is registered.
    WellTrackWidget* create(std::shared_ptr<IWellTrackDataSource> source,
                            QWidget* parent = nullptr) const;

    // Test/integration overload with an explicit surface (takes ownership).
    WellTrackWidget* createWithSurface(std::shared_ptr<IWellTrackDataSource> source,
                                       IWellTrackSurface* surface, QWidget* parent = nullptr) const;
};

}  // namespace geoviz::well_track
