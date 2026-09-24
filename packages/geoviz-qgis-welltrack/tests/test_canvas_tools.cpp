/***************************************************************************
 * SPDX-License-Identifier: MIT
 *
 * Tool stack on the QGIS canvas, driven gesture-level through viewport
 * events (protected constrain hooks are not directly callable; the marquee
 * equivalence is asserted through the resulting depth domain).
 ***************************************************************************/
#include "canvas_helpers.h"

#include <qgsplotmouseevent.h>
#include <qgsplottoolpan.h>

#include <QMouseEvent>

using namespace geoviz::qgis_welltrack;
using geoviz::qgis_welltrack::test::DemoData;

namespace
{

void sendMouse( QWidget *target, QEvent::Type type, const QPointF &pos,
                Qt::MouseButton button = Qt::LeftButton, Qt::MouseButtons buttons = Qt::LeftButton,
                Qt::KeyboardModifiers mods = Qt::NoModifier )
{
  QMouseEvent event( type, pos, pos, button, buttons, mods );
  QCoreApplication::sendEvent( target, &event );
}

} // namespace

class TestCanvasTools : public QObject
{
    Q_OBJECT
  private slots:
    void panToolDrillsDepth();
    void depthZoomMarqueeGesture();
    void depthZoomClick();
    void cursorToolSignals();
    void cursorToolHeaderIsNaN();
    void transientMidButtonPanSmoke();
    void toolSwitching();

  private:
    static void prepareCanvas( WellTrackCanvas &canvas, DemoData &demo );
};

void TestCanvasTools::prepareCanvas( WellTrackCanvas &canvas, DemoData &demo )
{
  demo = DemoData::make();
  canvas.setModel( demo.model );
  canvas.resize( 300, 400 );
  canvas.show();
  QVERIFY( QTest::qWaitForWindowExposed( &canvas ) );
  canvas.fitDepth();
  canvas.zoomToDepth( 1200.0, 1500.0 );  // sub-window: pan/zoom have room
  QTRY_VERIFY( !canvas.lastLayout().tracks.empty() );
}

void TestCanvasTools::panToolDrillsDepth()
{
  DemoData demo;
  WellTrackCanvas canvas;
  prepareCanvas( canvas, demo );

  QgsPlotToolPan panTool( &canvas );
  canvas.setTool( &panTool );

  const DepthDomain before = canvas.depthDomain();
  sendMouse( canvas.viewport(), QEvent::MouseButtonPress, QPointF( 150, 100 ) );
  sendMouse( canvas.viewport(), QEvent::MouseMove, QPointF( 150, 200 ) );
  sendMouse( canvas.viewport(), QEvent::MouseButtonRelease, QPointF( 150, 200 ) );

  const DepthDomain after = canvas.depthDomain();
  QCOMPARE( after.span(), before.span() );                          // pan never zooms
  QVERIFY( after.minDepth() < before.minDepth() - 1.0 );            // content moved down
}

void TestCanvasTools::depthZoomMarqueeGesture()
{
  DemoData demo;
  WellTrackCanvas canvas;
  prepareCanvas( canvas, demo );

  WellTrackDepthZoomTool zoomTool( &canvas );
  canvas.setTool( &zoomTool );

  const double dTop = canvas.depthAt( QPointF( 150, 100.0 ) );
  const double dBottom = canvas.depthAt( QPointF( 150, 300.0 ) );
  QVERIFY( std::isfinite( dTop ) && std::isfinite( dBottom ) );

  // Drag the marquee: the tool's constrained full-width band ends in
  // zoomToRect on release; the resulting window must be exactly the depths
  // spanned by the dragged y range.
  sendMouse( canvas.viewport(), QEvent::MouseButtonPress, QPointF( 40, 100.0 ) );
  sendMouse( canvas.viewport(), QEvent::MouseMove, QPointF( 220, 300.0 ) );
  sendMouse( canvas.viewport(), QEvent::MouseButtonRelease, QPointF( 220, 300.0 ) );

  const DepthDomain after = canvas.depthDomain();
  QVERIFY( std::abs( after.minDepth() - dTop ) < 0.5 );
  QVERIFY( std::abs( after.maxDepth() - dBottom ) < 0.5 );
}

