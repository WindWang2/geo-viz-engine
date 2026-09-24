/***************************************************************************
 * SPDX-License-Identifier: MIT
 *
 * Multi-canvas depth sync: propagation exact, no ping-pong, removal and
 * mid-sync destruction safety.
 ***************************************************************************/
#include "canvas_helpers.h"
#include "geoviz/qgis_welltrack/depth_synchronizer.h"

using namespace geoviz::qgis_welltrack;
using geoviz::qgis_welltrack::test::DemoData;

class TestSynchronizer : public QObject
{
    Q_OBJECT
  private slots:
    void twoCanvasSync();
    void noPingPong();
    void removeCanvasStopsSync();
    void destroyCanvasMidSync();
};

void TestSynchronizer::twoCanvasSync()
{
  DemoData demoA = DemoData::make();
  DemoData demoB = DemoData::make( 1500, 2000.0, 1.0 );

  WellTrackCanvas a;
  WellTrackCanvas b;
  a.setModel( demoA.model );
  b.setModel( demoB.model );
  a.resize( 300, 400 );
  b.resize( 300, 400 );

  WellTrackSynchronizer sync;
  sync.addCanvas( &a );
  sync.addCanvas( &b );

  QSignalSpy spyB( &b, &WellTrackCanvas::depthRangeChanged );
  a.zoomToDepth( 1100.0, 1200.0 );
  QTest::qWait( 10 );

  QCOMPARE( b.depthDomain().minDepth(), 1100.0 );
  QCOMPARE( b.depthDomain().maxDepth(), 1200.0 );
  QCOMPARE( spyB.count(), 1 );  // exactly once — B's echo is a no-op
}

void TestSynchronizer::noPingPong()
{
  DemoData demoA = DemoData::make();
  DemoData demoB = DemoData::make();

  WellTrackCanvas a;
  WellTrackCanvas b;
  a.setModel( demoA.model );
  b.setModel( demoB.model );

  QSignalSpy spyA( &a, &WellTrackCanvas::depthRangeChanged );
  QSignalSpy spyB( &b, &WellTrackCanvas::depthRangeChanged );

  WellTrackSynchronizer sync;
  sync.addCanvas( &a );
  sync.addCanvas( &b );

  a.panContentsBy( 0.0, 50.0 );
  QTest::qWait( 10 );
  QCOMPARE( spyA.count(), 1 );  // A emitted once for the gesture…
  QCOMPARE( spyB.count(), 1 );  // …B applied it once and its echo was a no-op.
}

void TestSynchronizer::removeCanvasStopsSync()
{
  DemoData demoA = DemoData::make();
  DemoData demoB = DemoData::make();

  WellTrackCanvas a;
  WellTrackCanvas b;
  a.setModel( demoA.model );
  b.setModel( demoB.model );

  WellTrackSynchronizer sync;
  sync.addCanvas( &a );
  sync.addCanvas( &b );
  sync.removeCanvas( &b );

  a.zoomToDepth( 1100.0, 1200.0 );
  QTest::qWait( 10 );
  QVERIFY( std::abs( b.depthDomain().minDepth() - 1100.0 ) > 1e-9 );  // untouched
}

void TestSynchronizer::destroyCanvasMidSync()
{
  DemoData demoA = DemoData::make();
  WellTrackCanvas a;
  a.setModel( demoA.model );

  WellTrackSynchronizer sync;
  {
    DemoData demoB = DemoData::make();
    auto *b = new WellTrackCanvas;
    b->setModel( demoB.model );
    sync.addCanvas( &a );
    sync.addCanvas( b );
    delete b;  // destroyed while registered
  }
  sync.removeCanvas( &a );
  QVERIFY( sync.isEmpty() );  // destroyed canvas auto-removed via QPointer
  a.zoomToDepth( 1100.0, 1200.0 );  // no crash
}

GEOVIZ_QWT_QGIS_APP_MAIN( TestSynchronizer )
#include "test_synchronizer.moc"
