/***************************************************************************
 * SPDX-License-Identifier: MIT
 ***************************************************************************/
#include "geoviz/qgis_welltrack/curve_data.h"

#include <QtTest>

#include <cmath>
#include <vector>

using namespace geoviz::qgis_welltrack;

class TestCurveView : public QObject
{
    Q_OBJECT
  private slots:
    void packedDoubleView();
    void float32View();
    void stridedMemberView();
    void emptyView();
    void monotonicValidation();
};

void TestCurveView::packedDoubleView()
{
  const std::vector<double> depths = { 0.0, 0.5, 1.0, 1.5 };
  const std::vector<double> values = { 10.0, std::numeric_limits<double>::quiet_NaN(), 30.0, 40.0 };
  const CurveSeriesView v = makeDoubleView( depths.data(), values.data(), 4 );
  QCOMPARE( v.count, qsizetype( 4 ) );
  QCOMPARE( v.depthAt( 2 ), 1.0 );
  QVERIFY( std::isnan( v.valueAt( 1 ) ) );
  QCOMPARE( v.valueAt( 3 ), 40.0 );
}

void TestCurveView::float32View()
{
  const std::vector<float> depths = { 0.0f, 1.0f, 2.0f };
  const std::vector<float> values = { 1.5f, -2.25f, 3.75f };
  CurveSeriesView v;
  v.depths = depths.data();
  v.values = values.data();
  v.count = 3;
  v.format = SampleFormat::Float32;
  QCOMPARE( v.depthAt( 1 ), 1.0 );
  QCOMPARE( v.valueAt( 1 ), -2.25 );
}

void TestCurveView::stridedMemberView()
{
  struct Sample
  {
    double depth;
    int tag;
    double value;
  };
  std::vector<Sample> samples = { { 0.0, 1, 5.0 }, { 1.0, 2, 6.0 }, { 2.0, 3, 7.0 } };
  const CurveSeriesView v =
    makeMemberView( samples.data(), samples.size(), &Sample::depth, &Sample::value );
  QCOMPARE( v.depthStride(), qsizetype( sizeof( Sample ) ) );
  QCOMPARE( v.depthAt( 1 ), 1.0 );
  QCOMPARE( v.valueAt( 2 ), 7.0 );
}

void TestCurveView::emptyView()
{
  CurveSeriesView v;
  QVERIFY( v.isEmpty() );
  const CurveSeriesView nullCount = makeDoubleView( nullptr, nullptr, 0 );
  QVERIFY( nullCount.isEmpty() );
}

void TestCurveView::monotonicValidation()
{
  {
    const std::vector<double> d = { 0, 1, 2, 3 };
    const std::vector<double> v( 4, 0.0 );
    QCOMPARE( validateDepthMonotonic( makeDoubleView( d.data(), v.data(), 4 ) ), qsizetype( -1 ) );
  }
  {
    const std::vector<double> d = { 0, 2, 1, 3 };  // violation at index 2
    const std::vector<double> v( 4, 0.0 );
    QCOMPARE( validateDepthMonotonic( makeDoubleView( d.data(), v.data(), 4 ) ), qsizetype( 2 ) );
  }
  {
    const double nan = std::numeric_limits<double>::quiet_NaN();
    const std::vector<double> d = { 0, 1, nan, 3 };
    const std::vector<double> v( 4, 0.0 );
    QCOMPARE( validateDepthMonotonic( makeDoubleView( d.data(), v.data(), 4 ) ), qsizetype( 2 ) );
  }
  {
    const std::vector<double> d = { 0, 0, 1 };  // equal depths are fine
    const std::vector<double> v( 3, 0.0 );
    QCOMPARE( validateDepthMonotonic( makeDoubleView( d.data(), v.data(), 3 ) ), qsizetype( -1 ) );
  }
}

QTEST_APPLESS_MAIN( TestCurveView )
#include "test_curve_view.moc"
