/***************************************************************************
 * geoviz-qgis-welltrack — composite scene item + crosshair (gui, private)
 *
 * SPDX-License-Identifier: MIT
 *
 * The composite item follows the upstream QgsElevationProfilePlotItem
 * pattern: one scene item covers the whole canvas, renders through the core
 * WellTrackRenderer into a DPR-aware cached QImage and blits it. The
 * crosshair is a separate item (z=100) so hover never invalidates the
 * content cache. Rubber bands from QGIS tools live at z=1000 (upstream).
 ***************************************************************************/
#ifndef GEOVIZ_QWT_WELL_TRACK_SCENE_ITEM_H
#define GEOVIZ_QWT_WELL_TRACK_SCENE_ITEM_H

#include "geoviz/qgis_welltrack/depth_domain.h"
#include "geoviz/qgis_welltrack/track_model.h"
#include "geoviz/qgis_welltrack/welltrack_renderer.h"

#include <qgsplotcanvasitem.h>

#include <QImage>
#include <QPointer>
#include <memory>

namespace geoviz::qgis_welltrack
{

class WellTrackCanvas;

class WellTrackSceneItem : public QgsPlotCanvasItem
{
  public:
    WellTrackSceneItem( WellTrackCanvas *canvas );
    ~WellTrackSceneItem() override;

    QRectF boundingRect() const override;

    //! Marks the cached image dirty; the next paint re-renders.
    void invalidate();
    //! Syncs geometry to the canvas viewport and invalidates.
    void updateRect();

    const TrackLayoutResult &layout() const { return mRenderer.lastLayout(); }
    WellTrackRenderer &renderer() { return mRenderer; }

    void paint( QPainter *painter ) override;

  private:
    double devicePixelRatio( const QPainter *painter ) const;

    WellTrackRenderer mRenderer;
    QImage mCache;
    QRectF mRect;
    bool mCacheDirty = true;
};

class WellTrackCrosshairItem : public QgsPlotCanvasItem
{
  public:
    WellTrackCrosshairItem( WellTrackCanvas *canvas );
    ~WellTrackCrosshairItem() override;

    QRectF boundingRect() const override;

    void setCursorDepth( double depth, double y );
    void clear();
    bool active() const { return mActive; }

    void paint( QPainter *painter ) override;

  private:
    double mY = 0.0;
    QRectF mRect;
    bool mActive = false;
};

} // namespace geoviz::qgis_welltrack

#endif // GEOVIZ_QWT_WELL_TRACK_SCENE_ITEM_H
