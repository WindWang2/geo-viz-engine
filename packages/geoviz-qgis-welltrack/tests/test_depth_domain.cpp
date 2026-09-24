/***************************************************************************
 * SPDX-License-Identifier: MIT
 ***************************************************************************/
#include "geoviz/qgis_welltrack/depth_domain.h"

#include <QtTest>

#include <cmath>

using namespace geoviz::qgis_welltrack;

class TestDepthDomain : public QObject
{
    Q_OBJECT
  private slots:
    void yDepthRoundTrip();
    void orientationUp();
    void degenerateDomain();
    void outsideRange();
    void clamping();
    void makeDomainNormalizes();
};

void TestDepthDomain::yDepthRoundTrip()
{
  const QRectF rect( 10, 100, 50, 400 );
  DepthDomain d = makeDomain( 1000.0, 2000.0 );  // IncreasingDown
  QVERIFY( d.isValid() );

  QCOMPARE( d.yForDepth( 1000.0, rect ), rect.top() );
  QCOMPARE( d.yForDepth( 2000.0, rect ), rect.bottom() );
  QCOMPARE( d.yForDepth( 1500.0, rect ), rect.top() + rect.height() / 2 );

  QCOMPARE( d.depthAtY( rect.top(), rect ), 1000.0 );
  QCOMPARE( d.depthAtY( rect.bottom(), rect ), 2000.0 );
  QCOMPARE( d.depthAtY( rect.top() + rect.height() / 2, rect ), 1500.0 );

  // Round-trip a few arbitrary depths.
  for ( double depth = 1000.0; depth <= 2000.0; depth += 137.5 )
  {
    const double y = d.yForDepth( depth, rect );
    QVERIFY( std::abs( d.depthAtY( y, rect ) - depth ) < 1e-9 );
  }
}

void TestDepthDomain::orientationUp()
{
  const QRectF rect( 0, 0, 10, 300 );
  DepthDomain d = makeDomain( 1000.0, 2000.0, DepthOrientation::IncreasingUp );
  // Larger depth renders at the top.
  QCOMPARE( d.yForDepth( 2000.0, rect ), rect.top() );
  QCOMPARE( d.yForDepth( 1000.0, rect ), rect.bottom() );
  QCOMPARE( d.depthAtY( rect.top(), rect ), 2000.0 );
}

void TestDepthDomain::degenerateDomain()
{
  DepthDomain d;
  d.shallow = 5.0;
  d.deep = 5.0;
  QVERIFY( !d.isValid() );
  QVERIFY( std::isnan( d.normalize( 6.0 ) ) );

  // Zero-height rect is a caller error; must not divide by zero into UB
  // (returns NaN through depthAtFraction's isValid guard first).
  const QRectF rect( 0, 0, 10, 0 );
  QVERIFY( std::isnan( d.depthAtY( 3.0, rect ) ) );
}

void TestDepthDomain::outsideRange()
{
  const QRectF rect( 0, 0, 100, 100 );
  DepthDomain d = makeDomain( 0.0, 100.0 );
  QVERIFY( d.normalize( -10.0 ) < 0.0 );
  QVERIFY( d.normalize( 110.0 ) > 1.0 );
  QVERIFY( d.yForDepth( 110.0, rect ) > rect.bottom() );
  QVERIFY( std::isnan( d.normalize( std::numeric_limits<double>::quiet_NaN() ) ) );
}

void TestDepthDomain::clamping()
{
  DepthDomain d = makeDomain( 0.0, 100.0 );
  const DepthDomain c = d.clampedTo( 50.0, 200.0 );
  QVERIFY( c.minDepth() >= 50.0 - 1e-9 );
  QVERIFY( c.maxDepth() <= 200.0 + 1e-9 );

  // Window wider than full extent collapses to the extent.
  const DepthDomain e = d.clampedTo( 10.0, 20.0 );
  QCOMPARE( e.minDepth(), 10.0 );
  QCOMPARE( e.maxDepth(), 20.0 );
}

void TestDepthDomain::makeDomainNormalizes()
{
  const DepthDomain d = makeDomain( 200.0, 100.0 );  // reversed edges
  QCOMPARE( d.shallow, 100.0 );
  QCOMPARE( d.deep, 200.0 );
}

QTEST_APPLESS_MAIN( TestDepthDomain )
#include "test_depth_domain.moc"
