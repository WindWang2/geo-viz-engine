/***************************************************************************
 * geoviz-qgis-welltrack — visible slicing + extrema-preserving LOD
 *
 * SPDX-License-Identifier: MIT
 *
 * Behavior oracle: packages/geoviz_well_log downsample.py (floor binning,
 * per-bin min/max emitted in original index order, NaN break markers).
 * These functions are pure data: thread-safe against immutable buffers.
 ***************************************************************************/
#ifndef GEOVIZ_QWT_CURVE_LOD_H
#define GEOVIZ_QWT_CURVE_LOD_H

#include "geoviz/qgis_welltrack/curve_data.h"
#include "geoviz/qgis_welltrack/export.h"

#include <vector>

namespace geoviz::qgis_welltrack
{

/** Half-open [begin, end) index range into a CurveSeriesView. */
struct VisibleSlice
{
  qsizetype begin = 0;
  qsizetype end = 0;

  qsizetype size() const { return end - begin; }
  bool isEmpty() const { return end <= begin; }
};

/**
 * Binary-search slice of samples with depth inside
 * [fromDepth - margin, toDepth + margin] (margin = fraction of the span).
 * Requires non-decreasing depths (CurveSeriesView contract).
 * O(log n). Degenerate inputs yield empty slices, never crashes.
 */
GEOVIZ_QWT_CORE_EXPORT VisibleSlice visibleSlice( const CurveSeriesView &v, double fromDepth,
                                                  double toDepth, double marginFraction = 0.05 );

/** One emitted LOD point. `breakAfter` closes the polyline after this point. */
struct EnvelopeSample
{
  double depth = 0.0;
  double value = 0.0;
  bool breakAfter = false;
};

/**
 * Extrema-preserving min/max envelope over a slice, one bin per screen
 * depth-row (bins = content height).
 *
 * Contract (pinned by tests, mirrors geoviz_well_log):
 *  - each bin emits its minimum and maximum sample, in original index order
 *    (if argmin < argmax, min first; else max first);
 *  - a bin whose samples include non-finite values additionally emits the
 *    first non-finite sample *in index order* and sets breakAfter on the
 *    bin's last emitted point so polylines never bridge the gap;
 *  - empty bins are skipped;
 *  - the visible window's global min/max are always present in the output.
 *
 * Small-slice fast path: sliceSize <= max(2*bins, 64) → raw pass-through.
 * O(slice). `out` is reused (cleared then filled) for steady-state zero
 * allocation after warmup.
 */
GEOVIZ_QWT_CORE_EXPORT void buildEnvelope( const CurveSeriesView &v, VisibleSlice slice, int bins,
                                           std::vector<EnvelopeSample> &out );

/**
 * Linear interpolation of the value at \a depth (binary search + lerp on the
 * monotone depth array). Returns NaN when the depth is outside the sample
 * range or the bracketing samples include non-finite values. This is the
 * cursor-readout primitive (mirrors geoviz_well_log's bisect readout).
 */
GEOVIZ_QWT_CORE_EXPORT double interpolateAtDepth( const CurveSeriesView &v, double depth );

} // namespace geoviz::qgis_welltrack

#endif // GEOVIZ_QWT_CURVE_LOD_H
