/***************************************************************************
 * geoviz-qgis-welltrack — depth synchronizer implementation (gui)
 *
 * SPDX-License-Identifier: MIT
 ***************************************************************************/
#include "depth_synchronizer.h"
#include "well_track_canvas.h"

#include <algorithm>

namespace geoviz::qgis_welltrack
{

WellTrackSynchronizer::WellTrackSynchronizer( QObject *parent )
  : QObject( parent )
{
}

WellTrackSynchronizer::~WellTrackSynchronizer() = default;

void WellTrackSynchronizer::addCanvas( WellTrackCanvas *canvas )
{
  if ( !canvas )
    return;
  for ( const auto &c : mCanvases )
  {
    if ( c == canvas )
      return;
  }
  mCanvases.push_back( canvas );
  connect( canvas, &WellTrackCanvas::depthRangeChanged, this,
           &WellTrackSynchronizer::onDepthRangeChanged );
  connect( canvas, &QObject::destroyed, this, [ this, canvas ]()
  {
    mCanvases.erase( std::remove_if( mCanvases.begin(), mCanvases.end(),
                                     [ canvas ]( const QPointer<WellTrackCanvas> &c )
                                     { return c == nullptr || c.data() == canvas; } ),
                     mCanvases.end() );
  } );
}

void WellTrackSynchronizer::removeCanvas( WellTrackCanvas *canvas )
{
  disconnect( canvas, &WellTrackCanvas::depthRangeChanged, this,
              &WellTrackSynchronizer::onDepthRangeChanged );
  mCanvases.erase( std::remove_if( mCanvases.begin(), mCanvases.end(),
                                   [ canvas ]( const QPointer<WellTrackCanvas> &c )
                                   { return c == nullptr || c.data() == canvas; } ),
                   mCanvases.end() );
}

void WellTrackSynchronizer::onDepthRangeChanged( double shallow, double deep )
{
  if ( mDispatching )
    return;  // feedback breaker: re-entrant emissions are no-ops
  auto *sender = qobject_cast<WellTrackCanvas *>( QObject::sender() );
  if ( !sender )
    return;

  mDispatching = true;
  const DepthDomain domain = sender->depthDomain();
  for ( const auto &c : mCanvases )
  {
    if ( c && c != sender )
      c->setDepthDomain( domain );  // canvas-side <1e-9 guard absorbs echo
  }
  mDispatching = false;
}

} // namespace geoviz::qgis_welltrack
