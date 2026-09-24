/***************************************************************************
 * geoviz-qgis-welltrack — non-owning curve sample view
 *
 * SPDX-License-Identifier: MIT
 *
 * Zero-copy data admission for large sample counts (1e5..1e6 per curve).
 * The view borrows caller-owned memory; hosts guarantee the buffers outlive
 * every WellTrackModel snapshot that references them. The kernel never
 * copies sample arrays on the render path.
 ***************************************************************************/
#ifndef GEOVIZ_QWT_CURVE_DATA_H
#define GEOVIZ_QWT_CURVE_DATA_H

#include "geoviz/qgis_welltrack/export.h"

#include <QtGlobal>

#include <cstring>

namespace geoviz::qgis_welltrack
{

enum class SampleFormat
{
  Float32,
  Float64,
};

/**
 * \brief Read-only, strided view over parallel depth/value arrays.
 *
 * Contract (enforced by validateDepthMonotonic, assumed everywhere else):
 *   - depths are non-decreasing (ascending monotone) so binary search works;
 *   - NaN depths are a caller bug (they break the ordering invariant);
 *   - NaN *values* are legal and render as gaps.
 *
 * Strides are in bytes; 0 means "natural element size" for the format.
 * Unaligned bases are safe (loads go through memcpy).
 */
struct CurveSeriesView
{
  const void *depths = nullptr;
  const void *values = nullptr;
  qsizetype count = 0;
  SampleFormat format = SampleFormat::Float64;
  qsizetype depthStrideBytes = 0;
  qsizetype valueStrideBytes = 0;

  qsizetype depthStride() const
  {
    return depthStrideBytes > 0 ? depthStrideBytes
           : ( format == SampleFormat::Float64 ? static_cast<qsizetype>( sizeof( double ) )
                                                : static_cast<qsizetype>( sizeof( float ) ) );
  }
  qsizetype valueStride() const { return valueStrideBytes > 0 ? valueStrideBytes : depthStride(); }

  bool isEmpty() const { return count <= 0 || depths == nullptr || values == nullptr; }

  double depthAt( qsizetype i ) const
  {
    return readDouble( depths, i, format, depthStride() );
  }
  double valueAt( qsizetype i ) const
  {
    return readDouble( values, i, format, valueStride() );
  }

private:
  static double readDouble( const void *base, qsizetype index, SampleFormat fmt, qsizetype stride )
  {
    const char *p = static_cast<const char *>( base ) + index * stride;
    if ( fmt == SampleFormat::Float64 )
    {
      double d = 0.0;
      std::memcpy( &d, p, sizeof( double ) );
      return d;
    }
    float f = 0.0f;
    std::memcpy( &f, p, sizeof( float ) );
    return static_cast<double>( f );
  }
};

/**
 * Depth-monotonicity audit. Returns the index of the first violating sample
 * (NaN depth or depth[i] < depth[i-1]), or -1 when the view is valid.
 * O(n); intended for load time / debug builds, never on the render path.
 */
GEOVIZ_QWT_CORE_EXPORT qsizetype validateDepthMonotonic( const CurveSeriesView &view );

//! Convenience: view over packed double arrays.
inline CurveSeriesView makeDoubleView( const double *depths, const double *values, qsizetype count )
{
  CurveSeriesView v;
  v.depths = depths;
  v.values = values;
  v.count = count;
  v.format = SampleFormat::Float64;
  return v;
}

//! Convenience: view over two double members of a struct array; each member
//! address advances by sizeof(S) per element, so the stride is one element.
template <typename S>
CurveSeriesView makeMemberView( const S *base, qsizetype count, double S::*depthMember,
                                double S::*valueMember )
{
  CurveSeriesView v;
  if ( count > 0 )
  {
    v.depths = &( base->*depthMember );
    v.values = &( base->*valueMember );
  }
  v.count = count;
  v.format = SampleFormat::Float64;
  v.depthStrideBytes = sizeof( S );
  v.valueStrideBytes = sizeof( S );
  return v;
}

} // namespace geoviz::qgis_welltrack

#endif // GEOVIZ_QWT_CURVE_DATA_H
