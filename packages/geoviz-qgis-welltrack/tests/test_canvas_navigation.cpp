/***************************************************************************
 * SPDX-License-Identifier: MIT
 *
 * Navigation semantics: pan math, centered scale, rect zoom (normal / tiny /
 * inverted), wheel anchor (normal + Ctrl fine), coordinate round-trip,
 * snapping, invalid CRS, IncreasingUp orientation.
 ***************************************************************************/
#include "canvas_helpers.h"

#include <QWheelEvent>

using namespace geoviz::qgis_welltrack;
using geoviz::qgis_welltrack::test::DemoData;

class TestCanvasNavigation : public QObject
{
    Q_OBJECT
  private slots:
    void panByDelta();
    void panClampsAtExtent();
    void scalePlotCenters();
    void zoomToRect();
    void zoomToRectTinyNoOp();
    void zoomToRectInvertedNoOp();
    void wheelZoomAnchorsCursor();
    void wheelZoomCtrlFine();
    void coordinateRoundTrip();
    void snapToPlot();
    void crsInvalid();
    void orientationUpNavigation();

  private:
    static void prepareCanvas( WellTrackCanvas &canvas, DemoData &demo );
};

void TestCanvasNavigation::prepareCanvas( WellTrackCanvas &canvas, DemoData &demo )
{
  demo = DemoData::make();
  canvas.setModel( demo.model );
  canvas.resize( 300, 400 );
  canvas.show();
  QVERIFY( QTest::qWaitForWindowExposed( &canvas ) );
  canvas.fitDepth();
  canvas.zoomToDepth( 1200.0, 1500.0 );  // sub-window so pan/zoom are unclamped
  QTRY_VERIFY( !canvas.lastLayout().tracks.empty() );
}

void TestCanvasNavigation::panByDelta()
{
  DemoData demo;
  WellTrackCanvas canvas;
  prepareCanvas( canvas, demo );

  const DepthDomain before = canvas.depthDomain();
  const double contentHeight = canvas.lastLayout().contentArea.height();
  const double span = before.span();
  QVERIFY( contentHeight > 0 );

  // Drag content down by 100 px → window shifts up by 100/h * span.
  canvas.panContentsBy( 0.0, 100.0 );
  const DepthDomain after = canvas.depthDomain();
  const double expectedShift = -100.0 / contentHeight * span;
  QVERIFY( std::abs( after.minDepth() - ( before.minDepth() + expectedShift ) ) < 1e-6 );
  QVERIFY( std::abs( after.span() - span ) < 1e-9 );
}

void TestCanvasNavigation::panClampsAtExtent()
{
  DemoData demo;
  WellTrackCanvas canvas;
  prepareCanvas( canvas, demo );

  canvas.panContentsBy( 0.0, 1e6 );
  const DepthDomain d = canvas.depthDomain();
  QVERIFY( d.minDepth() >= 1000.0 - 1e-6 );
  QVERIFY( d.maxDepth() <= demo.depths.back() + 1e-6 );
}

void TestCanvasNavigation::scalePlotCenters()
{
  DemoData demo;
  WellTrackCanvas canvas;
  prepareCanvas( canvas, demo );

  const DepthDomain before = canvas.depthDomain();
  const double centerBefore = before.minDepth() + before.span() / 2;
  canvas.scalePlot( 2.0 );
  const DepthDomain after = canvas.depthDomain();
  QVERIFY( std::abs( after.span() - before.span() / 2.0 ) < 1e-6 );
  QVERIFY( std::abs( ( after.minDepth() + after.span() / 2 ) - centerBefore ) < 1e-6 );
}

void TestCanvasNavigation::zoomToRect()
{
  DemoData demo;
  WellTrackCanvas canvas;
  prepareCanvas( canvas, demo );

  const QRectF content = canvas.lastLayout().contentArea;
  const double dTop = canvas.depthAt( QPointF( 0, content.top() ) );
  const double dQuarter = canvas.depthAt( QPointF( 0, content.top() + content.height() / 4 ) );
  const double dHalf = canvas.depthAt( QPointF( 0, content.top() + content.height() / 2 ) );

  canvas.zoomToRect( QRectF( content.left(), content.top(), content.width(), content.height() / 2 ) );
  const DepthDomain after = canvas.depthDomain();
  QVERIFY( std::abs( after.minDepth() - dTop ) < 1e-6 );
  QVERIFY( std::abs( after.maxDepth() - dHalf ) < 1e-6 );
  QVERIFY( dQuarter > dTop );  // sanity: depth increases downward
}

void TestCanvasNavigation::zoomToRectTinyNoOp()
{
  DemoData demo;
  WellTrackCanvas canvas;
  prepareCanvas( canvas, demo );
  const DepthDomain before = canvas.depthDomain();
  canvas.zoomToRect( QRectF( 10, 50, 5, 1 ) );  // < 2 px high
  QCOMPARE( canvas.depthDomain().minDepth(), before.minDepth() );
}