void TestCanvasTools::depthZoomClick()
{
  DemoData demo;
  WellTrackCanvas canvas;
  prepareCanvas( canvas, demo );

  WellTrackDepthZoomTool zoomTool( &canvas );
  canvas.setTool( &zoomTool );

  const DepthDomain before = canvas.depthDomain();
  const double centerDepth = canvas.depthAt( QPointF( 150, 200 ) );

  // Plain click (press + release at the same spot): zoom in ×2 around the click.
  sendMouse( canvas.viewport(), QEvent::MouseButtonPress, QPointF( 150, 200 ) );
  sendMouse( canvas.viewport(), QEvent::MouseButtonRelease, QPointF( 150, 200 ) );

  const DepthDomain after = canvas.depthDomain();
  QVERIFY( std::abs( after.span() - before.span() / 2 ) < 1e-6 );
  QVERIFY( std::abs( after.depthAtFraction( 0.5 ) - centerDepth ) < 1.0 );
}

void TestCanvasTools::cursorToolSignals()
{
  DemoData demo;
  WellTrackCanvas canvas;
  prepareCanvas( canvas, demo );

  WellTrackCursorTool cursorTool( &canvas );
  canvas.setTool( &cursorTool );

  QSignalSpy depthSpy( &canvas, &WellTrackCanvas::cursorDepthChanged );
  QSignalSpy hoverSpy( &canvas, &WellTrackCanvas::sampleHovered );

  // Inside the content area (below the 40px header).
  sendMouse( canvas.viewport(), QEvent::MouseMove, QPointF( 150, 200 ), Qt::NoButton, Qt::NoButton );
  QVERIFY( depthSpy.count() >= 1 );
  QVERIFY( hoverSpy.count() >= 1 );
  QVERIFY( std::isfinite( depthSpy.last().at( 0 ).toDouble() ) );

  cursorTool.deactivate();  // clears crosshair, emits NaN depth
  QVERIFY( std::isnan( depthSpy.last().at( 0 ).toDouble() ) );
}

void TestCanvasTools::cursorToolHeaderIsNaN()
{
  DemoData demo;
  WellTrackCanvas canvas;
  prepareCanvas( canvas, demo );

  WellTrackCursorTool cursorTool( &canvas );
  canvas.setTool( &cursorTool );

  QSignalSpy depthSpy( &canvas, &WellTrackCanvas::cursorDepthChanged );
  // y=20 is inside the header band, outside depth space.
  sendMouse( canvas.viewport(), QEvent::MouseMove, QPointF( 150, 20 ), Qt::NoButton, Qt::NoButton );
  QVERIFY( depthSpy.count() >= 1 );
  QVERIFY( std::isnan( depthSpy.last().at( 0 ).toDouble() ) );
}

void TestCanvasTools::transientMidButtonPanSmoke()
{
  DemoData demo;
  WellTrackCanvas canvas;
  prepareCanvas( canvas, demo );

  // Middle-button drag activates QgsPlotCanvas's transient pan tool without
  // any tool set; must not crash and must pan.
  const DepthDomain before = canvas.depthDomain();
  sendMouse( canvas.viewport(), QEvent::MouseButtonPress, QPointF( 150, 100 ), Qt::MiddleButton,
             Qt::MiddleButton );
  sendMouse( canvas.viewport(), QEvent::MouseMove, QPointF( 150, 180 ), Qt::MiddleButton,
             Qt::MiddleButton );
  sendMouse( canvas.viewport(), QEvent::MouseButtonRelease, QPointF( 150, 180 ), Qt::MiddleButton );
  const DepthDomain after = canvas.depthDomain();
  QVERIFY( after.minDepth() != before.minDepth() );
}

void TestCanvasTools::toolSwitching()
{
  DemoData demo;
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
