/***************************************************************************
 * SPDX-License-Identifier: MIT
 ***************************************************************************/
#include "geoviz/qgis_welltrack/axis_spec.h"

#include <QtTest>

#include <cmath>
#include <limits>

using namespace geoviz::qgis_welltrack;

class TestAxisTransform : public QObject
{
    Q_OBJECT
  private slots:
    void linearRoundTrip();
    void logMapping();
    void logFloorClamp();
    void degenerateRange();
    void nanHandling();
};

void TestAxisTransform::linearRoundTrip()
{
  TrackAxisSpec axis;
  axis.minimum = 0.0;
  axis.maximum = 200.0;
  const QRectF r( 20, 0, 160, 100 );
  QCOMPARE( axis.xForValue( 0.0, r ), r.left() );
  QCOMPARE( axis.xForValue( 200.0, r ), r.right() );
  QCOMPARE( axis.xForValue( 100.0, r ), r.left() + r.width() / 2 );
  QVERIFY( std::abs( axis.valueForX( axis.xForValue( 77.0, r ), r ) - 77.0 ) < 1e-9 );
}

void TestAxisTransform::logMapping()
{
  TrackAxisSpec axis;
  axis.minimum = 0.2;
  axis.maximum = 2000.0;
  axis.scale = ValueScale::Log10;
  const QRectF r( 0, 0, 300, 10 );
  QCOMPARE( axis.xForValue( 0.2, r ), r.left() );
  QCOMPARE( axis.xForValue( 2000.0, r ), r.right() );
  // One decade above the floor is 1/4 of the span (0.2 → 2 → 20 → 200 → 2000: 4 decades).
  QCOMPARE( axis.xForValue( 2.0, r ), r.left() + r.width() * 0.25 );
}

void TestAxisTransform::logFloorClamp()
{
  TrackAxisSpec axis;
  axis.minimum = 1e-10;
  axis.maximum = 100.0;
  axis.scale = ValueScale::Log10;
  const QRectF r( 0, 0, 100, 10 );
  // Zero and negative values clamp to the floor, never log() them.
  QCOMPARE( axis.xForValue( 0.0, r ), axis.xForValue( axis.logFloor, r ) );
  QCOMPARE( axis.xForValue( -5.0, r ), axis.xForValue( axis.logFloor, r ) );
  QVERIFY( axis.isValid() );
}

void TestAxisTransform::degenerateRange()
{
  TrackAxisSpec axis;
  axis.minimum = 50.0;
  axis.maximum = 50.0;
  QVERIFY( !axis.isValid() );
  const QRectF r( 0, 0, 100, 10 );
  QCOMPARE( axis.xForValue( 50.0, r ), r.center().x() );
}

void TestAxisTransform::nanHandling()
{
  TrackAxisSpec axis;
  axis.minimum = 0.0;
  axis.maximum = 1.0;
  const QRectF r( 0, 0, 100, 10 );
  QVERIFY( std::isnan( axis.xForValue( std::numeric_limits<double>::quiet_NaN(), r ) ) );
}

QTEST_APPLESS_MAIN( TestAxisTransform )
#include "test_axis_transform.moc"
