/***************************************************************************
 * geoviz-qgis-welltrack — track column layout implementation
 *
 * SPDX-License-Identifier: MIT
 ***************************************************************************/
#include "track_layout.h"

#include <algorithm>
#include <cmath>

namespace geoviz::qgis_welltrack
{

int TrackLayoutResult::trackAtX( double x ) const
{
  for ( const auto &g : tracks )
  {
    if ( x >= g.columnRect.left() && x < g.columnRect.right() )
      return g.trackIndex;
  }
  return -1;
}

const TrackGeometry *TrackLayoutResult::geometryForTrackId( TrackId id ) const
{
  for ( const auto &g : tracks )
  {
    if ( g.trackId == id )
      return &g;
  }
  return nullptr;
}

TrackLayoutResult computeTrackLayout( const WellTrackModel &model, const QRectF &targetRect,
                                      const TrackLayoutOptions &options )
{
  TrackLayoutResult result;
  result.separatorWidth = options.separatorWidth;

  const auto &tracks = model.tracks();

  int visibleCount = 0;
  for ( const auto &t : tracks )
  {
    if ( t->visible )
      ++visibleCount;
  }
  if ( visibleCount == 0 || targetRect.width() <= 0 || targetRect.height() <= 0 )
    return result;

  const int separatorCount = visibleCount - 1;
  const double headerHeight = std::max( 0.0, options.headerHeight );

  const double availableWidth =
    targetRect.width() - options.outerMargins.left() - options.outerMargins.right()
    - separatorCount * options.separatorWidth;

  // Fixed widths (depth ruler gets its fixed default unless a track width
  // was set explicitly).
  std::vector<std::shared_ptr<TrackSpec>> visibleTracks;
  visibleTracks.reserve( visibleCount );
  double fixedTotal = 0.0;
  for ( const auto &t : tracks )
  {
    if ( !t->visible )
      continue;
    visibleTracks.push_back( t );
    if ( t->fixedWidth )
      fixedTotal += *t->fixedWidth;
    else if ( t->role == TrackRole::DepthRuler )
      fixedTotal += options.depthRulerWidth;
  }

  int stretchCount = 0;
  for ( const auto &t : visibleTracks )
  {
    if ( !t->fixedWidth && t->role != TrackRole::DepthRuler )
      ++stretchCount;
  }

  // Overflow handling: shrink fixed tracks proportionally before starving
  // stretch tracks below 1 px.
  double stretchWidth = 0.0;
  double fixedScale = 1.0;
  if ( stretchCount > 0 )
  {
    stretchWidth = std::max( 1.0, ( availableWidth - fixedTotal ) / stretchCount );
    if ( fixedTotal + stretchWidth * stretchCount > availableWidth )
    {
      // Fixed tracks alone overflow: shrink them.
      const double room = availableWidth - stretchCount * 1.0;
      if ( room > 0 && fixedTotal > 0 )
        fixedScale = room / fixedTotal;
      stretchWidth = 1.0;
    }
  }
  else if ( fixedTotal > availableWidth && fixedTotal > 0 )
  {
    fixedScale = std::max( 0.0, availableWidth / fixedTotal );
  }

  double x = targetRect.left() + options.outerMargins.left();
  const double top = targetRect.top() + options.outerMargins.top();
  const double columnHeight = targetRect.height() - options.outerMargins.top() - options.outerMargins.bottom();

  int index = 0;
  result.tracks.reserve( visibleCount );
  for ( const auto &t : visibleTracks )
  {
    TrackGeometry g;
    g.trackIndex = index++;
    g.trackId = t->id;
    g.role = t->role;

    double width = 0.0;
    if ( t->fixedWidth )
      width = *t->fixedWidth * fixedScale;
    else if ( t->role == TrackRole::DepthRuler )
      width = options.depthRulerWidth * fixedScale;
    else
      width = stretchWidth;
    width = std::max( 1.0, width );

    g.columnRect = QRectF( x, top, width, columnHeight );
    g.headerRect = QRectF( x, top, width, headerHeight );
    g.contentRect = QRectF( x, top + headerHeight, width, std::max( 1.0, columnHeight - headerHeight ) );
    x += width + options.separatorWidth;

    result.contentArea = result.contentArea.isNull() ? g.contentRect
                                                     : result.contentArea.united( g.contentRect );
    result.tracks.push_back( g );
  }
  return result;
}

} // namespace geoviz::qgis_welltrack
