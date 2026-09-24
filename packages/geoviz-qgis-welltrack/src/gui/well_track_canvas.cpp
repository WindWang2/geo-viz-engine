/***************************************************************************
 * geoviz-qgis-welltrack — WellTrackCanvas implementation (gui)
 *
 * SPDX-License-Identifier: MIT
 *
 * Implements the QgsPlotCanvas interaction virtuals for the well-track
 * substrate. Gesture capture stays 100% in QGIS tools; this class only
 * maps gestures to the shared depth domain through the single mutation
 * path applyDepthDomain().
 ***************************************************************************/
#include "well_track_canvas.h"
#include "well_track_scene_item.h"

#include <qgscoordinatereferencesystem.h>
#include <qgspoint.h>
#include <qgsplotmouseevent.h>

#include <QWheelEvent>

#include <algorithm>
#include <cmath>
#include <limits>

namespace geoviz::qgis_welltrack
{

namespace
{
constexpr double kMinDepthSpan = 1e-9;
constexpr double kMaxDepthSpan = 1e12;
constexpr double kWheelZoomFactor = 1.2;
constexpr double kWheelZoomFineFactor = 1.05;
} // namespace

WellTrackCanvas::WellTrackCanvas( QWidget *parent )
  : QgsPlotCanvas( parent )
{
  mSceneItem = new WellTrackSceneItem( this );
  mCrosshairItem = new WellTrackCrosshairItem( this );
  mSceneItem->updateRect();
}

WellTrackCanvas::~WellTrackCanvas() = default;

void WellTrackCanvas::setModel( std::shared_ptr<WellTrackModel> model )
{
  mModel = std::move( model );
  if ( mModel )
  {
    mHasFullExtent = mModel->depthExtent( mFullExtentMin, mFullExtentMax );
    if ( !mDepthDomain.isValid() && mHasFullExtent )
      mDepthDomain = makeDomain( mFullExtentMin, mFullExtentMax );
  }
  else
  {
    mHasFullExtent = false;
  }
  if ( mSceneItem )
    mSceneItem->invalidate();
  refresh();
}

void WellTrackCanvas::setDepthDomain( const DepthDomain &domain )
{
  applyDepthDomain( domain );
}

void WellTrackCanvas::applyDepthDomain( const DepthDomain &candidate )
{
  DepthDomain domain = candidate;
  if ( domain.shallow > domain.deep )
    domain = makeDomain( candidate.shallow, candidate.deep, candidate.orientation );
  if ( !domain.isValid() )
    return;

  // No-op guard (anti-cascade, mirrors geoviz_well_log 1e-9 rule).
  if ( std::abs( domain.shallow - mDepthDomain.shallow ) < kDepthNoOpEpsilon &&
       std::abs( domain.deep - mDepthDomain.deep ) < kDepthNoOpEpsilon &&
       mDepthDomain.isValid() )
    return;

  if ( mHasFullExtent )
    domain = domain.clampedTo( mFullExtentMin, mFullExtentMax );
  if ( !domain.isValid() )
    return;

  mDepthDomain = domain;
  if ( mSceneItem )
    mSceneItem->invalidate();
  emit depthRangeChanged( mDepthDomain.shallow, mDepthDomain.deep );
  emit plotAreaChanged();
  refresh();
}

void WellTrackCanvas::zoomToDepth( double shallow, double deep )
{
  applyDepthDomain( makeDomain( shallow, deep, mDepthDomain.orientation ) );
}

void WellTrackCanvas::fitDepth()
{
  if ( mModel && mHasFullExtent )
    applyDepthDomain( makeDomain( mFullExtentMin, mFullExtentMax, mDepthDomain.orientation ) );
}

double WellTrackCanvas::depthAt( const QPointF &canvasPos ) const
{
  if ( !mSceneItem )
    return std::numeric_limits<double>::quiet_NaN();
  const TrackLayoutResult &layout = mSceneItem->layout();
  if ( layout.tracks.empty() )
    return std::numeric_limits<double>::quiet_NaN();
  return mDepthDomain.depthAtY( canvasPos.y(), layout.contentArea );
}

const TrackLayoutResult &WellTrackCanvas::lastLayout() const
{
  static const TrackLayoutResult empty;
  return mSceneItem ? mSceneItem->layout() : empty;
}

HitResult WellTrackCanvas::hitTest( const QPointF &canvasPos, double tolerancePx ) const
{
  if ( !mModel || !mSceneItem )
    return HitResult();
  return hitTestNearestSample( *mModel, mSceneItem->layout(), mDepthDomain, canvasPos, tolerancePx );
}

// ---------------------------------------------------------------- QgsPlotCanvas surface

void WellTrackCanvas::refresh()
{
  if ( mSceneItem )
    mSceneItem->updateRect();
  QgsPlotCanvas::refresh();
  viewport()->update();
}

void WellTrackCanvas::panContentsBy( double dx, double dy )
{
  Q_UNUSED( dx )  // v1 has no horizontal pan; tracks own their x domain
  if ( !mDepthDomain.isValid() )
    return;
  const double h = height();
  if ( h <= 0 )
    return;

  // "Drag the paper": content follows the mouse. Dragging down (dy > 0)
  // reveals what was above → the window shifts by the depth equivalent of
  // -dy pixels. depthAtFraction handles both orientations.
  const double delta =
    mDepthDomain.depthAtFraction( -dy / h ) - mDepthDomain.depthAtFraction( 0.0 );
  if ( !std::isfinite( delta ) )
    return;
  applyDepthDomain( makeDomain( mDepthDomain.shallow + delta, mDepthDomain.deep + delta,
                                mDepthDomain.orientation ) );
}

void WellTrackCanvas::centerPlotOn( double x, double y )
{
  Q_UNUSED( x )
  if ( !mDepthDomain.isValid() )
    return;
  const double center = depthAt( QPointF( 0, y ) );
  if ( !std::isfinite( center ) )
    return;
  const double half = mDepthDomain.span() / 2.0;
  applyDepthDomain( makeDomain( center - half, center + half, mDepthDomain.orientation ) );
}

void WellTrackCanvas::scalePlot( double factor )
{
  if ( !mDepthDomain.isValid() || !std::isfinite( factor ) || factor <= 0 )
    return;
  const double centerDepth = mDepthDomain.depthAtFraction( 0.5 );
  double newSpan = mDepthDomain.span() / factor;
  newSpan = std::clamp( newSpan, kMinDepthSpan, kMaxDepthSpan );
  applyDepthDomain(
    makeDomain( centerDepth - newSpan / 2.0, centerDepth + newSpan / 2.0, mDepthDomain.orientation ) );
}

void WellTrackCanvas::zoomToRect( const QRectF &rect )
{
  if ( rect.height() < 2.0 || !mDepthDomain.isValid() )
    return;
  const double dTop = depthAt( QPointF( 0.0, rect.top() ) );
  const double dBottom = depthAt( QPointF( 0.0, rect.bottom() ) );
  if ( !std::isfinite( dTop ) || !std::isfinite( dBottom ) )
    return;
  applyDepthDomain( makeDomain( dTop, dBottom, mDepthDomain.orientation ) );
}

void WellTrackCanvas::wheelZoom( QWheelEvent *event )
{
  if ( !mDepthDomain.isValid() )
    return;
  const QPointF pos = event->position();
  const double anchorDepth = depthAt( pos );
  if ( !std::isfinite( anchorDepth ) )
    return;

  const int steps = event->angleDelta().y() / 120;
  if ( steps == 0 )
    return;
  const double factor =
    ( event->modifiers() & Qt::ControlModifier ) ? kWheelZoomFineFactor : kWheelZoomFactor;
  const double f = std::pow( factor, steps );

  double newSpan = mDepthDomain.span() / f;
  newSpan = std::clamp( newSpan, kMinDepthSpan, kMaxDepthSpan );

  // Keep the depth under the cursor fixed: t is the anchor's screen fraction,
  // so this holds for both orientations.
  const double t = mDepthDomain.normalize( anchorDepth );
  const double newMin = anchorDepth - t * newSpan;
  applyDepthDomain(
    makeDomain( newMin, newMin + newSpan, mDepthDomain.orientation ) );
  event->accept();
}

QgsPoint WellTrackCanvas::toMapCoordinates( const QgsPointXY &point ) const
{
  const TrackLayoutResult &layout = lastLayout();
  if ( layout.tracks.empty() || !mDepthDomain.isValid() )
    return QgsPoint( std::numeric_limits<double>::quiet_NaN(),
                     std::numeric_limits<double>::quiet_NaN() );

  const double depth = mDepthDomain.depthAtY( point.y(), layout.contentArea );
  double value = std::numeric_limits<double>::quiet_NaN();
  const int ti = layout.trackAtX( point.x() );
  if ( ti >= 0 )
  {
    const TrackGeometry &g = layout.tracks[ static_cast<size_t>( ti ) ];
    std::shared_ptr<TrackSpec> spec = mModel ? mModel->track( g.trackId ) : nullptr;
    if ( spec && g.role == TrackRole::CurveTrack )
      value = spec->axis.valueForX( point.x(), g.contentRect );
  }
  return QgsPoint( value, depth );
}

QgsPointXY WellTrackCanvas::toCanvasCoordinates( const QgsPoint &point ) const
{
  // x maps through the first curve track's value axis (ambiguous across
  // tracks by design; documented).
  const TrackLayoutResult &layout = lastLayout();
  if ( layout.tracks.empty() || !mDepthDomain.isValid() )
    return QgsPointXY();

  double x = 0.0;
  bool mapped = false;
  for ( const TrackGeometry &g : layout.tracks )
  {
    if ( g.role != TrackRole::CurveTrack )
      continue;
    std::shared_ptr<TrackSpec> spec = mModel ? mModel->track( g.trackId ) : nullptr;
    if ( !spec )
      continue;
    x = spec->axis.xForValue( point.x(), g.contentRect );
    mapped = true;
    break;
  }
  const double y = mDepthDomain.yForDepth( point.y(), layout.contentArea );
  if ( !mapped || !std::isfinite( y ) )
    return QgsPointXY();
  return QgsPointXY( x, y );
}

QgsPointXY WellTrackCanvas::snapToPlot( QPoint point )
{
  const HitResult hit = hitTest( QPointF( point ), 10.0 );
  if ( !hit.hit )
    return QgsPointXY();
  return QgsPointXY( hit.value, hit.depth );
}

QgsCoordinateReferenceSystem WellTrackCanvas::crs() const
{
  return QgsCoordinateReferenceSystem();  // deliberately invalid: numeric depth/value space
}

void WellTrackCanvas::resizeEvent( QResizeEvent *event )
{
  QgsPlotCanvas::resizeEvent( event );
  if ( mSceneItem )
    mSceneItem->updateRect();
}

void WellTrackCanvas::scheduleRefresh()
{
  refresh();
}

// ---------------------------------------------------------------- cursor plumbing

void WellTrackCanvas::notifyCursor( const QPointF &canvasPos )
{
  const double depth = depthAt( canvasPos );
  if ( std::isfinite( depth ) )
  {
    if ( mCrosshairItem )
      mCrosshairItem->setCursorDepth( depth, canvasPos.y() );
    emit cursorDepthChanged( depth );
    emit sampleHovered( hitTest( canvasPos ) );
  }
  else
  {
    clearCursor();
  }
}

void WellTrackCanvas::clearCursor()
{
  if ( mCrosshairItem )
    mCrosshairItem->clear();
  emit cursorDepthChanged( std::numeric_limits<double>::quiet_NaN() );
}

} // namespace geoviz::qgis_welltrack