void TestCanvasNavigation::zoomToRectInvertedNoOp()
{
  DemoData demo;
  WellTrackCanvas canvas;
  prepareCanvas( canvas, demo );
  const DepthDomain before = canvas.depthDomain();
  // Negative height (QRectF turns it inside-out → height < 2): no-op.
  canvas.zoomToRect( QRectF( 10, 300, 5, -50 ) );
  QCOMPARE( canvas.depthDomain().minDepth(), before.minDepth() );
}

void TestCanvasNavigation::wheelZoomAnchorsCursor()
{
  DemoData demo;
  WellTrackCanvas canvas;
  prepareCanvas( canvas, demo );

  const QPointF cursor( 150, 200 );
  const double anchorBefore = canvas.depthAt( cursor );
  const double spanBefore = canvas.depthDomain().span();

  // 240 delta = 2 steps × 1.2 → span /= 1.44.
  QWheelEvent event( cursor, cursor, QPoint( 0, 0 ), QPoint( 0, 240 ), Qt::NoButton, Qt::NoModifier,
                     Qt::NoScrollPhase, false );
  QCoreApplication::sendEvent( &canvas, &event );

  QVERIFY( canvas.depthDomain().span() < spanBefore / 1.4 );
  const double anchorAfter = canvas.depthAt( cursor );
  QVERIFY2( std::abs( anchorBefore - anchorAfter ) < 0.5,
            qPrintable( QStringLiteral( "anchor moved: %1 → %2" ).arg( anchorBefore ).arg( anchorAfter ) ) );
}

void TestCanvasNavigation::wheelZoomCtrlFine()
{
  DemoData demo;
  WellTrackCanvas canvas;
  prepareCanvas( canvas, demo );

  const double spanBefore = canvas.depthDomain().span();
  QWheelEvent event( QPointF( 150, 200 ), QPointF( 150, 200 ), QPoint( 0, 0 ), QPoint( 0, 120 ),
                     Qt::NoButton, Qt::ControlModifier, Qt::NoScrollPhase, false );
  QCoreApplication::sendEvent( &canvas, &event );
  const double spanAfter = canvas.depthDomain().span();
  // Fine factor 1.05 — much less shrink than the normal 1.2.
  QVERIFY( spanAfter > spanBefore / 1.1 );
  QVERIFY( spanAfter < spanBefore );
}

void TestCanvasNavigation::coordinateRoundTrip()
{
  DemoData demo;
  WellTrackCanvas canvas;
  prepareCanvas( canvas, demo );

  const QgsPoint mapped = canvas.toMapCoordinates( QgsPointXY( 150, 200 ) );
  QVERIFY( std::isfinite( mapped.x() ) );
  QVERIFY( std::isfinite( mapped.y() ) );

  const QgsPointXY back = canvas.toCanvasCoordinates( mapped );
  QVERIFY( std::abs( back.x() - 150.0 ) < 1e-3 );
  QVERIFY( std::abs( back.y() - 200.0 ) < 1e-3 );
}

void TestCanvasNavigation::snapToPlot()
{
  DemoData demo;
  WellTrackCanvas canvas;
  prepareCanvas( canvas, demo );

  const double sampleDepth = demo.depths[ 1000 ];
  const TrackLayoutResult &layout = canvas.lastLayout();
  const TrackGeometry *gr = nullptr;
  for ( const auto &g : layout.tracks )
  {
    if ( g.role == TrackRole::CurveTrack )
      gr = &g;
  }
  QVERIFY( gr );
  const double y = canvas.depthDomain().yForDepth( sampleDepth, gr->contentRect );
  const double value = demo.values[ 1000 ];
  const double px = demo.model->track( gr->trackId )->axis.xForValue( value, gr->contentRect );

  const QgsPointXY snapped = canvas.snapToPlot( QPoint( static_cast<int>( px ), static_cast<int>( y ) ) );
  QVERIFY( !snapped.isEmpty() );
  QVERIFY( std::abs( snapped.y() - sampleDepth ) < 1.0 );
}

void TestCanvasNavigation::crsInvalid()
{
  QVERIFY( !WellTrackCanvas().crs().isValid() );
}

void TestCanvasNavigation::orientationUpNavigation()
{
  DemoData demo;
  WellTrackCanvas canvas;
  prepareCanvas( canvas, demo );

  DepthDomain up = canvas.depthDomain();
  up.orientation = DepthOrientation::IncreasingUp;
  canvas.setDepthDomain( up );
  QVERIFY( canvas.depthDomain().orientation == DepthOrientation::IncreasingUp );

  // yForDepth flips: the deep edge is now at the top.
  const QRectF content = canvas.lastLayout().contentArea;
  QVERIFY( canvas.depthDomain().yForDepth( canvas.depthDomain().maxDepth(), content )
           < canvas.depthDomain().yForDepth( canvas.depthDomain().minDepth(), content ) );

  // Pan: dragging content down exposes what was above the top edge — for
  // IncreasingUp the top edge is the DEEP end, so the window moves deeper.
  const DepthDomain before = canvas.depthDomain();
  canvas.panContentsBy( 0.0, 100.0 );
  QVERIFY( canvas.depthDomain().minDepth() > before.minDepth() );
}

GEOVIZ_QWT_QGIS_APP_MAIN( TestCanvasNavigation )
#include "test_canvas_navigation.moc"
