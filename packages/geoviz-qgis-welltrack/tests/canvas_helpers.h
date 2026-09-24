/***************************************************************************
 * geoviz-qgis-welltrack — shared GUI test helpers
 *
 * SPDX-License-Identifier: MIT
 ***************************************************************************/
#ifndef GEOVIZ_QWT_TEST_CANVAS_HELPERS_H
#define GEOVIZ_QWT_TEST_CANVAS_HELPERS_H

#include "qgis_app_fixture.h"
#include "geoviz/qgis_welltrack/well_track_canvas.h"
#include "geoviz/qgis_welltrack/well_track_tools.h"

#include <QtTest>

#include <cmath>
#include <memory>
#include <vector>

using namespace geoviz::qgis_welltrack;

namespace geoviz::qgis_welltrack::test
{

struct DemoData
{
  std::vector<double> depths;
  std::vector<double> values;
  std::shared_ptr<WellTrackModel> model;

  static DemoData make( int samples = 2000, double top = 1000.0, double step = 0.5 )
  {
    DemoData d;
    for ( int i = 0; i < samples; ++i )
    {
      d.depths.push_back( top + i * step );
      d.values.push_back( std::sin( i / 60.0 ) * 40.0 );
    }
    d.model = WellTrackModel::create();
    d.model->appendTrack( QStringLiteral( "MD" ), TrackRole::DepthRuler );
    auto track = d.model->appendTrack( QStringLiteral( "GR" ) );
    track->axis.minimum = -50.0;
    track->axis.maximum = 50.0;
    CurveSpec curve;
    curve.id = 1;
    curve.label = QStringLiteral( "GR" );
    curve.style.lineColor = Qt::blue;
    curve.data = makeDoubleView( d.depths.data(), d.values.data(), d.depths.size() );
    track->curves.push_back( curve );
    return d;
  }
};

} // namespace geoviz::qgis_welltrack::test

#endif // GEOVIZ_QWT_TEST_CANVAS_HELPERS_H
