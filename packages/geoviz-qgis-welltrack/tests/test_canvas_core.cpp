/***************************************************************************
 * SPDX-License-Identifier: MIT
 *
 * Canvas core lifecycle: construct/grab, model fit, no-op guard, resize
 * relayout, repeated open/close (leak/UAF smoke).
 ***************************************************************************/
#include "canvas_helpers.h"

class TestCanvasCore : public QObject
{
    Q_OBJECT
  private slots:
    void constructRenderGrab();
    void setModelFitsDepth();
    void noopDomainGuard();
    void resizeRelayout();
    void repeatedOpenClose();
};

using namespace geoviz::qgis_welltrack;
using geoviz::qgis_welltrack::test::DemoData;

void TestCanvasCore::constructRenderGrab()
{
  DemoData demo = DemoData::make();
  WellTrackCanvas canvas;
  canvas.setModel( demo.model );
  canvas.resize( 400, 500 );
  canvas.show();
  QVERIFY( QTest::qWaitForWindowExposed( &canvas ) );
  const QImage grabbed = canvas.grab().toImage();
  QVERIFY( !grabbed.isNull() );
  // Physical pixels scale with the device DPR (offscreen default is 1).
  QCOMPARE( grabbed.width(), qRound( 400 * canvas.devicePixelRatioF() ) );
}

void TestCanvasCore::setModelFitsDepth()
{
  DemoData demo = DemoData::make();
  WellTrackCanvas canvas;
  canvas.setModel( demo.model );
  const DepthDomain d = canvas.depthDomain();
  QVERIFY( d.isValid() );
  QCOMPARE( d.minDepth(), 1000.0 );
  QCOMPARE( d.maxDepth(), demo.depths.back() );
}

void TestCanvasCore::noopDomainGuard()
{
  DemoData demo = DemoData::make();
  WellTrackCanvas canvas;
  canvas.setModel( demo.model );
  canvas.resize( 300, 300 );

  QSignalSpy spy( &canvas, &WellTrackCanvas::depthRangeChanged );
  const DepthDomain current = canvas.depthDomain();
  canvas.setDepthDomain( current );  // identical → no-op
  QCOMPARE( spy.count(), 0 );

  DepthDomain wiggled = current;
  wiggled.shallow += 1e-12;  // below 1e-9 → still a no-op
  canvas.setDepthDomain( wiggled );
  QCOMPARE( spy.count(), 0 );

  wiggled.shallow += 1.0;  // real change
  canvas.setDepthDomain( wiggled );
  QCOMPARE( spy.count(), 1 );
}

void TestCanvasCore::resizeRelayout()
{
  DemoData demo = DemoData::make();
  WellTrackCanvas canvas;
  canvas.setModel( demo.model );
  canvas.resize( 300, 300 );
  canvas.show();
  QVERIFY( QTest::qWaitForWindowExposed( &canvas ) );
  canvas.resize( 600, 400 );
  canvas.refresh();
  QTest::qWait( 30 );  // let queued resizes settle
  QVERIFY( canvas.lastLayout().tracks.size() >= 1 );
  QVERIFY( canvas.lastLayout().contentArea.width() > 500.0 );
}

void TestCanvasCore::repeatedOpenClose()
{
  for ( int i = 0; i < 50; ++i )
  {
    DemoData demo = DemoData::make( 200 );
    WellTrackCanvas *canvas = new WellTrackCanvas;
    canvas->setModel( demo.model );
    canvas->resize( 320, 240 );
    canvas->show();
    QTest::qWait( 1 );
    delete canvas;
  }
  QVERIFY( true );  // reaching here means no crash / UAF
}

GEOVIZ_QWT_QGIS_APP_MAIN( TestCanvasCore )
#include "test_canvas_core.moc"
