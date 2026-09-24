/***************************************************************************
 * geoviz-qgis-welltrack — QgsApplication test fixture
 *
 * SPDX-License-Identifier: MIT
 *
 * Process-wide exactly-once QgsApplication bootstrap (recipe mirrors
 * paleo-workbench native/qgis_render_bridge): offscreen platform,
 * optional prefix from QT_QGIS_PREFIX_DIR, init()+initQgis().
 ***************************************************************************/
#ifndef GEOVIZ_QWT_QGIS_APP_FIXTURE_H
#define GEOVIZ_QWT_QGIS_APP_FIXTURE_H

#include <qgsapplication.h>

#include <QtTest>

namespace geoviz::qgis_welltrack::test
{

inline int runAppTests( int argc, char **argv, QObject &testObject )
{
  QgsApplication app( argc, argv, false );
  const QByteArray prefix = qgetenv( "QT_QGIS_PREFIX_DIR" );
  if ( !prefix.isEmpty() )
    QgsApplication::setPrefixPath( QString::fromLocal8Bit( prefix ), true );
  QgsApplication::init();
  QgsApplication::initQgis();

  const int result = QTest::qExec( &testObject, argc, argv );

  QgsApplication::exitQgis();
  return result;
}

} // namespace geoviz::qgis_welltrack::test

//! main() for tests that need QGIS application state.
#define GEOVIZ_QWT_QGIS_APP_MAIN( TestObject )                 \
  int main( int argc, char **argv )                            \
  {                                                            \
    TestObject tc;                                             \
    return geoviz::qgis_welltrack::test::runAppTests( argc, argv, tc ); \
  }

#endif // GEOVIZ_QWT_QGIS_APP_FIXTURE_H
