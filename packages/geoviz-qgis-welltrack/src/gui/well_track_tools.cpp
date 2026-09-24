/***************************************************************************
 * geoviz-qgis-welltrack — tools implementation (gui)
 *
 * SPDX-License-Identifier: MIT
 ***************************************************************************/
#include "well_track_tools.h"
#include "well_track_canvas.h"

#include <qgsplotmouseevent.h>

#include <cmath>

namespace geoviz::qgis_welltrack
{

// ---------------------------------------------------------------- depth zoom

WellTrackDepthZoomTool::WellTrackDepthZoomTool( WellTrackCanvas *canvas )
  : QgsPlotToolZoom( canvas )
{
}

QRectF WellTrackDepthZoomTool::plotArea() const
{
  auto *canvas = qobject_cast<WellTrackCanvas *>( mCanvas );
  if ( !canvas )
    return QRectF( 0, 0, 1, 1 );
  const TrackLayoutResult &layout = canvas->lastLayout();
  if ( layout.tracks.empty() )
    return QRectF( QPointF( 0, 0 ), QSizeF( canvas->size() ) );
  return layout.contentArea;
}

QPointF WellTrackDepthZoomTool::constrainStartPoint( QPointF scenePoint ) const
{
  // Depth-axis zoom: pin x to the plot area's horizontal center; the
  // bounds constraint then stretches the band to full width.
  const QRectF area = plotArea();
  return QPointF( area.center().x(), scenePoint.y() );
}

QPointF WellTrackDepthZoomTool::constrainMovePoint( QPointF scenePoint ) const
{
  // y free, x irrelevant (bounds get stretched); keep x near center so the
  // dragged rect stays visually centered before constraining.
  const QRectF area = plotArea();
  return QPointF( area.center().x(), scenePoint.y() );
}

QRectF WellTrackDepthZoomTool::constrainBounds( const QRectF &sceneBounds ) const
{
  const QRectF area = plotArea();
  QRectF bounds = sceneBounds.normalized();
  bounds.setLeft( area.left() );
  bounds.setRight( area.right() );
  if ( bounds.height() < 2.0 )
    bounds.setHeight( 2.0 );
  return bounds;
}

void WellTrackDepthZoomTool::zoomOutClickOn( QPointF scenePoint )
{
  auto *canvas = qobject_cast<WellTrackCanvas *>( mCanvas );
  if ( !canvas )
    return;
  // Center the window on the clicked depth and double the span.
  const double clicked = canvas->depthAt( scenePoint );
  const double span = canvas->depthDomain().span();
  if ( !std::isfinite( clicked ) || !( span > 0 ) )
    return;
  canvas->zoomToDepth( clicked - span, clicked + span );
}

void WellTrackDepthZoomTool::zoomInClickOn( QPointF scenePoint )
{
  auto *canvas = qobject_cast<WellTrackCanvas *>( mCanvas );
  if ( !canvas )
    return;
  const double clicked = canvas->depthAt( scenePoint );
  const double span = canvas->depthDomain().span();
  if ( !std::isfinite( clicked ) || !( span > 0 ) )
    return;
  canvas->zoomToDepth( clicked - span / 4.0, clicked + span / 4.0 );
}

// ---------------------------------------------------------------- cursor

WellTrackCursorTool::WellTrackCursorTool( WellTrackCanvas *canvas )
  : QgsPlotTool( canvas, QStringLiteral( "WellTrackCursor" ) )
{
  setCursor( QCursor( Qt::CrossCursor ) );
}

void WellTrackCursorTool::plotMoveEvent( QgsPlotMouseEvent *event )
{
  auto *canvas = qobject_cast<WellTrackCanvas *>( mCanvas );
  if ( canvas )
    canvas->notifyCursor( event->localPos() );
  event->accept();
}

void WellTrackCursorTool::plotReleaseEvent( QgsPlotMouseEvent *event )
{
  auto *canvas = qobject_cast<WellTrackCanvas *>( mCanvas );
  if ( canvas )
    canvas->notifyCursor( event->localPos() );
  event->accept();
}

void WellTrackCursorTool::deactivate()
{
  auto *canvas = qobject_cast<WellTrackCanvas *>( mCanvas );
  if ( canvas )
    canvas->clearCursor();
  QgsPlotTool::deactivate();
}

} // namespace geoviz::qgis_welltrack
