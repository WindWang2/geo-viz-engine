/***************************************************************************
 * geoviz-qgis-welltrack — minimal host example
 *
 * SPDX-License-Identifier: MIT
 *
 * Interactive demo by default; `--offscreen out.png` renders one frame into
 * a PNG (QGIS application still required for symbol registries) and exits.
 *
 * Build/run:
 *   cmake -S packages/geoviz-qgis-welltrack -B build -DGEOVIZ_QWT_BUILD_EXAMPLES=ON
 *   cmake --build build --target welltrack_demo -j4
 *   ./build/welltrack_demo            # interactive: pan drag / wheel zoom /
 *                                     # marquee depth zoom / F=fit / C=cursor
 *   ./build/welltrack_demo --offscreen out.png
 ***************************************************************************/
#include "geoviz/qgis_welltrack/depth_synchronizer.h"
#include "geoviz/qgis_welltrack/well_track_canvas.h"
#include "geoviz/qgis_welltrack/well_track_tools.h"

#include <qgsapplication.h>

#include <QApplication>
#include <QImage>
#include <QKeyEvent>
#include <QPainter>
#include <QToolBar>
#include <QVBoxLayout>
#include <QWidget>

#include <cmath>
#include <random>
#include <vector>

using namespace geoviz::qgis_welltrack;

namespace
{

struct DemoWell
{
  std::vector<double> depths;
  std::vector<double> gr;
  std::vector<double> rho;
  std::shared_ptr<WellTrackModel> model;

  static DemoWell make()
  {
    std::mt19937 rng( 4 );
    std::normal_distribution<double> noise( 0.0, 3.0 );
    DemoWell w;
    double gr = 60.0;
    for ( int i = 0; i < 50000; ++i )
    {
      w.depths.push_back( 1000.0 + i * 0.1 );
      gr += noise( rng );
      gr = std::clamp( gr, 10.0, 150.0 );
      w.gr.push_back( gr );
      w.rho.push_back( 2.2 + std::sin( i / 700.0 ) * 0.35 + noise( rng ) * 0.02 );
    }
    w.model = WellTrackModel::create();
    w.model->appendTrack( QStringLiteral( "MD" ), TrackRole::DepthRuler );

    auto grTrack = w.model->appendTrack( QStringLiteral( "GR (API)" ) );
    grTrack->axis.minimum = 0.0;
    grTrack->axis.maximum = 150.0;
    CurveSpec grCurve;
    grCurve.id = 1;
    grCurve.label = QStringLiteral( "GR" );
    grCurve.style.lineColor = Qt::darkGreen;
    grCurve.style.lineWidthF = 1.2;
    grCurve.data = makeDoubleView( w.depths.data(), w.gr.data(), w.depths.size() );
    grTrack->curves.push_back( grCurve );

    DepthIntervalBand shale;
    shale.top = 1500.0;
    shale.bottom = 1800.0;
    shale.fill = QBrush( QColor( 160, 120, 90, 120 ) );
    shale.label = QStringLiteral( "band" );
    grTrack->bands.push_back( shale );

    DepthMarkerLine top;
    top.depth = 2000.0;
    top.label = QStringLiteral( "marker @2000" );
    grTrack->markers.push_back( top );

    auto rhoTrack = w.model->appendTrack( QStringLiteral( "RHOB (log)" ) );
    rhoTrack->axis.minimum = 1.9;
    rhoTrack->axis.maximum = 2.8;
    rhoTrack->axis.scale = ValueScale::Log10;
    CurveSpec rhoCurve;
    rhoCurve.id = 2;
    rhoCurve.label = QStringLiteral( "RHOB" );
    rhoCurve.style.lineColor = Qt::blue;
    rhoCurve.style.lineWidthF = 1.2;
    rhoCurve.style.fill = FillMode::ToBaseline;
    rhoCurve.style.fillBaseline = 2.2;
    rhoCurve.style.fillColor = QColor( 90, 140, 255 );
    rhoCurve.style.fillOpacity = 0.25;
    rhoCurve.data = makeDoubleView( w.depths.data(), w.rho.data(), w.depths.size() );
    rhoTrack->curves.push_back( rhoCurve );
    return w;
  }
};

class DemoWindow : public QWidget
{
    Q_OBJECT
  public:
    explicit DemoWindow( QWidget *parent = nullptr )
      : QWidget( parent ), mCanvas( new WellTrackCanvas( this ) )
    {
      mWell = DemoWell::make();
      mCanvas->setModel( mWell.model );
      mCanvas->fitDepth();

      auto *zoomTool = new WellTrackDepthZoomTool( mCanvas );
      auto *cursorTool = new WellTrackCursorTool( mCanvas );
      mCanvas->setTool( cursorTool );

      auto *layout = new QVBoxLayout( this );
      auto *bar = new QToolBar;
      bar->addAction( QStringLiteral( "Pan: drag — Zoom: wheel / marquee (zoom tool)" ) );
      bar->addAction( QStringLiteral( "Zoom tool" ), this, [ this, zoomTool ] { mCanvas->setTool( zoomTool ); } );
      bar->addAction( QStringLiteral( "Cursor tool" ), this, [ this, cursorTool ] { mCanvas->setTool( cursorTool ); } );
      bar->addAction( QStringLiteral( "Fit (F)" ), this, [ this ] { mCanvas->fitDepth(); } );
      layout->addWidget( bar );
      layout->addWidget( mCanvas );
      setLayout( layout );
      resize( 900, 700 );
      setWindowTitle( QStringLiteral( "geoviz-qgis-welltrack demo" ) );
    }

  protected:
    void keyPressEvent( QKeyEvent *event ) override
    {
      if ( event->key() == Qt::Key_F )
        mCanvas->fitDepth();
      QWidget::keyPressEvent( event );
    }

  private:
    DemoWell mWell;
    WellTrackCanvas *mCanvas = nullptr;
};

int runOffscreen( const QString &outPath )
{
  DemoWell well;
  QImage image( 900, 700, QImage::Format_ARGB32_Premultiplied );
  QPainter painter( &image );
  WellTrackRenderer renderer;
  RenderStats stats;
  renderer.render( &painter, QRectF( 0, 0, 900, 700 ), *well.model,
                   makeDomain( well.depths.front(), well.depths.back() ), &stats );
  painter.end();
  const bool saved = image.save( outPath );
  qInfo( "offscreen render: %s — prep %lld µs, paint %lld µs, envelope %lld pts",
         saved ? qPrintable( outPath ) : "SAVE FAILED",
         static_cast<long long>( stats.prepUsec ), static_cast<long long>( stats.paintUsec ),
         static_cast<long long>( stats.envelopePoints ) );
  return saved ? 0 : 1;
}

} // namespace

int main( int argc, char **argv )
{
  QgsApplication app( argc, argv, true );
  QgsApplication::setPrefixPath( QString::fromLocal8Bit( qgetenv( "QT_QGIS_PREFIX_DIR" ) ), true );
  QgsApplication::init();
  QgsApplication::initQgis();

  int result = 0;
  const QStringList args = app.arguments();
  const int offscreenIndex = args.indexOf( QStringLiteral( "--offscreen" ) );
  if ( offscreenIndex >= 0 && offscreenIndex + 1 < args.size() )
  {
    result = runOffscreen( args.at( offscreenIndex + 1 ) );
  }
  else
  {
    DemoWindow window;
    window.show();
    result = app.exec();
  }

  QgsApplication::exitQgis();
  return result;
}

#include "main.moc"
