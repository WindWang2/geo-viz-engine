// Domain tests (Qt-free logic, docs 10 §A). Oracle rows N1/C1/C2/C7/G2/G6/C5.
#include <QtTest>

#include <cmath>
#include <limits>

#include "document_builder.h"
#include "geoviz/well_track/domain/curve.h"
#include "geoviz/well_track/domain/defaults.h"
#include "geoviz/well_track/domain/depth.h"
#include "geoviz/well_track/domain/intervals.h"
#include "geoviz/well_track/domain/pattern_catalog.h"
#include "geoviz/well_track/domain/robust_range.h"

using namespace geoviz::well_track;
using std::vector;

class TestDepth : public QObject {
    Q_OBJECT
private slots:
    void normalizeSwaps() {
        DepthRange r{100.0, 50.0};
        r.normalize();
        QCOMPARE(r.top, 50.0);
        QCOMPARE(r.bottom, 100.0);
    }
    void normalizeZeroSpan() {
        DepthRange r{10.0, 10.0};
        r.normalize();
        QCOMPARE(r.bottom - r.top, 1.0);
    }
    void nearlyEqualGuard() {
        DepthRange a{0.0, 100.0};
        DepthRange b{0.0, 100.0 + 5e-10};
        QVERIFY(a.nearlyEqual(b));
        DepthRange c{0.0, 100.0 + 1e-6};
        QVERIFY(!a.nearlyEqual(c));
    }
    void niceInterval() {
        // parity: smallest 1/2/5x10^k >= span/height*minPx
        QCOMPARE(niceDepthInterval(100.0, 500.0, 20.0), 5.0);    // raw=4
        QCOMPARE(niceDepthInterval(3000.0, 600.0, 20.0), 100.0); // raw=100
        QCOMPARE(niceDepthInterval(0.5, 400.0, 20.0), 0.05);     // raw=0.025
        QCOMPARE(niceDepthInterval(-1.0, 500.0), 1.0);           // degenerate span
    }
    void depthTicksRange() {
        const auto ticks = depthTicks(100.0, 200.0, 500.0, 20.0);
        QVERIFY(!ticks.empty());
        QVERIFY(ticks.front() >= 100.0);
        QVERIFY(ticks.back() <= 200.0);
        for (std::size_t i = 1; i < ticks.size(); ++i) {
            QVERIFY(ticks[i] > ticks[i - 1]);
        }
    }
};

class TestCurveBuffer : public QObject {
    Q_OBJECT
private slots:
    void sortsAndDropsNonFiniteDepth() {
        CurveBuffer buf({30.0, 10.0, std::numeric_limits<double>::quiet_NaN(), 20.0},
                        {3.0, 1.0, 99.0, 2.0}, {"GR", "API"});
        QCOMPARE(static_cast<int>(buf.size()), 3);
        QCOMPARE(buf.depths()[0], 10.0);
        QCOMPARE(buf.values()[0], 1.0);
    }
    void valueAtInterpolates() {
        CurveBuffer buf({0.0, 10.0, 20.0}, {0.0, 10.0, 20.0}, {"GR", ""});
        QCOMPARE(buf.valueAt(5.0), 5.0);   // halfway
        QCOMPARE(buf.valueAt(10.0), 10.0); // exact sample
    }
    void valueAtOutsideIsNaN() {
        CurveBuffer buf({0.0, 10.0}, {0.0, 10.0}, {"GR", ""});
        QVERIFY(std::isnan(buf.valueAt(-1.0)));
        QVERIFY(std::isnan(buf.valueAt(11.0)));
    }
    void valueAtGapIsNaN() {
        const double nan = std::numeric_limits<double>::quiet_NaN();
        CurveBuffer buf({0.0, 10.0, 20.0, 30.0}, {0.0, nan, nan, 3.0}, {"GR", ""});
        QVERIFY(std::isnan(buf.valueAt(15.0)));
        QCOMPARE(buf.valueAt(30.0), 3.0);
    }
};

