/***************************************************************************
 * SPDX-License-Identifier: MIT
 *
 * Hit probes compute their x through the same axis mapping the renderer
 * uses, so tolerance math — not layout guesses — decides the verdict.
 ***************************************************************************/
#include "geoviz/qgis_welltrack/hit_testing.h"

#include <QtTest>

#include <cmath>
#include <vector>

using namespace geoviz::qgis_welltrack;

class TestHitTesting : public QObject
{
    Q_OBJECT
  private slots:
    void exactHitOnSample();
    void nearestWithinTolerance();
    void missBeyondTolerance();
    void multiTrackDisambiguation();
    void nanSamplesSkipped();
    void emptyModelNoHit();

  private:
    static std::shared_ptr<WellTrackModel> twoTrackModel( std::vector<double> &depths,
                                                          std::vector<double> &values );
};

std::shared_ptr<WellTrackModel> TestHitTesting::twoTrackModel( std::vector<double> &depths,
                                                               std::vector<double> &values )
{
  depths.clear();
  values.clear();
  for ( int i = 0; i < 100; ++i )
  {
    depths.push_back( 1000.0 + i * 1.0 );
    values.push_back( i % 2 == 0 ? 20.0 : -20.0 );
  }
  auto model = WellTrackModel::create();
  auto left = model->appendTrack( QStringLiteral( "Left" ) );
  left->axis.minimum = -50.0;
  left->axis.maximum = 50.0;
  CurveSpec curve;
  curve.id = 11;
  curve.label = QStringLiteral( "GR" );
  curve.data = makeDoubleView( depths.data(), values.data(), depths.size() );
  left->curves.push_back( curve );

  auto right = model->appendTrack( QStringLiteral( "Right" ) );
  right->axis.minimum = 0.0;
  right->axis.maximum = 100.0;
  CurveSpec curve2;
  curve2.id = 22;
  curve2.label = QStringLiteral( "RD" );
  curve2.data = makeDoubleView( depths.data(), values.data(), depths.size() );
  right->curves.push_back( curve2 );
  return model;
}

void TestHitTesting::exactHitOnSample()
{
  std::vector<double> depths, values;
  auto model = twoTrackModel( depths, values );
  const TrackLayoutResult layout = computeTrackLayout( *model, QRectF( 0, 0, 400, 500 ) );
  const DepthDomain domain = makeDomain( 1000.0, 1100.0 );

  // Sample 50: depth 1050, value +20 (even index).
  const TrackGeometry &left = layout.tracks[ 0 ];
  const double y = domain.yForDepth( 1050.0, left.contentRect );
  const double x = model->track( left.trackId )->axis.xForValue( 20.0, left.contentRect );
  const HitResult hit = hitTestNearestSample( *model, layout, domain, QPointF( x, y ), 10.0 );
  QVERIFY( hit.hit );
  QCOMPARE( hit.sampleIndex, qsizetype( 50 ) );
  QCOMPARE( hit.curveId, SeriesId( 11 ) );
  QCOMPARE( hit.depth, 1050.0 );
}

void TestHitTesting::nearestWithinTolerance()
{
  std::vector<double> depths, values;
  auto model = twoTrackModel( depths, values );
  const TrackLayoutResult layout = computeTrackLayout( *model, QRectF( 0, 0, 400, 500 ) );
  const DepthDomain domain = makeDomain( 1000.0, 1100.0 );
  const TrackGeometry &left = layout.tracks[ 0 ];
  const double y = domain.yForDepth( 1050.0, left.contentRect );
  const double x = model->track( left.trackId )->axis.xForValue( 20.0, left.contentRect );

  // 5 px below the sample — inside 10 px tolerance.
  const HitResult hit = hitTestNearestSample( *model, layout, domain, QPointF( x, y + 5.0 ), 10.0 );
  QVERIFY( hit.hit );
  QCOMPARE( hit.sampleIndex, qsizetype( 50 ) );
}

void TestHitTesting::missBeyondTolerance()
{
  std::vector<double> depths, values;
  auto model = twoTrackModel( depths, values );
  const TrackLayoutResult layout = computeTrackLayout( *model, QRectF( 0, 0, 400, 500 ) );
  const DepthDomain domain = makeDomain( 1000.0, 1100.0 );
  const HitResult miss =
    hitTestNearestSample( *model, layout, domain, QPointF( -500.0, 250.0 ), 10.0 );
  QVERIFY( !miss.hit );
}

void TestHitTesting::multiTrackDisambiguation()
{
  std::vector<double> depths, values;
  auto model = twoTrackModel( depths, values );
  const TrackLayoutResult layout = computeTrackLayout( *model, QRectF( 0, 0, 400, 500 ) );
  const DepthDomain domain = makeDomain( 1000.0, 1100.0 );

  const TrackGeometry &right = layout.tracks[ 1 ];
  const double y = domain.yForDepth( 1050.0, right.contentRect );
  const double x = model->track( right.trackId )->axis.xForValue( 20.0, right.contentRect );
  const HitResult hit = hitTestNearestSample( *model, layout, domain, QPointF( x, y ), 10.0 );
  QVERIFY( hit.hit );
  QCOMPARE( hit.curveId, SeriesId( 22 ) );
}

void TestHitTesting::nanSamplesSkipped()
{
  const double nan = std::numeric_limits<double>::quiet_NaN();
  std::vector<double> depths = { 1000.0, 1001.0, 1002.0 };
  std::vector<double> values = { nan, nan, 15.0 };
  auto model = WellTrackModel::create();
  auto track = model->appendTrack( QStringLiteral( "T" ) );
  track->axis.minimum = 0.0;
  track->axis.maximum = 30.0;
  CurveSpec curve;
  curve.id = 1;
  curve.data = makeDoubleView( depths.data(), values.data(), 3 );
  track->curves.push_back( curve );

  const TrackLayoutResult layout = computeTrackLayout( *model, QRectF( 0, 0, 300, 400 ) );
  const DepthDomain domain = makeDomain( 1000.0, 1002.0 );
  const TrackGeometry &g = layout.tracks[ 0 ];
  // Probe exactly at the finite sample (1002, 15) — NaN neighbors are skipped.
  const double y = domain.yForDepth( 1002.0, g.contentRect );
  const double x = track->axis.xForValue( 15.0, g.contentRect );
  const HitResult hit = hitTestNearestSample( *model, layout, domain, QPointF( x, y ), 6.0 );
  QVERIFY( hit.hit );
  QCOMPARE( hit.sampleIndex, qsizetype( 2 ) );
}

void TestHitTesting::emptyModelNoHit()
{
  auto model = WellTrackModel::create();
  const TrackLayoutResult layout = computeTrackLayout( *model, QRectF( 0, 0, 300, 400 ) );
  const HitResult hit =
    hitTestNearestSample( *model, layout, makeDomain( 0, 1 ), QPointF( 10, 10 ), 10.0 );
  QVERIFY( !hit.hit );
}

QTEST_APPLESS_MAIN( TestHitTesting )
#include "test_hit_testing.moc"
