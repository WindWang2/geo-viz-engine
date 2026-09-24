/***************************************************************************
 * geoviz-qgis-welltrack — depth domain implementation
 *
 * SPDX-License-Identifier: MIT
 ***************************************************************************/
#include "depth_domain.h"

namespace geoviz::qgis_welltrack
{

double DepthDomain::normalize( double depth ) const
{
  if ( !isValid() || !std::isfinite( depth ) )
    return std::numeric_limits<double>::quiet_NaN();

  // Screen-order edges: for IncreasingDown the top of the rect is the
  // smaller depth; for IncreasingUp the top is the larger depth.
  const double topEdge = ( orientation == DepthOrientation::IncreasingDown ) ? minDepth() : maxDepth();
  const double bottomEdge = ( orientation == DepthOrientation::IncreasingDown ) ? maxDepth() : minDepth();
  return ( depth - topEdge ) / ( bottomEdge - topEdge );
}

double DepthDomain::depthAtFraction( double fraction ) const
{
  if ( !isValid() || !std::isfinite( fraction ) )
    return std::numeric_limits<double>::quiet_NaN();

  const double topEdge = ( orientation == DepthOrientation::IncreasingDown ) ? minDepth() : maxDepth();
  const double bottomEdge = ( orientation == DepthOrientation::IncreasingDown ) ? maxDepth() : minDepth();
  return topEdge + fraction * ( bottomEdge - topEdge );
}

double DepthDomain::depthAtY( double y, const QRectF &contentRect ) const
{
  if ( contentRect.height() <= 0.0 )
    return std::numeric_limits<double>::quiet_NaN();
  return depthAtFraction( ( y - contentRect.top() ) / contentRect.height() );
}

double DepthDomain::yForDepth( double depth, const QRectF &contentRect ) const
{
  return contentRect.top() + normalize( depth ) * contentRect.height();
}

DepthDomain DepthDomain::clampedTo( double fullMin, double fullMax ) const
{
  if ( !( std::isfinite( fullMin ) && std::isfinite( fullMax ) ) || fullMax <= fullMin )
    return *this;

  double lo = minDepth();
  double hi = maxDepth();
  double s = hi - lo;

  // Clamp the span itself to the full extent.
  if ( s > ( fullMax - fullMin ) )
    s = fullMax - fullMin;

  if ( lo < fullMin )
    lo = fullMin;
  if ( hi > fullMax )
    hi = fullMax;
  if ( hi - lo < s )
    lo = hi - s;
  if ( lo < fullMin )
    lo = fullMin;
  double newHi = std::min( lo + s, fullMax );

  // Preserve orientation; makeDomain normalizes the edge pair so the
  // invariant shallow <= deep (for Down) always holds.
  return makeDomain( lo, newHi, orientation );
}

DepthDomain makeDomain( double edgeA, double edgeB, DepthOrientation orientation )
{
  DepthDomain d;
  d.orientation = orientation;
  if ( edgeA <= edgeB )
  {
    d.shallow = edgeA;
    d.deep = edgeB;
  }
  else
  {
    d.shallow = edgeB;
    d.deep = edgeA;
  }
  return d;
}

} // namespace geoviz::qgis_welltrack
