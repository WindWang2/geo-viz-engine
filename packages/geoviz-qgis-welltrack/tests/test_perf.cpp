/***************************************************************************
 * SPDX-License-Identifier: MIT
 *
 * Performance evidence: 1e4/1e5/1e6 samples × 4 curves × 4 tracks.
 * Asserts only sanity bounds (no wall-clock CI flakes); prints a measured
 * table that goes into 13-final-build-evidence.md. No FPS claims.
 ***************************************************************************/
#include "canvas_helpers.h"
#include "geoviz/qgis_welltrack/welltrack_renderer.h"

#include <QImage>
#include <QPainter>

#include <cmath>
#include <random>
#include <vector>

using namespace geoviz::qgis_welltrack;
using geoviz::qgis_welltrack::test::DemoData;

class TestPerf : public QObject
{
    Q_OBJECT
  private slots:
    void envelopeBound();
    void renderScaleTable();
    void visibleSliceBigData();

  private:
    static std::shared_ptr<WellTrackModel> syntheticModel( int samples, int curves, int tracks,
                                                           std::vector<double> &depths,
                                                           std::vector<double> &values );
};

std::shared_ptr<WellTrackModel> TestPerf::syntheticModel( int samples, int curves, int tracks,
                                                          std::vector<double> &depths,
                                                          std::vector<double> &values )
{
  std::mt19937 rng( 20260924 );
  std::normal_distribution<double> walk( 0.0, 3.0 );

  depths.resize( samples );
  values.resize( samples );
  double d = 0.0;
  double v = 0.0;
  for ( int i = 0; i < samples; ++i )
  {
    d += 0.125;
    v += walk( rng );
    depths[ i ] = d;
    values[ i ] = std::sin( i / 500.0 ) * 30.0 + v;
  }

  auto model = WellTrackModel::create();
  model->appendTrack( QStringLiteral( "MD" ), TrackRole::DepthRuler );
  for ( int t = 0; t < tracks; ++t )
  {
    auto track = model->appendTrack( QStringLiteral( "T%1" ).arg( t ) );
    track->axis.minimum = -100.0;
    track->axis.maximum = 100.0;
    for ( int c = 0; c < curves; ++c )
    {
      CurveSpec spec;
      spec.id = static_cast<SeriesId>( t * 100 + c + 1 );
      spec.label = QStringLiteral( "C%1" ).arg( c );
      // All views share the same buffers (zero-copy admission).
      spec.data = makeDoubleView( depths.data(), values.data(), samples );
      track->curves.push_back( spec );
    }
  }
  return model;
}

void TestPerf::envelopeBound()
{
  std::vector<double> depths, values;
  auto model = syntheticModel( 100000, 4, 4, depths, values );

  const DepthDomain domain = makeDomain( depths.front(), depths.back() );
  const VisibleSlice slice = visibleSlice( model->tracks()[ 1 ]->curves[ 0 ].data,
                                            domain.minDepth(), domain.maxDepth() );
  std::vector<EnvelopeSample> envelope;
  buildEnvelope( model->tracks()[ 1 ]->curves[ 0 ].data, slice, 800, envelope );
  QVERIFY( envelope.size() <= 4 * 800 );  // ≤ 2 points/bin + breaks headroom
  qInfo( "1e5 samples → %zu envelope points (%lld raw in slice)", envelope.size(),
         static_cast<long long>( slice.size() ) );
}

void TestPerf::renderScaleTable()
{
  qInfo( "samples | prep µs | paint µs | envelope pts | raw in slices" );
  const int scales[ 3 ] = { 10000, 100000, 1000000 };
  for ( int n : scales )
  {
    std::vector<double> depths, values;
    auto model = syntheticModel( n, 4, 4, depths, values );

    QImage image( 900, 700, QImage::Format_ARGB32_Premultiplied );
    QPainter painter( &image );
    WellTrackRenderer renderer;
    RenderStats stats;
    renderer.render( &painter, QRectF( 0, 0, 900, 700 ), *model,
                     makeDomain( depths.front(), depths.back() ), &stats );
    painter.end();

    qInfo( "%7d | %7lld | %8lld | %13lld | %17lld", n, static_cast<long long>( stats.prepUsec ),
           static_cast<long long>( stats.paintUsec ),
           static_cast<long long>( stats.envelopePoints ),
           static_cast<long long>( stats.rawSamplesInSlices ) );

    // Sanity bounds only (CI can't flake on wall clock):
    QVERIFY( stats.envelopePoints <= 4 * 700 * 16 );
    // Whole 1e6 composite must complete headless well under the test budget.
    QVERIFY( stats.prepUsec + stats.paintUsec < 5'000'000 );

    // Second render of the same state should hit caches and be cheaper.
    QPainter painter2( &image );
    RenderStats stats2;
    renderer.render( &painter2, QRectF( 0, 0, 900, 700 ), *model,
                     makeDomain( depths.front(), depths.back() ), &stats2 );
    painter2.end();
    QVERIFY( stats2.prepUsec <= stats.prepUsec );
  }
}

void TestPerf::visibleSliceBigData()
{
  std::vector<double> depths, values;
  auto model = syntheticModel( 1000000, 1, 1, depths, values );
  const CurveSeriesView view = model->tracks()[ 1 ]->curves[ 0 ].data;

  // A narrow window in the middle of 1e6 samples must yield a small slice.
  const double mid = depths[ 500000 ];
  const VisibleSlice slice = visibleSlice( view, mid, mid + 125.0, 0.0 );
  QVERIFY( slice.size() <= 2000 );
  QCOMPARE( slice.size(), qsizetype( 1001 ) );  // 125 / 0.125 + 1
}

GEOVIZ_QWT_QGIS_APP_MAIN( TestPerf )
#include "test_perf.moc"
