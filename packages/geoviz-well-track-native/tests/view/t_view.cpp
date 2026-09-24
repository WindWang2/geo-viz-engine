// Controller/widget behaviour tests driven through MockSurface (docs 10 §C/D).
#include <QtTest>

#include <QApplication>
#include <cmath>

#include "geoviz/well_track/view/well_track_factory.h"
#include "geoviz/well_track/view/well_track_widget.h"
#include "mock_surface.h"
#include "test_fixtures.h"

using namespace geoviz::well_track;
using namespace geoviz::well_track::testing;

namespace {
int countCalls(const MockSurface& s, MockSurfaceCall::Kind k) {
    int n = 0;
    for (const auto& c : s.calls())
        if (c.kind == k) ++n;
    return n;
}
bool hasCall(const MockSurface& s, MockSurfaceCall::Kind k, const QString& id = QString()) {
    for (const auto& c : s.calls()) {
        if (c.kind == k && (id.isEmpty() || c.trackId == id)) return true;
    }
    return false;
}
}  // namespace

class TestControllerDepth : public QObject {
    Q_OBJECT
private slots:
    void init() { surface_ = new MockSurface(); }
    void cleanup() { delete surface_; }

    void noOpGuardSuppressesSignal() {
        WellTrackController c(surface_);
        QSignalSpy spy(&c, &WellTrackController::depthRangeChanged);
        c.loadSource(std::make_shared<StaticSource>(representativeSnapshot()));
        const int afterLoad = spy.size();
        QVERIFY(!c.setDepthRange(1000.0, 2000.0));  // same range -> no-op
        QCOMPARE(spy.size(), afterLoad);
        // Below-eps change is also a no-op (1e-9 guard).
        QVERIFY(!c.setDepthRange(1000.0, 2000.0 + 5e-10));
        QCOMPARE(spy.size(), afterLoad);
    }
    void zoomAnchorStaysFixed() {
        WellTrackController c(surface_);
        c.loadSource(std::make_shared<StaticSource>(representativeSnapshot()));
        const double anchor = 1500.0;
        c.zoomAt(anchor, 0.2);
        // Anchor depth keeps its screen ratio: ratio*(newSpan) from newTop.
        const DepthRange r = c.depthRange();
        const double ratio = (anchor - r.top) / r.span();
        QCOMPARE(ratio, (anchor - 1000.0) / 1000.0);
        // span shrunk by 20% *if* not clamped by full range
        QVERIFY(r.span() <= 1000.0);
    }
    void zoomMinSpan() {
        WellTrackController c(surface_);
        c.loadSource(std::make_shared<StaticSource>(representativeSnapshot()));
        c.setDepthRange(1500.0, 1500.4);  // 0.4 span < 1 -> normalized to 1.4? see below
        // normalize() only guards zero span; the min-span rule lives in zoom.
        c.zoomAt(1500.0, 0.999);
        QVERIFY(c.depthRange().span() >= 1.0);
    }
    void panClampedToFullRange() {
        WellTrackController c(surface_);
        c.loadSource(std::make_shared<StaticSource>(representativeSnapshot()));
        c.panDepth(-5000.0);
        QCOMPARE(c.depthRange().top, 1000.0);
        c.panDepth(+5000.0);
        QCOMPARE(c.depthRange().bottom, 2000.0);
    }
    void fitDepthRestoresFull() {
        WellTrackController c(surface_);
        c.loadSource(std::make_shared<StaticSource>(representativeSnapshot()));
        c.zoomAt(1500.0, 0.5);
        QVERIFY(c.depthRange().span() < 1000.0);
        c.fitDepth();
        QVERIFY(c.depthRange().nearlyEqual(DepthRange{1000.0, 2000.0}));
    }
    void kernelRequestAppliesMinSpan() {
        WellTrackController c(surface_);
        c.loadSource(std::make_shared<StaticSource>(representativeSnapshot()));
        surface_->emitDepthRequest(1500.0, 1500.2);  // sub-min span intent
        QVERIFY(c.depthRange().span() >= 1.0);
    }

private:
    MockSurface* surface_ = nullptr;
};

