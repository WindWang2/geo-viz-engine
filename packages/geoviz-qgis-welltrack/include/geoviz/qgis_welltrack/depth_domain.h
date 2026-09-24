/***************************************************************************
 * geoviz-qgis-welltrack — shared numeric depth domain
 *
 * SPDX-License-Identifier: MIT
 *
 * The depth domain is the single shared vertical viewport of a well-track
 * composite. It is unit-agnostic (m, ft, ms, ...); MD/TVD/TVDSS/TWT
 * conversions belong to the host / domain layer (B-line), never here.
 ***************************************************************************/
#ifndef GEOVIZ_QWT_DEPTH_DOMAIN_H
#define GEOVIZ_QWT_DEPTH_DOMAIN_H

#include "geoviz/qgis_welltrack/export.h"

#include <QRectF>

#include <cmath>
#include <limits>

namespace geoviz::qgis_welltrack
{

/**
 * \brief Which way depth increases on screen.
 *
 * Well tracks default to IncreasingDown (shallow at top). IncreasingUp is
 * provided for hosts that display e.g. two-way-time sections with an upward
 * axis. QGIS's QgsPlotAxis has no inversion API (verified against the 4.2
 * snapshot), so the kernel owns this mapping.
 */
enum class DepthOrientation
{
  IncreasingDown,
  IncreasingUp,
};

/**
 * \brief Shared vertical viewport.
 *
 * `shallow`/`deep` are depth-unit window edges; for IncreasingDown the
 * smaller value renders at the top of the content rect. A "reversed" pair
 * (shallow > deep) is not an inversion switch — normalize it away by
 * construction (use makeDomain()).
 */
struct GEOVIZ_QWT_CORE_EXPORT DepthDomain
{
  double shallow = 0.0;
  double deep = 1.0;
  DepthOrientation orientation = DepthOrientation::IncreasingDown;

  //! Numeric window edges, order-independent.
  double minDepth() const { return shallow < deep ? shallow : deep; }
  double maxDepth() const { return shallow > deep ? shallow : deep; }

  //! Absolute window span (>= 0).
  double span() const { return maxDepth() - minDepth(); }

  //! TRUE when both edges are finite and the span is positive.
  bool isValid() const
  {
    return std::isfinite( shallow ) && std::isfinite( deep ) && ( maxDepth() - minDepth() ) > 0.0;
  }

  //! Both edges finite (span may be zero).
  bool isFinite() const { return std::isfinite( shallow ) && std::isfinite( deep ); }

  /**
   * Maps a depth to [0,1] across the window in *screen order* (0 = top edge
   * of the content rect). Values outside the window map outside [0,1];
   * invalid/degenerate domains return NaN.
   */
  double normalize( double depth ) const;

  /** Inverse of normalize(): fraction (screen order) → depth. */
  double depthAtFraction( double fraction ) const;

  /** Depth at pixel y inside \a contentRect (y outside the rect yields depths outside the window). */
  double depthAtY( double y, const QRectF &contentRect ) const;

  /** Pixel y for \a depth inside \a contentRect (no clamping — callers clip). */
  double yForDepth( double depth, const QRectF &contentRect ) const;

  /**
   * Clamps a candidate window to \a fullMin..fullMax, preserving span where
   * possible (span itself clamped to the full extent).
   */
  DepthDomain clampedTo( double fullMin, double fullMax ) const;
};

//! Builds a valid domain from unordered edges.
GEOVIZ_QWT_CORE_EXPORT DepthDomain makeDomain( double edgeA, double edgeB,
                                               DepthOrientation orientation = DepthOrientation::IncreasingDown );

//! No-op guard threshold: window deltas below this are treated as identical
//  (prevents multi-canvas sync cascades; mirrors geoviz_well_log's 1e-9).
inline constexpr double kDepthNoOpEpsilon = 1e-9;

} // namespace geoviz::qgis_welltrack

#endif // GEOVIZ_QWT_DEPTH_DOMAIN_H
