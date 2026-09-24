/***************************************************************************
 * geoviz-qgis-welltrack — well-track interaction tools (gui)
 *
 * SPDX-License-Identifier: MIT
 *
 * Pan is upstream's QgsPlotToolPan used as-is (the canvas implements
 * panContentsBy). The depth zoom tool specializes QgsPlotToolZoom through
 * its documented C++ constrain hooks — no upstream code is copied. The
 * cursor tool drives the crosshair + readout signals.
 ***************************************************************************/
#ifndef GEOVIZ_QWT_WELL_TRACK_TOOLS_H
#define GEOVIZ_QWT_WELL_TRACK_TOOLS_H

#include "geoviz/qgis_welltrack/export.h"

#include <qgsplottool.h>
#include <qgsplottoolzoom.h>

namespace geoviz::qgis_welltrack
{

class WellTrackCanvas;

//! Lifetime note: QgsPlotTool dtor auto-unsets itself from the canvas, so
//! tools may be stack-allocated in a scope that ends before the canvas dies
//! — declare the canvas FIRST in that scope (destruction order then runs
//! tools before canvas), as the upstream tools do.

/**
 * \brief Marquee zoom restricted to the depth axis: the rubber band spans
 * the full content width, and click-zoom doubles / halves the depth span.
 */
class GEOVIZ_QWT_GUI_EXPORT WellTrackDepthZoomTool : public QgsPlotToolZoom
{
    Q_OBJECT
  public:
    explicit WellTrackDepthZoomTool( WellTrackCanvas *canvas );

  protected:
    QPointF constrainStartPoint( QPointF scenePoint ) const override;
    QPointF constrainMovePoint( QPointF scenePoint ) const override;
    QRectF constrainBounds( const QRectF &sceneBounds ) const override;
    void zoomOutClickOn( QPointF scenePoint ) override;
    void zoomInClickOn( QPointF scenePoint ) override;

  private:
    QRectF plotArea() const;
};

/**
 * \brief Cursor readout: crosshair + cursorDepthChanged + sampleHovered.
 */
class GEOVIZ_QWT_GUI_EXPORT WellTrackCursorTool : public QgsPlotTool
{
    Q_OBJECT
  public:
    explicit WellTrackCursorTool( WellTrackCanvas *canvas );

    void plotMoveEvent( QgsPlotMouseEvent *event ) override;
    void plotReleaseEvent( QgsPlotMouseEvent *event ) override;
    void deactivate() override;
};

} // namespace geoviz::qgis_welltrack

#endif // GEOVIZ_QWT_WELL_TRACK_TOOLS_H