class TestControllerTracks : public QObject {
    Q_OBJECT
private slots:
    void init() { surface_ = new MockSurface(); }
    void cleanup() { delete surface_; }

    void widthClamp() {
        WellTrackController c(surface_);
        c.loadSource(std::make_shared<StaticSource>(representativeSnapshot()));
        const TrackId id("lithology");
        QVERIFY(c.setTrackWidth(id, 999));
        QCOMPARE(c.viewConfig().tracks[4].width, 300);
        QVERIFY(c.setTrackWidth(id, 5));
        QCOMPARE(c.viewConfig().tracks[4].width, 40);
    }
    void visibilityRemovesAndRestoresColumn() {
        WellTrackController c(surface_);
        c.loadSource(std::make_shared<StaticSource>(representativeSnapshot()));
        surface_->clearCalls();
        QVERIFY(c.setTrackVisible(TrackId("lithology"), false));
        QVERIFY(hasCall(*surface_, MockSurfaceCall::RemoveTrack, "lithology"));
        QVERIFY(c.setTrackVisible(TrackId("lithology"), true));
        QVERIFY(hasCall(*surface_, MockSurfaceCall::UpdateTrack, "lithology"));
    }
    void reorderRequiresFullSync() {
        WellTrackController c(surface_);
        c.loadSource(std::make_shared<StaticSource>(representativeSnapshot()));
        surface_->clearCalls();
        QVERIFY(c.moveTrack(TrackId("facies"), 0));
        QVERIFY(hasCall(*surface_, MockSurfaceCall::SetTracks));
        QCOMPARE(c.viewConfig().tracks[0].id.value.c_str(), "facies");
    }
    void mergeAndSplit() {
        WellTrackController c(surface_);
        c.loadSource(std::make_shared<StaticSource>(representativeSnapshot()));
        const TrackId merged = c.mergeCurvesIntoTrack({CurveId("AC"), CurveId("RT")}, "AC+RT");
        QVERIFY(merged);
        bool found = false;
        for (const auto& t : c.tracks()) {
            if (t.id == merged) {
                found = true;
                QCOMPARE(static_cast<int>(t.curves.size()), 2);
            }
        }
        QVERIFY(found);
        QVERIFY(c.splitCurveFromTrack(merged, CurveId("RT")));
        int trackCount = 0;
        for (const auto& t : c.tracks()) trackCount += (t.title == "AC+RT" || t.title == "RT");
        QCOMPARE(trackCount, 2);
    }
    void addCurveTrackValidatesIds() {
        WellTrackController c(surface_);
        c.loadSource(std::make_shared<StaticSource>(representativeSnapshot()));
        QVERIFY(!c.addCurveTrack({CurveId("NOPE")}));
        const TrackId id = c.addCurveTrack({CurveId("GR")});
        QVERIFY(id);
        // Seam upsert contract: the new column is actually on the surface.
        bool present = false;
        for (const auto& col : surface_->columns()) present = present || (col.trackId == id);
        QVERIFY(present);
    }
    void styleOnlyUpdateTouchesOneColumn() {
        WellTrackController c(surface_);
        c.loadSource(std::make_shared<StaticSource>(representativeSnapshot()));
        surface_->clearCalls();
        CurveStyle st;
        st.rgba = 0xFFFF0000;
        QVERIFY(c.setCurveStyle(TrackId("curve:merge:AC/GR"), CurveId("GR"), st));
        QCOMPARE(countCalls(*surface_, MockSurfaceCall::UpdateTrack), 1);
        QCOMPARE(countCalls(*surface_, MockSurfaceCall::SetTracks), 0);
    }

private:
    MockSurface* surface_ = nullptr;
};

class TestSnapshotReplace : public QObject {
    Q_OBJECT
private slots:
    void init() { surface_ = new MockSurface(); }
    void cleanup() { delete surface_; }

