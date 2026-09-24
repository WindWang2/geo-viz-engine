/***************************************************************************
 * geoviz-qgis-welltrack — curve hit testing implementation
 *
 * SPDX-License-Identifier: MIT
 ***************************************************************************/
#include "hit_testing.h"
#include "curve_lod.h"

#include <cmath>
#include <limits>

namespace geoviz::qgis_welltrack
{

HitResult hitTestNearestSample( const WellTrackModel &model, const TrackLayoutResult &layout,
                                const DepthDomain &depth, QPointF pos, double tolerancePx )
{
  HitResult result;
  if ( !depth.isValid() || layout.contentArea.height() <= 0 )
    return result;

  // Depth window equivalent to the pixel tolerance.
  const double depthTolerance = std::abs( tolerancePx ) / layout.contentArea.height() * depth.span();
  if ( !( depthTolerance > 0.0 ) )
    return result;

  double bestDist2 = std::numeric_limits<double>::infinity();
  const double tol2 = tolerancePx * tolerancePx;

  for ( const TrackGeometry &g : layout.tracks )
  {
    if ( g.role != TrackRole::CurveTrack )
      continue;
    // Cheap x rejection: the cursor must be inside this column (± tolerance).
    if ( pos.x() < g.contentRect.left() - tolerancePx || pos.x() > g.contentRect.right() + tolerancePx )
      continue;

    std::shared_ptr<TrackSpec> spec = model.track( g.trackId );
    if ( !spec )
      continue;

    const double cursorDepth = depth.depthAtY( pos.y(), g.contentRect );
    if ( !std::isfinite( cursorDepth ) )
      continue;

    for ( const CurveSpec &curve : spec->curves )
    {
      if ( curve.data.isEmpty() )
        continue;
      const VisibleSlice slice =
        visibleSlice( curve.data, cursorDepth - depthTolerance, cursorDepth + depthTolerance, 0.0 );
      for ( qsizetype i = slice.begin; i < slice.end; ++i )
      {
        const double value = curve.data.valueAt( i );
        if ( !std::isfinite( value ) )
          continue;
        const double x = spec->axis.xForValue( value, g.contentRect );
        const double y = depth.yForDepth( curve.data.depthAt( i ), g.contentRect );
        if ( !std::isfinite( x ) || !std::isfinite( y ) )
          continue;
        const double dx = x - pos.x();
        const double dy = y - pos.y();
        const double dist2 = dx * dx + dy * dy;
        if ( dist2 < bestDist2 )
        {
          bestDist2 = dist2;
          result.hit = true;
          result.trackId = g.trackId;
          result.trackTitle = spec->title;
          result.curveId = curve.id;
          result.curveLabel = curve.label;
          result.sampleIndex = i;
          result.depth = curve.data.depthAt( i );
          result.value = value;
        }
      }
    }
  }

  if ( result.hit )
  {
    result.screenDistPx = std::sqrt( bestDist2 );
    if ( result.screenDistPx > tolerancePx )
      result = HitResult();  // closest candidate is still outside tolerance
  }
  return result;
}

} // namespace geoviz::qgis_welltrack