class TestRobustRange : public QObject {
    Q_OBJECT
private slots:
    void grPreset() {
        // GR data centered at 80 -> preset (0, max(150, p99+10))
        vector<double> v(1001);
        for (int i = 0; i <= 1000; ++i) v[i] = 40.0 + 80.0 * i / 1000.0;
        const auto [lo, hi] = computeRobustDisplayRange(v.data(), v.size(), "GR");
        QCOMPARE(lo, 0.0);
        QVERIFY(hi >= 150.0);
    }
    void rhobPresetClamped() {
        vector<double> v(1001);
        for (int i = 0; i <= 1000; ++i) v[i] = 2.2 + 0.4 * i / 1000.0;
        const auto [lo, hi] = computeRobustDisplayRange(v.data(), v.size(), "RHOB");
        QVERIFY(lo >= 1.5);
        QVERIFY(hi <= 3.0);
        QVERIFY(lo < hi);  // #113: never inverted
    }
    void generalQuantile() {
        vector<double> v;
        for (int i = 0; i < 1000; ++i) v.push_back(i);  // 0..999
        const auto [lo, hi] = computeRobustDisplayRange(v.data(), v.size(), "CAL");
        // P2=19.98, P98=979.02, +/-5% then rounded
        QVERIFY(lo < 25.0 && lo > 10.0);
        QVERIFY(hi > 970.0 && hi < 1000.0);
    }
    void emptyFallsBack() {
        const auto [lo, hi] = computeRobustDisplayRange(nullptr, 0, "GR");
        QCOMPARE(lo, 0.0);
        QCOMPARE(hi, 100.0);
        vector<double> nans(10, std::numeric_limits<double>::quiet_NaN());
        const auto r = computeRobustDisplayRange(nans.data(), nans.size(), "GR");
        QCOMPARE(r.first, 0.0);
        QCOMPARE(r.second, 100.0);
    }
};

class TestXRange : public QObject {
    Q_OBJECT
private slots:
    void manualKeptWhenSane() {
        CurveBuffer buf({0.0, 10.0}, {0.0, 50.0}, {"GR", ""});
        XRange r;
        r.manual = std::make_pair(0.0, 200.0);
        const auto [vals, robust] = docbuild::effectiveRange(r, &buf, "GR");
        QVERIFY(!robust);
        QCOMPARE(vals.first, 0.0);
        QCOMPARE(vals.second, 200.0);
    }
    void manualRejectedWhenInsane() {
        CurveBuffer buf({0.0, 10.0}, {0.0, 50.0}, {"GR", ""});
        XRange r;
        r.manual = std::make_pair(-150.0, 50.0);  // lo <= -100
        QVERIFY(docbuild::effectiveRange(r, &buf, "GR").second);
        r.manual = std::make_pair(0.0, 2e5);  // hi > 1e5
        QVERIFY(docbuild::effectiveRange(r, &buf, "GR").second);
        r.manual = std::make_pair(50.0, 50.0);  // lo == hi
        QVERIFY(docbuild::effectiveRange(r, &buf, "GR").second);
        r.manual = std::make_pair(80.0, 10.0);  // inverted
        QVERIFY(docbuild::effectiveRange(r, &buf, "GR").second);
    }
    void logFloorClamp() {
        XRange r;
        r.scale = ScaleKind::Log;
        QCOMPARE(r.clampForScale(-5.0), XRange::kLogFloor);
        QCOMPARE(r.clampForScale(0.5), 0.5);
    }
};