    void staleRevisionRejected() {
        WellTrackController c(surface_);
        auto src = std::make_shared<StaticSource>(representativeSnapshot(5));
        c.loadSource(src);
        QVERIFY(!c.replaceSnapshot(representativeSnapshot(4)));  // stale (L3)
        QVERIFY(c.replaceSnapshot(representativeSnapshot(6)));
    }
    void oneCurveChangeUpdatesOnlyItsColumn() {
        WellTrackController c(surface_);
        auto src = std::make_shared<StaticSource>(representativeSnapshot(1));
        c.loadSource(src);
        surface_->clearCalls();

        // Shallow copy: unchanged curves keep their shared buffers (identity
        // equal), only GR gets a new buffer with a bumped revision.
        auto next = std::make_shared<WellDataSnapshot>(*src->snapshot());
        next->revision = 2;
        next->curves[CurveId("GR")] =
            makeCurve("GR", "API", {1000.0, 1500.0, 2000.0}, {10.0, 90.0, 30.0}, 2);
        QVERIFY(c.replaceSnapshot(next));
        QCOMPARE(countCalls(*surface_, MockSurfaceCall::UpdateTrack), 1);
        QVERIFY(hasCall(*surface_, MockSurfaceCall::UpdateTrack, "curve:merge:AC/GR"));
        QCOMPARE(countCalls(*surface_, MockSurfaceCall::SetTracks), 0);
    }
    void hiddenCurveTrackStaysHiddenOnRefresh() {
        WellTrackController c(surface_);
        auto src = std::make_shared<StaticSource>(representativeSnapshot(1));
        c.loadSource(src);
        const TrackId acGr("curve:merge:AC/GR");
        QVERIFY(c.setTrackVisible(acGr, false));
        bool onSurface = false;
        for (const auto& col : surface_->columns()) onSurface = onSurface || (col.trackId == acGr);
        QVERIFY(!onSurface);

        // Same-well refresh that changes GR must not resurrect the hidden
        // column (Round 2 P1).
        auto next = std::make_shared<WellDataSnapshot>(*src->snapshot());
        next->revision = 2;
        next->curves[CurveId("GR")] =
            makeCurve("GR", "API", {1000.0, 1500.0, 2000.0}, {10.0, 90.0, 30.0}, 2);
        QVERIFY(c.replaceSnapshot(next));
        for (const auto& col : surface_->columns()) {
            QVERIFY(col.trackId != acGr);  // still hidden
        }
        QVERIFY(!hasCall(*surface_, MockSurfaceCall::UpdateTrack, "curve:merge:AC/GR"));
    }

    void zeroCopyHandoff() {
        WellTrackController c(surface_);
        auto src = std::make_shared<StaticSource>(representativeSnapshot(1));
        c.loadSource(src);
        const CurveBufferPtr raw = src->snapshot()->curves.at(CurveId("GR"));
        for (const auto& col : surface_->columns()) {
            for (const auto& layer : col.curves) {
                if (layer.curveId == CurveId("GR")) {
                    QVERIFY(layer.data.get() == raw.get());  // no copy (docs 09)
                }
            }
        }
    }

private:
    MockSurface* surface_ = nullptr;
};

class TestInspection : public QObject {
    Q_OBJECT
private slots:
    void init() { surface_ = new MockSurface(); }
    void cleanup() { delete surface_; }

