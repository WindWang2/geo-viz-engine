#include "geoviz/well_track/view/well_track_factory.h"

#include "geoviz/well_track/view/surface_factory.h"
#include "geoviz/well_track/view/well_track_widget.h"

namespace geoviz::well_track {

WellTrackWidget* WellTrackViewFactory::create(std::shared_ptr<IWellTrackDataSource> source,
                                              QWidget* parent) const {
    IWellTrackSurface* surface = SurfaceRegistry::instance().createPreferred(parent);
    // WellTrackWidget shows its error state when the kernel is missing.
    return new WellTrackWidget(surface, std::move(source), parent);
}

WellTrackWidget* WellTrackViewFactory::createWithSurface(
    std::shared_ptr<IWellTrackDataSource> source, IWellTrackSurface* surface,
    QWidget* parent) const {
    return new WellTrackWidget(surface, std::move(source), parent);
}

}  // namespace geoviz::well_track
