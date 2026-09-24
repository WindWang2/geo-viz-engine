/***************************************************************************
 * geoviz-qgis-welltrack — curve hit testing
 *
 * SPDX-License-Identifier: MIT
 ***************************************************************************/
#ifndef GEOVIZ_QWT_HIT_TESTING_H
#define GEOVIZ_QWT_HIT_TESTING_H

#include "geoviz/qgis_welltrack/depth_domain.h"
#include "geoviz/qgis_welltrack/export.h"
#include "geoviz/qgis_welltrack/track_layout.h"
#include "geoviz/qgis_welltrack/track_model.h"

#include <QPointF>

namespace geoviz::qgis_welltrack
{

struct HitResult
{
  bool hit = false;
  TrackId trackId = 0;
  QString trackTitle;
  SeriesId curveId = 0;
  QString curveLabel;
  qsizetype sampleIndex = -1;
  double depth = 0.0;
  double value = 0.0;
  double screenDistPx = 0.0;   //!< Euclidean distance to the sample, px
};

/**
 * Nearest-sample hit test. Only samples inside a depth window of
 * ±tolerancePx (converted via the content height) are examined — O(log n)
 * to locate the window plus O(window) scan. NaN values are skipped.
 * tolerancePx is internally capped (50 px) so interactive callers cannot
 * degrade this into a full-array scan.
 */
GEOVIZ_QWT_CORE_EXPORT HitResult hitTestNearestSample( const WellTrackModel &model,
                                                       const TrackLayoutResult &layout,
                                                       const DepthDomain &depth, QPointF pos,
                                                       double tolerancePx = 10.0 );

} // namespace geoviz::qgis_welltrack

#endif // GEOVIZ_QWT_HIT_TESTING_H
