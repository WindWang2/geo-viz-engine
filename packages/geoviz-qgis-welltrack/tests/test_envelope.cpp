/***************************************************************************
 * SPDX-License-Identifier: MIT
 *
 * LOD oracle: per-bin min/max must equal brute force (extrema preservation),
 * emitted in original index order, with break markers on bins that contain
 * non-finite samples. Mirrors the geoviz_well_log downsample contract.
 ***************************************************************************/
#include "geoviz/qgis_welltrack/curve_lod.h"

#include <QtTest>

#include <algorithm>
#include <cmath>
#include <limits>
#include <random>
#include <vector>

using namespace geoviz::qgis_welltrack;

class TestEnvelope : public QObject
{
    Q_OBJECT
  private slots:
    void extremaPreservedRandomWalk();
    void indexOrderEmission();
    void nanBreakNoBridging();
    void smallSlicePassThrough();
    void binsExceedSamples();
    void emptySlice();
    void globalExtremaAlwaysPresent();

  private:
    struct Oracle
    {
      std::vector<double> depths;
      std::vector<double> values;
    };
    static Oracle makeRandomWalk( int n, unsigned seed );
};

TestEnvelope::Oracle TestEnvelope::makeRandomWalk( int n, unsigned seed )
{
  std::mt19937 rng( seed );
  std::uniform_real_distribution<double> step( 0.05, 1.0 );
  std::normal_distribution<double> walk( 0.0, 5.0 );
  Oracle o;
  o.depths.resize( n );
  o.values.resize( n );
  double d = 0.0;
  for ( int i = 0; i < n; ++i )
  {
    d += step( rng );
    o.depths[ i ] = d;
    o.values[ i ] = ( i == 0 ? 0.0 : o.values[ i - 1 ] ) + walk( rng );
  }
  return o;
}

void TestEnvelope::extremaPreservedRandomWalk()
{
  const int n = 5000;
  const Oracle o = makeRandomWalk( n, 7 );
  const CurveSeriesView v = makeDoubleView( o.depths.data(), o.values.data(), n );
  const VisibleSlice slice = visibleSlice( v, o.depths.front(), o.depths.back(), 0.0 );
  const int bins = 100;

  std::vector<EnvelopeSample> envelope;
  buildEnvelope( v, slice, bins, envelope );
  QVERIFY( !envelope.empty() );

  // Brute force per-bin min/max.
  const double d0 = o.depths[ slice.begin ];
  const double d1 = o.depths[ slice.end - 1 ];
  const double span = d1 - d0;
  for ( int b = 0; b < bins; ++b )
  {
    double binMin = std::numeric_limits<double>::infinity();
    double binMax = -std::numeric_limits<double>::infinity();
    for ( qsizetype i = slice.begin; i < slice.end; ++i )
    {
      const int bin = std::clamp<int>(
        static_cast<int>( ( o.depths[ i ] - d0 ) / span * bins ), 0, bins - 1 );
      if ( bin != b || !std::isfinite( o.values[ i ] ) )
        continue;
      binMin = std::min( binMin, o.values[ i ] );
      binMax = std::max( binMax, o.values[ i ] );
    }
    if ( binMin > binMax )
      continue;  // empty bin

    // All envelope points inside this bin must stay within [binMin, binMax]…
    bool sawMin = false, sawMax = false;
    for ( const EnvelopeSample &s : envelope )
    {
      const int bin = std::clamp<int>(
        static_cast<int>( ( s.depth - d0 ) / span * bins ), 0, bins - 1 );
      if ( bin != b )
        continue;
      QVERIFY( s.value >= binMin - 1e-12 );
      QVERIFY( s.value <= binMax + 1e-12 );
      if ( std::abs( s.value - binMin ) < 1e-12 )
        sawMin = true;
      if ( std::abs( s.value - binMax ) < 1e-12 )
        sawMax = true;
    }
    // …and the bin's exact extrema must be present (no decimation drift).
    QVERIFY2( sawMin, qPrintable( QStringLiteral( "bin %1 min missing" ).arg( b ) ) );
    QVERIFY2( sawMax, qPrintable( QStringLiteral( "bin %1 max missing" ).arg( b ) ) );
  }
}

void TestEnvelope::indexOrderEmission()
{
  // min after max in sample order → max emitted first.
  const std::vector<double> depths = { 0.0, 0.1, 0.2, 0.3 };
  const std::vector<double> values = { 5.0, -1.0, 9.0, 4.0 };
  const CurveSeriesView v = makeDoubleView( depths.data(), values.data(), 4 );
  std::vector<EnvelopeSample> envelope;
  buildEnvelope( v, VisibleSlice{ 0, 4 }, 1, envelope );
  // Single bin holds all samples; min=-1 (idx1), max=9 (idx2) → min first.
  QCOMPARE( envelope.size(), size_t( 2 ) );
  QCOMPARE( envelope[ 0 ].value, -1.0 );
  QCOMPARE( envelope[ 1 ].value, 9.0 );
}