class TestIntervals : public QObject {
    Q_OBJECT
private slots:
    void hitBasic() {
        IntervalColumn c;
        c.key = "system";
        c.items = {{0.0, 100.0, "A"}, {100.0, 200.0, "B"}, {250.0, 300.0, "C"}};
        c.finalize();
        QVERIFY(hitInterval(c, 50.0) != nullptr);
        QCOMPARE(QString::fromStdString(hitInterval(c, 50.0)->category), QStringLiteral("A"));
        QVERIFY(hitInterval(c, 100.0) != nullptr);
        QCOMPARE(QString::fromStdString(hitInterval(c, 100.0)->category), QStringLiteral("B"));
        QVERIFY(hitInterval(c, 220.0) == nullptr);  // gap
        QVERIFY(hitInterval(c, 199.999) != nullptr);
    }
    void hitOverlappingTakesLongest() {
        IntervalColumn c;
        c.key = "lithology";
        c.items = {{0.0, 100.0, "long"}, {40.0, 60.0, "short"}};
        c.finalize();
        QCOMPARE(QString::fromStdString(hitInterval(c, 50.0)->category), QStringLiteral("long"));
    }
};

class TestPatternCatalog : public QObject {
    Q_OBJECT
private slots:
    void exactMatch() {
        const auto& cat = PatternCatalog::builtin();
        QCOMPARE(cat.patternKeyFor("砂岩").value_or(""), "sandstone");
    }
    void substringLongestFirst() {
        const auto& cat = PatternCatalog::builtin();
        // "粉砂岩" must resolve to siltstone, not the shorter "砂岩"->sandstone
        QCOMPARE(cat.patternKeyFor("含粉砂岩").value_or(""), "siltstone");
    }
    void fallbackColor() {
        const auto& cat = PatternCatalog::builtin();
        QVERIFY(cat.fallbackColorFor("砂岩") != 0);
        QVERIFY(cat.fallbackColorFor("完全未知的岩性XYZ") == 0xFFE0E0E0);
    }
};

class TestDefaults : public QObject {
    Q_OBJECT
private slots:
    void mergeGroupsParity() {
        const auto& groups = mergeGroups();
        QCOMPARE(static_cast<int>(groups.size()), 2);
        QCOMPARE(QString::fromStdString(groups[0].second), QStringLiteral("AC/GR"));
        QCOMPARE(QString::fromStdString(groups[1].second), QStringLiteral("RT/RXO"));
    }
    void logScaleCurves() {
        QVERIFY(isLogScaleCurve("RT"));
        QVERIFY(isLogScaleCurve("RXO"));
        QVERIFY(!isLogScaleCurve("GR"));
    }
    void curveMetaColors() {
        QCOMPARE(curveMetaStyle("AC")->rgba, static_cast<std::uint32_t>(0xFF1D4ED8));
        QVERIFY(curveMetaStyle("AC")->lineStyle == LineStyle::Dashed);
        QVERIFY(!curveMetaStyle("UNKNOWN").has_value());
    }
    void markerPaletteCycles() {
        QCOMPARE(markerPaletteColor(0), static_cast<std::uint32_t>(0xFF0EA5E9));
        QCOMPARE(markerPaletteColor(6), markerPaletteColor(0));
    }
    void tractShapes() {
        QVERIFY(systemsTractStyle("TST", 0).shape == IntervalShape::UpTriangle);
        QVERIFY(systemsTractStyle("HST", 0).shape == IntervalShape::DownTriangle);
        QVERIFY(systemsTractStyle("LST", 0).shape == IntervalShape::Rect);
    }
};

// Run all test classes sequentially (QtTest convention for multi-class bins).
int main(int argc, char** argv) {
    int status = 0;
    {
        TestDepth t;
        status |= QTest::qExec(&t, argc, argv);
    }
    {
        TestCurveBuffer t;
        status |= QTest::qExec(&t, argc, argv);
    }
    {
        TestRobustRange t;
        status |= QTest::qExec(&t, argc, argv);
    }
    {
        TestXRange t;
        status |= QTest::qExec(&t, argc, argv);
    }
    {
        TestIntervals t;
        status |= QTest::qExec(&t, argc, argv);
    }
    {
        TestPatternCatalog t;
        status |= QTest::qExec(&t, argc, argv);
    }
    {
        TestDefaults t;
        status |= QTest::qExec(&t, argc, argv);
    }
    return status;
}
#include "t_domain.moc"
