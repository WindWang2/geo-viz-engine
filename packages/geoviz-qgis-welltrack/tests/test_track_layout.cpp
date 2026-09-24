/***************************************************************************
 * SPDX-License-Identifier: MIT
 ***************************************************************************/
#include "geoviz/qgis_welltrack/track_layout.h"

#include <QtTest>

using namespace geoviz::qgis_welltrack;

class TestTrackLayout : public QObject
{
    Q_OBJECT
  private slots:
    void widthsSumToTarget();
    void hiddenTracksExcluded();
    void depthRulerFixedWidth();
    void headersAndContent();
    void trackAtXBoundaries();
    void overflowShrinksFixed();
    void emptyModel();
};

void TestTrackLayout::widthsSumToTarget()
{
  auto model = WellTrackModel::create();
  model->appendTrack( QStringLiteral( "A" ) );  // stretch
  model->appendTrack( QStringLiteral( "B" ) );  // stretch

  const QRectF target( 0, 0, 400, 600 );
  const TrackLayoutOptions options;  // separator 1, margins 1+1
  const TrackLayoutResult r = computeTrackLayout( *model, target, options );
  QCOMPARE( r.tracks.size(), size_t( 2 ) );

  const double expected = target.width() - options.outerMargins.left() - options.outerMargins.right()
                          - 1 * options.separatorWidth;
  const double actual = r.tracks[ 0 ].columnRect.width() + r.tracks[ 1 ].columnRect.width();
  QVERIFY( std::abs( actual - expected ) < 1e-6 );
  QCOMPARE( r.tracks[ 0 ].columnRect.right() + options.separatorWidth,
            r.tracks[ 1 ].columnRect.left() );
}

void TestTrackLayout::hiddenTracksExcluded()
{
  auto model = WellTrackModel::create();
  auto a = model->appendTrack( QStringLiteral( "A" ) );
  model->appendTrack( QStringLiteral( "B" ) );
  a->visible = false;

  const TrackLayoutResult r = computeTrackLayout( *model, QRectF( 0, 0, 300, 400 ) );
  QCOMPARE( r.tracks.size(), size_t( 1 ) );
  QCOMPARE( r.tracks[ 0 ].trackId, a->id + 1 );  // B got id after A
}

void TestTrackLayout::depthRulerFixedWidth()
{
  auto model = WellTrackModel::create();
  model->appendTrack( QStringLiteral( "MD" ), TrackRole::DepthRuler );
  model->appendTrack( QStringLiteral( "GR" ) );

  TrackLayoutOptions options;
  options.depthRulerWidth = 80;
  const TrackLayoutResult r = computeTrackLayout( *model, QRectF( 0, 0, 400, 500 ), options );
  QCOMPARE( r.tracks.size(), size_t( 2 ) );
  QCOMPARE( r.tracks[ 0 ].role, TrackRole::DepthRuler );
  QVERIFY( std::abs( r.tracks[ 0 ].columnRect.width() - 80.0 ) < 1e-6 );
  QVERIFY( r.tracks[ 1 ].columnRect.width() > 300.0 );  // stretch gets the rest
}

void TestTrackLayout::headersAndContent()
{
  auto model = WellTrackModel::create();
  model->appendTrack( QStringLiteral( "A" ) );
  TrackLayoutOptions options;
  options.headerHeight = 42;
  const TrackLayoutResult r = computeTrackLayout( *model, QRectF( 0, 0, 200, 500 ), options );
  const TrackGeometry &g = r.tracks[ 0 ];
  QCOMPARE( g.headerRect.height(), 42.0 );
  QCOMPARE( g.contentRect.top(), g.headerRect.bottom() );
  QCOMPARE( g.contentRect.height() + g.headerRect.height(),
            500.0 - options.outerMargins.top() - options.outerMargins.bottom() );
}

void TestTrackLayout::trackAtXBoundaries()
{
  auto model = WellTrackModel::create();
  model->appendTrack( QStringLiteral( "A" ) );
  model->appendTrack( QStringLiteral( "B" ) );
  const TrackLayoutResult r = computeTrackLayout( *model, QRectF( 0, 0, 200, 100 ) );
  QCOMPARE( r.trackAtX( r.tracks[ 0 ].columnRect.center().x() ), 0 );
  QCOMPARE( r.trackAtX( r.tracks[ 1 ].columnRect.center().x() ), 1 );
  QCOMPARE( r.trackAtX( -5.0 ), -1 );
  QCOMPARE( r.trackAtX( 10000.0 ), -1 );
}

void TestTrackLayout::overflowShrinksFixed()
{
  auto model = WellTrackModel::create();
  auto a = model->appendTrack( QStringLiteral( "A" ) );
  auto b = model->appendTrack( QStringLiteral( "B" ) );
  a->fixedWidth = 300.0;
  b->fixedWidth = 300.0;  // 600 into ~200 px target

  const TrackLayoutResult r = computeTrackLayout( *model, QRectF( 0, 0, 200, 100 ) );
  QCOMPARE( r.tracks.size(), size_t( 2 ) );
  QVERIFY( r.tracks[ 0 ].columnRect.width() < 150.0 );
  QVERIFY( r.tracks[ 1 ].columnRect.width() > 0.0 );
}

void TestTrackLayout::emptyModel()
{
  auto model = WellTrackModel::create();
  const TrackLayoutResult r = computeTrackLayout( *model, QRectF( 0, 0, 200, 100 ) );
  QVERIFY( r.tracks.empty() );
}

QTEST_APPLESS_MAIN( TestTrackLayout )
#include "test_track_layout.moc"
