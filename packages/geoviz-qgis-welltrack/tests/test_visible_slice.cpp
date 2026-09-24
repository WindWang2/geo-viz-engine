/***************************************************************************
 * SPDX-License-Identifier: MIT
 ***************************************************************************/
#include "geoviz/qgis_welltrack/curve_lod.h"

#include <QtTest>

#include <random>
#include <vector>

#include <cmath>
#include <limits>

using namespace geoviz::qgis_welltrack;

class TestVisibleSlice : public QObject
{
    Q_OBJECT
  private slots:
    void matchesBruteForce();
    void marginPresent();
    void emptyView();
    void singleSample();
    void rangeFullyOutside();
    void fullRange();
    void interpolation();
};

static bool sliceContains( const std::vector<double> &depths, const VisibleSlice &slice, double from,
                           double to )
{
  // Brute-force oracle: the slice must be exactly all samples within [from,to].
  qsizetype expectedBegin = depths.size();
  qsizetype expectedEnd = 0;
  for ( qsizetype i = 0; i < qsizetype( depths.size() ); ++i )
  {
    if ( depths[ i ] >= from )
    {
      expectedBegin = i;
      break;
    }
  }
  for ( qsizetype i = 0; i < qsizetype( depths.size() ); ++i )
  {
    if ( depths[ i ] > to )
    {
      expectedEnd = i;
      break;
    }
  }
  if ( expectedEnd == 0 )
    expectedEnd = depths.size();
  return slice.begin == expectedBegin && slice.end == expectedEnd;
}

void TestVisibleSlice::matchesBruteForce()
{
  std::mt19937 rng( 42 );
  std::uniform_real_distribution<double> depthGen( 0.0, 1000.0 );
  std::uniform_real_distribution<double> windowGen( 0.0, 900.0 );
  std::uniform_real_distribution<double> spanGen( 10.0, 200.0 );

  for ( int trial = 0; trial < 200; ++trial )
  {
    std::vector<double> depths( 500 );
    double d = 0.0;
    std::uniform_real_distribution<double> stepGen( 0.1, 2.5 );
    for ( auto &depth : depths )
    {
      depth = d;
      d += stepGen( rng );
    }
    const std::vector<double> values( depths.size(), 1.0 );
    const double from = windowGen( rng );
    const double to = from + spanGen( rng );
    const VisibleSlice slice =
      visibleSlice( makeDoubleView( depths.data(), values.data(), depths.size() ), from, to, 0.0 );
    QVERIFY2( sliceContains( depths, slice, from, to ),
              qPrintable( QStringLiteral( "trial %1 window [%2,%3]" ).arg( trial ).arg( from ).arg( to ) ) );
  }
}

void TestVisibleSlice::marginPresent()
{
  const std::vector<double> depths = { 0, 10, 20, 30, 40, 50 };
  const std::vector<double> values( 6, 0.0 );
  const VisibleSlice slice =
    visibleSlice( makeDoubleView( depths.data(), values.data(), 6 ), 20.0, 30.0, 0.05 );
  // ±5% of 10 = 0.5 → samples 20 and 30 plus anything within [19.5, 30.5].
  QVERIFY( slice.begin <= 2 );
  QVERIFY( slice.end >= 4 );
}

void TestVisibleSlice::emptyView()
{
  const VisibleSlice slice = visibleSlice( CurveSeriesView(), 0.0, 1.0 );
  QVERIFY( slice.isEmpty() );
}

void TestVisibleSlice::singleSample()
{
  const std::vector<double> depths = { 42.0 };
  const std::vector<double> values = { 1.0 };
  const VisibleSlice in =
    visibleSlice( makeDoubleView( depths.data(), values.data(), 1 ), 40.0, 44.0 );
  QCOMPARE( in.begin, qsizetype( 0 ) );
  QCOMPARE( in.end, qsizetype( 1 ) );

  const VisibleSlice out =
    visibleSlice( makeDoubleView( depths.data(), values.data(), 1 ), 50.0, 60.0 );
  QVERIFY( out.isEmpty() );
}

void TestVisibleSlice::rangeFullyOutside()
{
  const std::vector<double> depths = { 100, 200, 300 };
  const std::vector<double> values( 3, 0.0 );
  QVERIFY(
    visibleSlice( makeDoubleView( depths.data(), values.data(), 3 ), 500.0, 600.0 ).isEmpty() );
  QVERIFY(
    visibleSlice( makeDoubleView( depths.data(), values.data(), 3 ), 0.0, 10.0 ).isEmpty() );
}

void TestVisibleSlice::fullRange()
{
  const std::vector<double> depths = { 100, 200, 300 };
  const std::vector<double> values( 3, 0.0 );
  const VisibleSlice slice =
    visibleSlice( makeDoubleView( depths.data(), values.data(), 3 ), 100.0, 300.0 );
  QCOMPARE( slice.begin, qsizetype( 0 ) );
  QCOMPARE( slice.end, qsizetype( 3 ) );
}

void TestVisibleSlice::interpolation()
{
  const std::vector<double> depths = { 0.0, 1.0, 2.0, 3.0 };
  const std::vector<double> values = { 0.0, 10.0, 20.0, 30.0 };
  const CurveSeriesView v = makeDoubleView( depths.data(), values.data(), 4 );

  QCOMPARE( interpolateAtDepth( v, 1.5 ), 15.0 );
  QCOMPARE( interpolateAtDepth( v, 0.0 ), 0.0 );
  QCOMPARE( interpolateAtDepth( v, 3.0 ), 30.0 );
  QVERIFY( std::isnan( interpolateAtDepth( v, -0.5 ) ) );
  QVERIFY( std::isnan( interpolateAtDepth( v, 3.5 ) ) );

  const double nan = std::numeric_limits<double>::quiet_NaN();
  const std::vector<double> nanValues = { 0.0, nan, 20.0, 30.0 };
  const CurveSeriesView nv = makeDoubleView( depths.data(), nanValues.data(), 4 );
  QVERIFY( std::isnan( interpolateAtDepth( nv, 1.5 ) ) );  // bracketing NaN → no bridge
  QCOMPARE( interpolateAtDepth( nv, 2.5 ), 25.0 );
}

QTEST_APPLESS_MAIN( TestVisibleSlice )
#include "test_visible_slice.moc"