    void curveReadoutInterpolated() {
        WellTrackController c(surface_);
        c.loadSource(std::make_shared<StaticSource>(representativeSnapshot()));
        const InspectionResult r = c.inspectAt(1000.5);
        QVERIFY(r.isValid());
        bool sawGr = false;
        for (const auto& rd : r.curves) {
            if (rd.name == "GR") {
                sawGr = true;
                QVERIFY(std::isfinite(rd.value));
                QVERIFY(!rd.unit.empty());
            }
        }
        QVERIFY(sawGr);
    }
    void intervalAndMarkerHits() {
        WellTrackController c(surface_);
        c.loadSource(std::make_shared<StaticSource>(representativeSnapshot()));
        const InspectionResult r = c.inspectAt(1250.0);
        bool sawFormation = false, sawLitho = false, sawTop = false;
        for (const auto& h : r.intervals) {
            if (h.columnKey == "formation") sawFormation = true;
            if (h.trackId == TrackId("lithology")) sawLitho = true;
        }
        for (const auto& m : r.markers) sawTop = (m.name == "F2-top");
        QVERIFY(sawFormation);
        QVERIFY(sawLitho);
        QVERIFY(sawTop);  // 10px screen tolerance at 400px/1000m ≈ 25 m
    }
    void gapDepthYieldsNaNReadings() {
        WellTrackController c(surface_);
        auto snap = representativeSnapshot();
        snap->curves[CurveId("GR")] =
            makeCurve("GR", "API", {1000.0, 1100.0, 1900.0, 2000.0},
                      {1.0, std::numeric_limits<double>::quiet_NaN(), 3.0, 4.0});
        c.loadSource(std::make_shared<StaticSource>(snap));
        const InspectionResult r = c.inspectAt(1500.0);
        for (const auto& rd : r.curves) {
            if (rd.name == "GR") QVERIFY(std::isnan(rd.value));  // gap readout
        }
    }
    void snapToExtreme() {
        WellTrackController c(surface_);
        c.loadSource(std::make_shared<StaticSource>(representativeSnapshot()));
        // GR = 80 + 40*sin(0.05 i): local max near i=10..11 (d≈1010-1011).
        const auto mx = c.snapToExtreme(CurveId("GR"), 1010.0, 1.5, SnapMode::Maximum);
        QVERIFY(mx.has_value());
        QVERIFY(std::abs(*mx - 1010.5) <= 1.5);
        const auto mn = c.snapToExtreme(CurveId("GR"), 1010.0, 1.5, SnapMode::Minimum);
        QVERIFY(mn.has_value());
        QVERIFY(*mn != *mx);
    }
    void hiddenTracksExcluded() {
        WellTrackController c(surface_);
        c.loadSource(std::make_shared<StaticSource>(representativeSnapshot()));
        c.setTrackVisible(TrackId("lithology"), false);
        const InspectionResult r = c.inspectAt(1450.0);
        for (const auto& h : r.intervals) QVERIFY(h.trackId != TrackId("lithology"));
    }

private:
    MockSurface* surface_ = nullptr;
};

class TestSyncGroup : public QObject {
    Q_OBJECT
private slots:
    void twoControllersNoEcho() {
        MockSurface s1, s2;
        WellTrackController a(&s1), b(&s2);
        a.loadSource(std::make_shared<StaticSource>(representativeSnapshot()));
        b.loadSource(std::make_shared<StaticSource>(representativeSnapshot()));
        a.addSyncPeer(&b);
        b.addSyncPeer(&a);
        s1.clearCalls();
        s2.clearCalls();
        a.setDepthRange(1200.0, 1600.0);
        QVERIFY(b.depthRange().nearlyEqual(DepthRange{1200.0, 1600.0}));
        QCOMPARE(countCalls(s2, MockSurfaceCall::SetDepthRange), 1);  // no echo
        QCOMPARE(countCalls(s1, MockSurfaceCall::SetDepthRange), 1);
    }
};

