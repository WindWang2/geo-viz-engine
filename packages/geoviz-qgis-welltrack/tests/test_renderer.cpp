/***************************************************************************
 * SPDX-License-Identifier: MIT
 *
 * Offscreen render probes: pixel-level assertions (colors present, NaN gap
 * not bridged, band fill present), stats sanity, SVG export, idempotent
 * re-render.
 ***************************************************************************/
#include "qgis_app_fixture.h"
#include "geoviz/qgis_welltrack/welltrack_renderer.h"

#include <QtTest>
#include <QFile>
#include <QImage>
#include <QPainter>
#include <QSvgGenerator>
#include <QTemporaryDir>

#include <cmath>
#include <vector>

using namespace geoviz::qgis_welltrack;

class TestRenderer : public QObject
{
    Q_OBJECT
  private slots:
    void rendersCurvePixels();
    void twoCurvesDistinctColors();
    void nanGapNotBridged();
    void bandFillRendered();
    void betweenSeriesFillRendered();
    void markerLineRendered();
    void statsPopulated();
    void svgExport();
    void idempotentRender();

  private:
    static std::shared_ptr<WellTrackModel> demoModel( std::vector<double> &depths,
                                                      std::vector<double> &values,
                                                      std::vector<double> &nanValues );
    static QImage renderToImage( const WellTrackModel &model, const DepthDomain &domain,
                                 const QRectF &rect, RenderStats *stats = nullptr );
};

std::shared_ptr<WellTrackModel> TestRenderer::demoModel( std::vector<double> &depths,
                                                         std::vector<double> &values,
                                                         std::vector<double> &nanValues )
{
  for ( int i = 0; i < 2000; ++i )
  {
    const double d = 1000.0 + i * 0.5;
    depths.push_back( d );
    const double v = std::sin( i / 80.0 ) * 40.0;
    values.push_back( v );
    nanValues.push_back( ( i >= 500 && i < 800 ) ? std::numeric_limits<double>::quiet_NaN() : v );
  }
  auto model = WellTrackModel::create();
  auto track = model->appendTrack( QStringLiteral( "GR" ) );
  track->axis.minimum = -50.0;
  track->axis.maximum = 50.0;
  CurveSpec curve;
  curve.id = 1;
  curve.label = QStringLiteral( "GR" );
  curve.style.lineColor = Qt::blue;
  curve.style.lineWidthF = 2.0;
  curve.data = makeDoubleView( depths.data(), values.data(), depths.size() );
  track->curves.push_back( curve );
  return model;
}

QImage TestRenderer::renderToImage( const WellTrackModel &model, const DepthDomain &domain,
                                    const QRectF &rect, RenderStats *stats )
{
  QImage image( rect.size().toSize(), QImage::Format_ARGB32_Premultiplied );
  QPainter painter( &image );
  WellTrackRenderer renderer;
  renderer.render( &painter, rect, model, domain, stats );
  painter.end();
  return image;
}

void TestRenderer::rendersCurvePixels()
{
  std::vector<double> depths, values, nanValues;
  auto model = demoModel( depths, values, nanValues );
  const DepthDomain domain = makeDomain( 1000.0, 2000.0 );
  const QImage image = renderToImage( *model, domain, QRectF( 0, 0, 300, 400 ) );

  int bluePixels = 0;
  for ( int y = 0; y < image.height(); ++y )
  {
    for ( int x = 0; x < image.width(); ++x )
    {
      const QColor c = image.pixelColor( x, y );
      if ( c.blue() > 150 && c.red() < 100 && c.green() < 100 )
        ++bluePixels;
    }
  }
  QVERIFY2( bluePixels > 50, qPrintable( QStringLiteral( "expected blue curve pixels, got %1" ).arg( bluePixels ) ) );
}

