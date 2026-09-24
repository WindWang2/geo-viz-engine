/***************************************************************************
 * geoviz-qgis-welltrack — scene items implementation (gui)
 *
 * SPDX-License-Identifier: MIT
 ***************************************************************************/
#include "well_track_scene_item.h"
#include "well_track_canvas.h"

#include <QPainter>
#include <QWidget>

namespace geoviz::qgis_welltrack
{

WellTrackSceneItem::WellTrackSceneItem( WellTrackCanvas *canvas )
  : QgsPlotCanvasItem( canvas )
{
  setZValue( 0 );
}

WellTrackSceneItem::~WellTrackSceneItem() = default;

QRectF WellTrackSceneItem::boundingRect() const
{
  return mRect;
}

void WellTrackSceneItem::invalidate()
{
  mCacheDirty = true;
  update();
}

void WellTrackSceneItem::updateRect()
{
  if ( !mCanvas )
    return;
  const QSize size = mCanvas->viewport()->size();
  const QRectF rect( QPointF( 0, 0 ), QSizeF( size ) );
  if ( rect != mRect )
  {
    prepareGeometryChange();
    mRect = rect;
  }
  invalidate();
}

void WellTrackSceneItem::paint( QPainter *painter )
{
  auto *canvas = qobject_cast<WellTrackCanvas *>( mCanvas );
  if ( !canvas || !canvas->model() )
    return;

  const double dpr = devicePixelRatio( painter );
  const QSizeF logicalSize = mRect.size();
  if ( logicalSize.width() <= 0 || logicalSize.height() <= 0 )
    return;

  const QSize cacheSize = QSize( std::max( 1, static_cast<int>( std::lround( logicalSize.width() * dpr ) ) ),
                                 std::max( 1, static_cast<int>( std::lround( logicalSize.height() * dpr ) ) ) );
  if ( mCacheDirty || mCache.size() != cacheSize || mCache.devicePixelRatio() != dpr )
  {
    QImage image( cacheSize, QImage::Format_ARGB32_Premultiplied );
    image.setDevicePixelRatio( dpr );
    {
      QPainter imagePainter( &image );
      mRenderer.render( &imagePainter, QRectF( QPointF( 0, 0 ), logicalSize ), *canvas->model(),
                        canvas->depthDomain() );
    }
    mCache = std::move( image );
    mCacheDirty = false;
  }
  painter->drawImage( QPointF( 0, 0 ), mCache );
}

double WellTrackSceneItem::devicePixelRatio( const QPainter *painter ) const
{
  if ( painter && painter->device() )
    return painter->device()->devicePixelRatioF();
  if ( mCanvas && mCanvas->viewport() )
    return mCanvas->devicePixelRatioF();
  return 1.0;
}

// --------------------------------------------------------------------

WellTrackCrosshairItem::WellTrackCrosshairItem( WellTrackCanvas *canvas )
  : QgsPlotCanvasItem( canvas )
{
  setZValue( 100 );  // upstream convention: overlays 100, rubber bands 1000
  setAcceptHoverEvents( false );
}

WellTrackCrosshairItem::~WellTrackCrosshairItem() = default;

QRectF WellTrackCrosshairItem::boundingRect() const
{
  return mRect;
}

void WellTrackCrosshairItem::setCursorDepth( double depth, double y )
{
  Q_UNUSED( depth )
  if ( !mActive || !qFuzzyCompare( mY, y ) )
  {
    prepareGeometryChange();
    mRect = QRectF( 0, y - 1, ( mCanvas ? static_cast<double>( mCanvas->width() ) : 0.0 ), 3.0 );
    mY = y;
    mActive = true;
    update();
  }
}

void WellTrackCrosshairItem::clear()
{
  if ( mActive )
  {
    prepareGeometryChange();
    mRect = QRectF();
    mActive = false;
    update();
  }
}

void WellTrackCrosshairItem::paint( QPainter *painter )
{
  if ( !mActive )
    return;
  QPen pen( QColor( 220, 30, 30, 200 ), 0.0 );
  pen.setStyle( Qt::DashLine );
  painter->setPen( pen );
  const double w = mCanvas ? static_cast<double>( mCanvas->width() ) : 0.0;
  painter->drawLine( QPointF( 0.0, mY ), QPointF( w, mY ) );
}

} // namespace geoviz::qgis_welltrack
