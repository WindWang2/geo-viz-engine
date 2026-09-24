/***************************************************************************
 * geoviz-qgis-welltrack — curve data audit
 *
 * SPDX-License-Identifier: MIT
 ***************************************************************************/
#include "curve_data.h"

#include <cmath>

namespace geoviz::qgis_welltrack
{

qsizetype validateDepthMonotonic( const CurveSeriesView &view )
{
  if ( view.isEmpty() )
    return -1;
  double previous = view.depthAt( 0 );
  if ( !std::isfinite( previous ) )
    return 0;
  for ( qsizetype i = 1; i < view.count; ++i )
  {
    const double d = view.depthAt( i );
    if ( !std::isfinite( d ) )
      return i;
    if ( d < previous )
      return i;
    previous = d;
  }
  return -1;
}

} // namespace geoviz::qgis_welltrack