void TestEnvelope::nanBreakNoBridging()
{
  const double nan = std::numeric_limits<double>::quiet_NaN();
  std::vector<double> depths;
  std::vector<double> values;
  for ( int i = 0; i < 2000; ++i )
  {
    depths.push_back( double( i ) );
    values.push_back( ( i >= 900 && i < 1000 ) ? nan : std::sin( double( i ) / 100.0 ) );
  }
  const CurveSeriesView v = makeDoubleView( depths.data(), values.data(), 2000 );
  std::vector<EnvelopeSample> envelope;
  buildEnvelope( v, VisibleSlice{ 0, 2000 }, 100, envelope );
  QVERIFY( envelope.size() > 10 );

  // No emitted value may be NaN, and at least one break must exist after the
  // NaN region begins and before it ends (the gap bins).
  bool sawBreakInNaNRegion = false;
  for ( const EnvelopeSample &s : envelope )
  {
    QVERIFY( std::isfinite( s.value ) );
    if ( s.breakAfter && s.depth > 850.0 && s.depth < 1050.0 )
      sawBreakInNaNRegion = true;
  }
  QVERIFY( sawBreakInNaNRegion );

  // Extrema outside the gap survive.
  double envMin = std::numeric_limits<double>::infinity();
  double envMax = -std::numeric_limits<double>::infinity();
  for ( const EnvelopeSample &s : envelope )
  {
    envMin = std::min( envMin, s.value );
    envMax = std::max( envMax, s.value );
  }
  double refMin = std::numeric_limits<double>::infinity();
  double refMax = -std::numeric_limits<double>::infinity();
  for ( int i = 0; i < 2000; ++i )
  {
    if ( !std::isfinite( values[ i ] ) )
      continue;
    refMin = std::min( refMin, values[ i ] );
    refMax = std::max( refMax, values[ i ] );
  }
  QCOMPARE( envMin, refMin );
  QCOMPARE( envMax, refMax );
}

void TestEnvelope::smallSlicePassThrough()
{
  const std::vector<double> depths = { 0.0, 1.0, 2.0, 3.0, 4.0 };
  const std::vector<double> values = { 1.0, 5.0, -5.0, 3.0, 2.0 };
  const CurveSeriesView v = makeDoubleView( depths.data(), values.data(), 5 );
  std::vector<EnvelopeSample> envelope;
  buildEnvelope( v, VisibleSlice{ 0, 5 }, 4, envelope );  // 5 <= max(8, 64)
  QCOMPARE( envelope.size(), size_t( 5 ) );
  for ( size_t i = 0; i < envelope.size(); ++i )
    QCOMPARE( envelope[ i ].value, values[ i ] );
}

void TestEnvelope::binsExceedSamples()
{
  const std::vector<double> depths = { 0.0, 1.0, 2.0, 3.0 };
  const std::vector<double> values = { 1.0, 9.0, -3.0, 4.0 };
  const CurveSeriesView v = makeDoubleView( depths.data(), values.data(), 4 );
  std::vector<EnvelopeSample> envelope;
  buildEnvelope( v, VisibleSlice{ 0, 4 }, 64, envelope );
  // Each populated bin emits exactly one point (single sample per bin).
  QCOMPARE( envelope.size(), size_t( 4 ) );
}

void TestEnvelope::emptySlice()
{
  const std::vector<double> depths = { 0.0, 1.0 };
  const std::vector<double> values = { 1.0, 2.0 };
  const CurveSeriesView v = makeDoubleView( depths.data(), values.data(), 2 );
  std::vector<EnvelopeSample> envelope;
  envelope.push_back( EnvelopeSample{} );  // stale contents must be cleared
  buildEnvelope( v, VisibleSlice{ 1, 1 }, 10, envelope );
  QVERIFY( envelope.empty() );
}

void TestEnvelope::globalExtremaAlwaysPresent()
{
  // Spike data: one extreme excursion per bin-pair must never be dropped.
  const int n = 10000;
  std::vector<double> depths( n );
  std::vector<double> values( n );
  std::mt19937 rng( 99 );
  std::uniform_real_distribution<double> spike( -1000.0, 1000.0 );
  double globalMin = std::numeric_limits<double>::infinity();
  double globalMax = -std::numeric_limits<double>::infinity();
  for ( int i = 0; i < n; ++i )
  {
    depths[ i ] = double( i );
    values[ i ] = ( i % 97 == 0 ) ? spike( rng ) : std::sin( double( i ) / 50.0 );
    globalMin = std::min( globalMin, values[ i ] );
    globalMax = std::max( globalMax, values[ i ] );
  }
  const CurveSeriesView v = makeDoubleView( depths.data(), values.data(), n );
  std::vector<EnvelopeSample> envelope;
  buildEnvelope( v, VisibleSlice{ 0, n }, 200, envelope );
  double envMin = std::numeric_limits<double>::infinity();
  double envMax = -std::numeric_limits<double>::infinity();
  for ( const EnvelopeSample &s : envelope )
  {
    envMin = std::min( envMin, s.value );
    envMax = std::max( envMax, s.value );
  }
  QCOMPARE( envMin, globalMin );
  QCOMPARE( envMax, globalMax );
}

QTEST_APPLESS_MAIN( TestEnvelope )
#include "test_envelope.moc"
