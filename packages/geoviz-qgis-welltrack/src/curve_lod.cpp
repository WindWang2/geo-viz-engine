/***************************************************************************
 * geoviz-qgis-welltrack — visible slicing + envelope implementation
 *
 * SPDX-License-Identifier: MIT
 ***************************************************************************/
#include "geoviz/qgis_welltrack/curve_lod.h"

#include <QtGlobal>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>

namespace geoviz::qgis_welltrack
{

namespace
{

// Manual binary searches (index space) — avoids materializing iterators
// over strided reads.
qsizetype lowerBoundDepth( const CurveSeriesView &v, double depth )
{
  qsizetype lo = 0;
  qsizetype hi = v.count;
  while ( lo < hi )
  {
    const qsizetype mid = lo + ( hi - lo ) / 2;
    if ( v.depthAt( mid ) < depth )
      lo = mid + 1;
    else
      hi = mid;
  }
  return lo;
}

qsizetype upperBoundDepth( const CurveSeriesView &v, double depth )
{
  qsizetype lo = 0;
  qsizetype hi = v.count;
  while ( lo < hi )
  {
    const qsizetype mid = lo + ( hi - lo ) / 2;
    if ( v.depthAt( mid ) <= depth )
      lo = mid + 1;
    else
      hi = mid;
  }
  return lo;
}

} // namespace

VisibleSlice visibleSlice( const CurveSeriesView &v, double fromDepth, double toDepth,
                           double marginFraction )
{
  VisibleSlice slice;
  if ( v.isEmpty() )
    return slice;

  const double lo = std::min( fromDepth, toDepth );
  const double hi = std::max( fromDepth, toDepth );
  if ( !std::isfinite( lo ) || !std::isfinite( hi ) )
    return slice;

  const double margin = std::abs( marginFraction ) * ( hi - lo );
  const double from = lo - margin;
  const double to = hi + margin;

  slice.begin = lowerBoundDepth( v, from );
  slice.end = upperBoundDepth( v, to );

  slice.begin = std::clamp<qsizetype>( slice.begin, 0, v.count );
  slice.end = std::clamp<qsizetype>( slice.end, slice.begin, v.count );
  return slice;
}

void buildEnvelope( const CurveSeriesView &v, VisibleSlice slice, int bins,
                    std::vector<EnvelopeSample> &out )
{
  out.clear();
  const qsizetype n = slice.isEmpty() ? 0 : slice.size();
  if ( n <= 0 )
    return;

  // ---- pass-through fast path: few samples, LOD not worth it ----
  const qsizetype passThroughThreshold = std::max<qsizetype>( 2 * static_cast<qsizetype>( bins ), 64 );
  if ( n <= passThroughThreshold )
  {
    bool gapPending = false;  // a non-finite sample was seen since the last emitted point
    for ( qsizetype i = slice.begin; i < slice.end; ++i )
    {
      const double value = v.valueAt( i );
      if ( std::isfinite( value ) )
      {
        if ( gapPending && !out.empty() )
          out.back().breakAfter = true;  // break sits on the finite sample before the gap
        gapPending = false;
        EnvelopeSample s;
        s.depth = v.depthAt( i );
        s.value = value;
        out.push_back( s );
      }
      else
      {
        gapPending = true;
      }
    }
    if ( gapPending && !out.empty() )
      out.back().breakAfter = true;  // trailing gap: harmless, keeps contract uniform
    return;
  }

  if ( bins <= 0 )
    bins = 1;

  const double d0 = v.depthAt( slice.begin );
  const double d1 = v.depthAt( slice.end - 1 );
  const double span = d1 - d0;
  const bool degenerateSpan = !( span > 0.0 );

  auto binOf = [&]( double depth ) -> int
  {
    if ( degenerateSpan )
      return 0;
    double t = ( depth - d0 ) / span;
    int b = static_cast<int>( t * bins );
    if ( b < 0 )
      b = 0;
    if ( b >= bins )
      b = bins - 1;
    return b;
  };

  struct BinState
  {
    void reset()
    {
      minIdx = -1;
      maxIdx = -1;
      sawNaN = false;
    }
    qsizetype minIdx = -1;   // index of running finite minimum
    qsizetype maxIdx = -1;   // index of running finite maximum
    bool sawNaN = false;
  };

  BinState cur;
  cur.reset();
  // Set when a bin with only non-finite samples was flushed: the gap must
  // break the polyline at the last emitted finite point, otherwise the two
  // finite bins on either side of the NaN-only bin would be bridged.
  bool gapAfterLastEmitted = false;

  auto flushBin = [ & ]()
  {
    if ( cur.minIdx < 0 )
    {
      if ( cur.sawNaN )
        gapAfterLastEmitted = true;  // NaN-only bin: force break on next emit
      cur.reset();
      return;
    }
    const qsizetype firstIdx = ( cur.minIdx < cur.maxIdx ) ? cur.minIdx : cur.maxIdx;
    const qsizetype secondIdx = ( cur.minIdx < cur.maxIdx ) ? cur.maxIdx : cur.minIdx;
    const bool single = ( cur.minIdx == cur.maxIdx );

    if ( gapAfterLastEmitted && !out.empty() )
      out.back().breakAfter = true;
    gapAfterLastEmitted = false;

    EnvelopeSample a;
    a.depth = v.depthAt( firstIdx );
    a.value = v.valueAt( firstIdx );
    out.push_back( a );

    if ( !single )
    {
      EnvelopeSample b;
      b.depth = v.depthAt( secondIdx );
      b.value = v.valueAt( secondIdx );
      out.push_back( b );
    }
    if ( cur.sawNaN )
      out.back().breakAfter = true;
    cur.reset();
  };

  int currentBin = binOf( v.depthAt( slice.begin ) );
  for ( qsizetype i = slice.begin; i < slice.end; ++i )
  {
    const int b = binOf( v.depthAt( i ) );
    if ( b != currentBin )
    {
      flushBin();
      currentBin = b;
    }
    const double value = v.valueAt( i );
    if ( !std::isfinite( value ) )
    {
      cur.sawNaN = true;
      continue;
    }
    if ( cur.minIdx < 0 || value < v.valueAt( cur.minIdx ) )
      cur.minIdx = i;
    if ( cur.maxIdx < 0 || value > v.valueAt( cur.maxIdx ) )
      cur.maxIdx = i;
  }
  flushBin();
}

double interpolateAtDepth( const CurveSeriesView &v, double depth )
{
  if ( v.isEmpty() || !std::isfinite( depth ) )
    return std::numeric_limits<double>::quiet_NaN();

  if ( depth < v.depthAt( 0 ) || depth > v.depthAt( v.count - 1 ) )
    return std::numeric_limits<double>::quiet_NaN();

  const qsizetype hi = lowerBoundDepth( v, depth );
  // hi is the first index with depthAt(hi) >= depth.
  if ( hi >= v.count )
    return v.valueAt( v.count - 1 );
  const double dHi = v.depthAt( hi );
  if ( hi == 0 )
  {
    return qFuzzyIsNull( dHi - depth ) ? v.valueAt( 0 )
                                       : std::numeric_limits<double>::quiet_NaN();
  }
  const qsizetype lo = hi - 1;
  const double dLo = v.depthAt( lo );
  const double vLo = v.valueAt( lo );
  const double vHi = v.valueAt( hi );
  if ( !std::isfinite( vLo ) || !std::isfinite( vHi ) )
    return std::numeric_limits<double>::quiet_NaN();
  if ( qFuzzyIsNull( dHi - dLo ) )
    return vHi;
  const double t = ( depth - dLo ) / ( dHi - dLo );
  return vLo + t * ( vHi - vLo );
}

} // namespace geoviz::qgis_welltrack