void TestRenderer::twoCurvesDistinctColors()
{
  std::vector<double> depths, values, nanValues;
  auto model = demoModel( depths, values, nanValues );
  auto track = model->track( 1 );
  CurveSpec second;
  second.id = 2;
  second.label = QStringLiteral( "RD" );
  second.style.lineColor = Qt::red;
  second.style.lineWidthF = 2.0;
  // Same buffers viewed at half count keeps sample memory shared.
  second.data = makeDoubleView( depths.data(), values.data(), depths.size() / 2 );
  track->curves.push_back( second );

  const QImage image = renderToImage( *model, makeDomain( 1000.0, 2000.0 ), QRectF( 0, 0, 300, 400 ) );
  int blue = 0, red = 0;
  for ( int y = 0; y < image.height(); ++y )
  {
    for ( int x = 0; x < image.width(); ++x )
    {
      const QColor c = image.pixelColor( x, y );
      if ( c.blue() > 150 && c.red() < 100 && c.green() < 100 )
        ++blue;
      if ( c.red() > 150 && c.blue() < 100 && c.green() < 100 )
        ++red;
    }
  }
  QVERIFY( blue > 30 );
  QVERIFY( red > 30 );
}

void TestRenderer::nanGapNotBridged()
{
  std::vector<double> depths, values, nanValues;
  auto model = demoModel( depths, values, nanValues );
  auto track = model->track( 1 );
  track->curves[ 0 ].data = makeDoubleView( depths.data(), nanValues.data(), depths.size() );

  const DepthDomain domain = makeDomain( 1000.0, 2000.0 );
  const QImage image = renderToImage( *model, domain, QRectF( 0, 0, 120, 400 ) );

  // The gap covers depths 1250..1400 → y band [ (1250-1000)/1000*contentH,
  // (1400-1000)/1000*contentH ] within the content area (header 40px).
  const QRectF content( 1, 41, 118, 358 );
  const double gapTop = content.top() + content.height() * 0.25 + 4;
  const double gapBottom = content.top() + content.height() * 0.40 - 4;
  int blueInGap = 0;
  for ( int y = static_cast<int>( gapTop ); y <= static_cast<int>( gapBottom ); ++y )
  {
    for ( int x = static_cast<int>( content.left() ); x < content.right(); ++x )
    {
      const QColor c = image.pixelColor( x, y );
      if ( c.blue() > 150 && c.red() < 100 )
        ++blueInGap;
    }
  }
  QCOMPARE( blueInGap, 0 );
}

void TestRenderer::bandFillRendered()
{
  std::vector<double> depths, values, nanValues;
  auto model = demoModel( depths, values, nanValues );
  auto track = model->track( 1 );
  DepthIntervalBand band;
  band.top = 1100.0;
  band.bottom = 1150.0;
  band.fill = QBrush( QColor( 255, 200, 0, 255 ) );
  band.label = QStringLiteral( "zone" );
  track->bands.push_back( band );

  const DepthDomain domain = makeDomain( 1000.0, 2000.0 );
  const QImage image = renderToImage( *model, domain, QRectF( 0, 0, 300, 400 ) );

  const QRectF content( 1, 41, 298, 358 );
  const double bandTop = content.top() + content.height() * 0.10 + 2;
  bool sawOrange = false;
  for ( int x = static_cast<int>( content.left() ) + 2; x < content.right() - 2; x += 5 )
  {
    const QColor c = image.pixelColor( x, static_cast<int>( bandTop ) );
    if ( c.red() > 230 && c.green() > 160 && c.blue() < 80 )
      sawOrange = true;
  }
  QVERIFY( sawOrange );
}

void TestRenderer::betweenSeriesFillRendered()
{
  std::vector<double> depths, values, nanValues;
  auto model = demoModel( depths, values, nanValues );
  auto track = model->track( 1 );

  // Second curve: same sine with an offset, fill between the two.
  std::vector<double> offsetValues;
  offsetValues.reserve( values.size() );
  for ( size_t i = 0; i < values.size(); ++i )
    offsetValues.push_back( values[ i ] + 25.0 );

  CurveSpec upper;
  upper.id = 2;
  upper.label = QStringLiteral( "UP" );
  upper.style.lineColor = Qt::darkGreen;
  upper.style.fill = FillMode::BetweenSeries;
  upper.style.fillColor = QColor( 255, 0, 255 );
  upper.style.fillOpacity = 0.9;
  upper.partnerId = 1;  // fill partner: the blue GR curve (id 1)
  upper.data = makeDoubleView( depths.data(), offsetValues.data(), depths.size() );
  track->curves.push_back( upper );

  const QImage image = renderToImage( *model, makeDomain( 1000.0, 2000.0 ), QRectF( 0, 0, 300, 400 ) );

  // Magenta-ish fill pixels (dominant R and B, low G) must exist between the lines.
  int magenta = 0;
  for ( int y = 0; y < image.height(); ++y )
    for ( int x = 0; x < image.width(); ++x )
    {
      const QColor c = image.pixelColor( x, y );
      if ( c.red() > 140 && c.blue() > 140 && c.green() < 110 )
        ++magenta;
    }
  QVERIFY2( magenta > 100, qPrintable( QStringLiteral( "between-series fill pixels: %1" ).arg( magenta ) ) );
}