class TestWidget : public QObject {
    Q_OBJECT
private slots:
    void constructAndLifecycle() {
        WellTrackViewFactory factory;
        auto source = std::make_shared<StaticSource>(representativeSnapshot());
        auto* surface = new MockSurface();
        WellTrackWidget* w = factory.createWithSurface(source, surface);
        QVERIFY(w->controller() != nullptr);
        // depth + 3 stratigraphy + lithology + facies + tract + 2 merged
        // curve tracks + tops overlay
        QCOMPARE(static_cast<int>(w->controller()->tracks().size()), 10);
        // Cursor inspection updates the readout.
        QSignalSpy spy(w, &WellTrackWidget::inspectionChanged);
        surface->emitCursor(1250.0);
        QVERIFY(spy.size() >= 1);
        QVERIFY(w->inspectAtCursor().isValid());
        // Switch wells (full document path), then destroy.
        w->controller()->replaceSnapshot(representativeSnapshot(2));
        w->syncWith(nullptr);  // no-op
        delete w;              // must not crash (ownership chain)
    }
    void errorStateWithoutKernel() {
        WellTrackWidget w(nullptr, nullptr);
        QVERIFY(w.controller() != nullptr);
        QVERIFY(w.controller()->tracks().empty());
    }
    void emptySnapshotState() {
        WellTrackViewFactory factory;
        auto snap = std::make_shared<WellDataSnapshot>();
        snap->well.id = WellId("W3");
        auto* surface = new MockSurface();
        WellTrackWidget* w = factory.createWithSurface(std::make_shared<StaticSource>(snap),
                                                       surface);
        QCOMPARE(static_cast<int>(w->controller()->tracks().size()), 1);  // depth only
        delete w;
    }
};

class TestLargeData : public QObject {
    Q_OBJECT
private slots:
    void largeCurveLoadAndInspect() {
        // docs 09 acceptance: 1e5 samples x 8 curves; timing recorded.
        auto s = std::make_shared<WellDataSnapshot>();
        s->revision = 1;
        s->well.id = WellId("BIG");
        s->fullRange = DepthRange{0.0, 100000.0};
        std::vector<double> d(100000);
        for (std::size_t i = 0; i < d.size(); ++i) d[i] = static_cast<double>(i);
        for (int k = 0; k < 8; ++k) {
            std::vector<double> v(d.size());
            for (std::size_t i = 0; i < v.size(); ++i)
                v[i] = std::sin(static_cast<double>(i + k) * 0.001);
            s->curves[CurveId("C" + std::to_string(k))] =
                makeCurve("C" + std::to_string(k), "u", d, v);
        }
        MockSurface surface;
        WellTrackController c(&surface);
        QElapsedTimer timer;
        timer.start();
        c.loadSource(std::make_shared<StaticSource>(s));
        const qint64 loadMs = timer.elapsed();
        timer.restart();
        for (double depth = 0.5; depth < 1000.0; depth += 3.7) c.inspectAt(depth);
        const qint64 inspectMs = timer.elapsed();
        qInfo("large-curve: load=%lldms inspect(270 calls)=%lldms", loadMs, inspectMs);
        QVERIFY(loadMs < 500);
        QVERIFY(inspectMs < 200);
    }
    void repeatedWellSwitchNoGrowth() {
        MockSurface surface;
        WellTrackController c(&surface);
        for (int i = 0; i < 20; ++i) {
            auto snap = representativeSnapshot(static_cast<std::uint64_t>(i + 1));
            snap->well.id = WellId("W" + std::to_string(i));  // force full rebuild
            c.replaceSnapshot(snap);
        }
        QCOMPARE(static_cast<int>(c.tracks().size()), 10);
    }
};

int main(int argc, char** argv) {
    QApplication app(argc, argv);  // widget tests need a real QApplication
    int status = 0;
    {
        TestControllerDepth t;
        status |= QTest::qExec(&t, argc, argv);
    }
    {
        TestControllerTracks t;
        status |= QTest::qExec(&t, argc, argv);
    }
    {
        TestSnapshotReplace t;
        status |= QTest::qExec(&t, argc, argv);
    }
    {
        TestInspection t;
        status |= QTest::qExec(&t, argc, argv);
    }
    {
        TestSyncGroup t;
        status |= QTest::qExec(&t, argc, argv);
    }
    {
        TestWidget t;
        status |= QTest::qExec(&t, argc, argv);
    }
    {
        TestLargeData t;
        status |= QTest::qExec(&t, argc, argv);
    }
    return status;
}
#include "t_view.moc"
