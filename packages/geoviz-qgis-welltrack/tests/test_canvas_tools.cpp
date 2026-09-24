/***************************************************************************
 * SPDX-License-Identifier: MIT
 *
 * Tool stack on the QGIS canvas: pan tool drag, depth zoom tool marquee
 * constraints, cursor tool readout, tool switching.
 ***************************************************************************/
#include "canvas_helpers.h"

#include <qgsplotmouseevent.h>
#include <qgsplottoolpan.h>

#include <QMouseEvent>

using namespace geoviz::qgis_welltrack;
using geoviz::qgis_welltrack::test::DemoData;

class TestCanvasTools : public QObject
{
    Q_OBJECT
  private slots:
    void panToolDrillsDepth();
    void depthZoomConstraints();
    void depthZoomClick();
    void cursorToolSignals();
    void toolSwitching();
};

void TestCanvasTools::panToolDrillsDepth()
{
  DemoData demo = DemoData::make();
  WellTrackCanvas canvas;
  canvas.setModel( demo.model );
  canvas.resize( 300, 400 );
  canvas.show();
  QTest::qWaitForWindowExposed( &canvas );
  canvas.fitDepth();

  QgsPlotToolPan panTool( &canvas );
  canvas.setTool( &panTool );

  const DepthDomain before = canvas.depthDomain();

  // Simulate the gesture the way QgsPlotToolPan sees it: press, move, release.
  const QPoint start( 150, 100 );
  const QPoint end( 150, 200 );  // drag down 100 px
  QMouseEvent press( QEvent::MouseButtonPress, start, start, Qt::LeftButton, Qt::LeftButton,
                     Qt::NoModifier );
  QMouseEvent move( QEvent::MouseMove, end, end, Qt::LeftButton, Qt::LeftButton, Qt::NoModifier );
  QMouseEvent release( QEvent::MouseButtonRelease, end, end, Qt::LeftButton, Qt::NoButton,
                       Qt::NoModifier );
  QCoreApplication::sendEvent( canvas.viewport(), &press );
  QCoreApplication::sendEvent( canvas.viewport(), &move );
  QCoreApplication::sendEvent( canvas.viewport(), &release );

  const DepthDomain after = canvas.depthDomain();
  QVERIFY( std::abs( after.minDepth() - before.minDepth() ) > 1.0 );  // panned upward meaningfully
  QVERIFY( std::abs( after.span() - before.span() ) < 1e-9 );
}

void TestCanvasTools::depthZoomConstraints()
{
  DemoData demo = DemoData::make();
  WellTrackCanvas canvas;
  canvas.setModel( demo.model );
  canvas.resize( 300, 400 );
  canvas.show();
  QTest::qWaitForWindowExposed( &canvas );
  canvas.fitDepth();

  WellTrackDepthZoomTool zoomTool( &canvas );
  const QPointF start( 40, 80 );
  const QPointF moved( 200, 240 );
  const QPointF cs = zoomTool.constrainStartPoint( start );
  const QPointF cm = zoomTool.constrainMovePoint( moved );
  QCOMPARE( cs.x(), cm.x() );  // both pinned to the same x (center band)

  const QRectF raw = QRectF( cs, cm ).normalized();
  const QRectF bounds = zoomTool.constrainBounds( raw );
  QCOMPARE( bounds.left(), canvas.lastLayout().contentArea.left() );
  QCOMPARE( bounds.right(), canvas.lastLayout().contentArea.right() );
  QVERIFY( bounds.height() >= 2.0 );
}

void TestCanvasTools::depthZoomClick()
{
  DemoData demo = DemoData::make();
  WellTrackCanvas canvas;
  canvas.setModel( demo.model );
  canvas.resize( 300, 400 );
  canvas.show();
  QTest::qWaitForWindowExposed( &canvas );
  canvas.fitDepth();

  WellTrackDepthZoomTool zoomTool( &canvas );
  const DepthDomain before = canvas.depthDomain();
  const double centerDepth = canvas.depthAt( QPointF( 150, 200 ) );

  zoomTool.zoomInClickOn( QPointF( 150, 200 ) );
  const DepthDomain after = canvas.depthDomain();
  QVERIFY( std::abs( after.span() - before.span() / 2 ) < 1e-6 );
  QVERIFY( std::abs( after.depthAtFraction( 0.5 ) - centerDepth ) < 1.0 );
}

void TestCanvasTools::cursorToolSignals()
{
  DemoData demo = DemoData::make();
  WellTrackCanvas canvas;
  canvas.setModel( demo.model );
  canvas.resize( 300, 400 );
  canvas.show();
  QTest::qWaitForWindowExposed( &canvas );
  canvas.fitDepth();

  WellTrackCursorTool cursorTool( &canvas );
  canvas.setTool( &cursorTool );

  qRegisterMetaType<HitResult>( "geoviz::qgis_welltrack::HitResult" );
  QSignalSpy depthSpy( &canvas, &WellTrackCanvas::cursorDepthChanged );
  QSignalSpy hoverSpy( &canvas, &WellTrackCanvas::sampleHovered );

  QMouseEvent move( QEvent::MouseMove, QPointF( 150, 200 ), QPointF( 150, 200 ), Qt::NoButton,
                    Qt::NoButton, Qt::NoModifier );
  QCoreApplication::sendEvent( canvas.viewport(), &move );
  QVERIFY( depthSpy.count() >= 1 );
  QVERIFY( hoverSpy.count() >= 1 );
  QVERIFY( std::isfinite( depthSpy.last().at( 0 ).toDouble() ) );

  cursorTool.deactivate();  // clears crosshair, emits NaN depth
  QVERIFY( std::isnan( depthSpy.last().at( 0 ).toDouble() ) );
}

void TestCanvasTools::toolSwitching()
{
  DemoData demo = DemoData::make();
  WellTrackCanvas canvas;
  canvas.setModel( demo.model );

  QgsPlotToolPan panTool( &canvas );
  WellTrackCursorTool cursorTool( &canvas );
  QSignalSpy toolSpy( &canvas, &QgsPlotCanvas::toolChanged );

  canvas.setTool( &panTool );
  canvas.setTool( &cursorTool );
  canvas.setTool( &panTool );
  QCOMPARE( toolSpy.count(), 3 );
  QCOMPARE( canvas.tool(), &panTool );
}

GEOVIZ_QWT_QGIS_APP_MAIN( TestCanvasTools )
#include "test_canvas_tools.moc"