void TestRenderer::markerLineRendered()
{
  std::vector<double> depths, values, nanValues;
  auto model = demoModel( depths, values, nanValues );
  auto track = model->track( 1 );
  DepthMarkerLine marker;
  marker.depth = 1500.0;
  marker.color = QColor( 255, 0, 0, 255 );
  marker.pen = Qt::SolidLine;
  marker.widthF = 3.0;
  marker.label = QStringLiteral( "TOP" );
  track->markers.push_back( marker );

  const QImage image = renderToImage( *model, makeDomain( 1000.0, 2000.0 ), QRectF( 0, 0, 300, 400 ) );

  const QRectF content( 1, 41, 298, 358 );
  const double markerY = content.top() + content.height() * 0.5;
  int redOnLine = 0;
  for ( int x = static_cast<int>( content.left() ); x < content.right(); x += 3 )
  {
    const QColor c = image.pixelColor( x, static_cast<int>( markerY ) );
    if ( c.red() > 180 && c.green() < 90 && c.blue() < 90 )
      ++redOnLine;
  }
  QVERIFY2( redOnLine > 40, qPrintable( QStringLiteral( "marker line pixels: %1" ).arg( redOnLine ) ) );
}

void TestRenderer::statsPopulated()
{
  std::vector<double> depths, values, nanValues;
  auto model = demoModel( depths, values, nanValues );
  RenderStats stats;
  renderToImage( *model, makeDomain( 1000.0, 2000.0 ), QRectF( 0, 0, 300, 400 ), &stats );
  QVERIFY( stats.rawSamplesInSlices > 1000 );
  QVERIFY( stats.envelopePoints > 0 );
  QVERIFY( stats.envelopePoints <= 4 * 400 );
  QVERIFY( stats.paintUsec >= 0 );
  QVERIFY( stats.prepUsec >= 0 );
}

void TestRenderer::svgExport()
{
  std::vector<double> depths, values, nanValues;
  auto model = demoModel( depths, values, nanValues );

  QTemporaryDir dir;
  const QString path = dir.filePath( QStringLiteral( "welltrack.svg" ) );
  {
    QSvgGenerator generator;
    generator.setFileName( path );
    generator.setSize( QSize( 300, 400 ) );
    generator.setViewBox( QRect( 0, 0, 300, 400 ) );
    QPainter painter( &generator );
    WellTrackRenderer renderer;
    renderer.render( &painter, QRectF( 0, 0, 300, 400 ), *model, makeDomain( 1000.0, 2000.0 ) );
    painter.end();
  }
  QFile file( path );
  QVERIFY( file.open( QIODevice::ReadOnly ) );
  const QByteArray svg = file.readAll();
  QVERIFY( svg.size() > 1000 );
  QVERIFY( svg.contains( "<path" ) || svg.contains( "<g" ) );
}

void TestRenderer::idempotentRender()
{
  std::vector<double> depths, values, nanValues;
  auto model = demoModel( depths, values, nanValues );
  const QImage a = renderToImage( *model, makeDomain( 1000.0, 2000.0 ), QRectF( 0, 0, 300, 400 ) );
  const QImage b = renderToImage( *model, makeDomain( 1000.0, 2000.0 ), QRectF( 0, 0, 300, 400 ) );
  QCOMPARE( a, b );
}

GEOVIZ_QWT_QGIS_APP_MAIN( TestRenderer )
#include "test_renderer.moc"
