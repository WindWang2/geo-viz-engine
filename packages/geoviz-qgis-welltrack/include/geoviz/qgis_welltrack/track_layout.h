/***************************************************************************
 * geoviz-qgis-welltrack — track column layout
 *
 * SPDX-License-Identifier: MIT
 ***************************************************************************/
#ifndef GEOVIZ_QWT_TRACK_LAYOUT_H
#define GEOVIZ_QWT_TRACK_LAYOUT_H

#include "geoviz/qgis_welltrack/export.h"
#include "geoviz/qgis_welltrack/track_model.h"

#include <QMarginsF>
#include <QRectF>

#include <vector>

namespace geoviz::qgis_welltrack
{

struct TrackLayoutOptions
{
  double headerHeight = 40.0;          //!< per-track header band (scale/title)
  double separatorWidth = 1.0;
  double depthRulerWidth = 72.0;       //!< DepthRuler track fixed width override
  QMarginsF outerMargins{ 1.0, 1.0, 1.0, 1.0 };
};

struct TrackGeometry
{
  int trackIndex = -1;      //!< index into TrackLayoutResult::tracks
  TrackId trackId = 0;
  TrackRole role = TrackRole::CurveTrack;
  QRectF columnRect;        //!< header + content
  QRectF headerRect;
  QRectF contentRect;
};

struct GEOVIZ_QWT_CORE_EXPORT TrackLayoutResult
{
  std::vector<TrackGeometry> tracks;   //!< visible tracks, x ascending
  QRectF contentArea;                  //!< union of content rects
  double separatorWidth = 1.0;

  //! Index into `tracks` of the track containing x; separator strips and
  //  outer margins belong to no track (-1).
  int trackAtX( double x ) const;

  const TrackGeometry *geometryForTrackId( TrackId id ) const;
};

/**
 * Lays out visible tracks left-to-right inside \a targetRect.
 * Fixed-width tracks get their width; remaining width is split equally
 * between stretch tracks (>= 1 px each; fixed tracks shrink proportionally
 * if the total overflows).
 */
GEOVIZ_QWT_CORE_EXPORT TrackLayoutResult computeTrackLayout( const WellTrackModel &model,
                                                             const QRectF &targetRect,
                                                             const TrackLayoutOptions &options = {} );

} // namespace geoviz::qgis_welltrack

#endif // GEOVIZ_QWT_TRACK_LAYOUT_H
