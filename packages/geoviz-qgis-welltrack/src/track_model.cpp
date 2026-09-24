/***************************************************************************
 * geoviz-qgis-welltrack — well-track render model implementation
 *
 * SPDX-License-Identifier: MIT
 ***************************************************************************/
#include "track_model.h"

#include <algorithm>
#include <cmath>
#include <limits>

namespace geoviz::qgis_welltrack
{

std::shared_ptr<WellTrackModel> WellTrackModel::create()
{
  return std::shared_ptr<WellTrackModel>( new WellTrackModel() );
}

WellTrackModel::WellTrackModel() = default;

WellTrackModel::~WellTrackModel() = default;

std::shared_ptr<TrackSpec> WellTrackModel::appendTrack( const QString &title, TrackRole role )
{
  auto track = std::make_shared<TrackSpec>();
  track->id = mNextTrackId++;
  track->title = title;
  track->role = role;
  mTracks.push_back( track );
  touch();
  return track;
}

bool WellTrackModel::adoptTrack( std::shared_ptr<TrackSpec> track )
{
  if ( !track )
    return false;
  for ( const auto &existing : mTracks )
  {
    if ( existing->id == track->id )
      return false;
  }
  mTracks.push_back( std::move( track ) );
  touch();
  return true;
}

void WellTrackModel::removeTrack( TrackId id )
{
  auto it = std::remove_if( mTracks.begin(), mTracks.end(),
                            [ id ]( const std::shared_ptr<TrackSpec> &t ) { return t->id == id; } );
  if ( it != mTracks.end() )
  {
    mTracks.erase( it, mTracks.end() );
    touch();
  }
}

std::shared_ptr<TrackSpec> WellTrackModel::track( TrackId id ) const
{
  for ( const auto &t : mTracks )
  {
    if ( t->id == id )
      return t;
  }
  return nullptr;
}

void WellTrackModel::touch()
{
  ++mGeneration;
}

bool WellTrackModel::depthExtent( double &outMin, double &outMax ) const
{
  bool found = false;
  double lo = std::numeric_limits<double>::infinity();
  double hi = -std::numeric_limits<double>::infinity();

  auto consider = [ & ]( double depth )
  {
    if ( !std::isfinite( depth ) )
      return;
    lo = std::min( lo, depth );
    hi = std::max( hi, depth );
    found = true;
  };

  for ( const auto &t : mTracks )
  {
    if ( !t->visible )
      continue;
    for ( const auto &c : t->curves )
    {
      const qsizetype n = c.data.count;
      if ( n <= 0 )
        continue;
      consider( c.data.depthAt( 0 ) );
      consider( c.data.depthAt( n - 1 ) );
    }
    for ( const auto &b : t->bands )
    {
      consider( b.top );
      consider( b.bottom );
    }
  }

  if ( !found || !( hi > lo ) )
    return false;
  outMin = lo;
  outMax = hi;
  return true;
}

} // namespace geoviz::qgis_welltrack
