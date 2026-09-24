/***************************************************************************
 * geoviz-qgis-welltrack — interactive well-track canvas (gui)
 *
 * SPDX-License-Identifier: MIT
 *
 * WellTrackCanvas adapts QGIS's plot canvas shell to the well-track
 * substrate by implementing exactly the virtual surface QGIS leaves open
 * (refresh/pan/zoom/transform virtuals are default-empty upstream — see
 * docs/…/02-qgis-source-inventory.md). Pan/zoom gestures themselves, tool
 * lifecycle, transient tools, rubber band and event routing are pure QGIS
 * (QgsPlotToolPan / QgsPlotToolZoom / QgsPlotCanvas).
 ***************************************************************************/
#ifndef GEOVIZ_QWT_WELL_TRACK_CANVAS_H
#define GEOVIZ_QWT_WELL_TRACK_CANVAS_H

#include "geoviz/qgis_welltrack/depth_domain.h"
#include "geoviz/qgis_welltrack/export.h"
#include "geoviz/qgis_welltrack/hit_testing.h"
#include "geoviz/qgis_welltrack/track_model.h"

#include <qgsplotcanvas.h>

#include <memory>

class QgsPlotTool;
class QWheelEvent;
class QResizeEvent;

namespace geoviz::qgis_welltrack
{

class WellTrackSceneItem;
class WellTrackCrosshairItem;

class GEOVIZ_QWT_GUI_EXPORT WellTrackCanvas : public QgsPlotCanvas
{
    Q_OBJECT
  public:
    explicit WellTrackCanvas( QWidget *parent = nullptr );
    ~WellTrackCanvas() override;

    void setModel( std::shared_ptr<WellTrackModel> model );
    std::shared_ptr<WellTrackModel> model() const { return mModel; }

    //! Sets the shared depth window (validated; <1e-9 delta is a no-op).
    void setDepthDomain( const DepthDomain &domain );
    DepthDomain depthDomain() const { return mDepthDomain; }

    //! Zooms (centers) on a depth window; clamps to full extent when known.
    void zoomToDepth( double shallow, double deep );

    //! Fits the full data extent of the current model.
    void fitDepth();

    double depthAt( const QPointF &canvasPos ) const;

    //! Last layout (valid after first paint/refresh).
    const TrackLayoutResult &lastLayout() const;

    //! Hit test at canvas position.
    HitResult hitTest( const QPointF &canvasPos, double tolerancePx = 10.0 ) const;

    // ---- QgsPlotCanvas virtual surface ----
    void refresh() override;
    void panContentsBy( double dx, double dy ) override;
    void centerPlotOn( double x, double y ) override;
    void scalePlot( double factor ) override;
    void zoomToRect( const QRectF &rect ) override;
    QgsPoint toMapCoordinates( const QgsPointXY &point ) const override;
    QgsPointXY toCanvasCoordinates( const QgsPoint &point ) const override;
    QgsPointXY snapToPlot( QPoint point ) override;
    QgsCoordinateReferenceSystem crs() const override;

  signals:
    void depthRangeChanged( double shallow, double deep );
    void cursorDepthChanged( double depth );  //!< NaN = cursor left the content area
    void sampleHovered( const geoviz::qgis_welltrack::HitResult &hit );

  protected:
    void wheelZoom( QWheelEvent *event ) override;
    void resizeEvent( QResizeEvent *event ) override;

  private slots:
    void scheduleRefresh();

  private:
    friend class WellTrackCursorTool;

    // Single mutation path: validates, applies no-op guard, invalidates the
    // scene item cache and emits depthRangeChanged.
    void applyDepthDomain( const DepthDomain &candidate );

    void notifyCursor( const QPointF &canvasPos );
    void clearCursor();

    std::shared_ptr<WellTrackModel> mModel;
    DepthDomain mDepthDomain;
    bool mHasFullExtent = false;
    double mFullExtentMin = 0.0;
    double mFullExtentMax = 1.0;

    // Raw pointers by upstream convention (QGraphicsScene owns the items and
    // is parented to the canvas; see QgsElevationProfileCanvas::mPlotItem).
    WellTrackSceneItem *mSceneItem = nullptr;
    WellTrackCrosshairItem *mCrosshairItem = nullptr;
};

} // namespace geoviz::qgis_welltrack

Q_DECLARE_METATYPE( geoviz::qgis_welltrack::HitResult )

#endif // GEOVIZ_QWT_WELL_TRACK_CANVAS_H
