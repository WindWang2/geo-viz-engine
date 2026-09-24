// Config serialization + default document builder tests (docs 10 §B).
#include <QtTest>

#include "document_builder.h"
#include "geoviz/well_track/config/view_config.h"
#include "test_fixtures.h"

using namespace geoviz::well_track;
using namespace geoviz::well_track::testing;

class TestViewConfig : public QObject {
    Q_OBJECT
private slots:
    void roundtrip() {
        WellTrackViewConfig cfg;
        cfg.templateId = "laolong1";
        cfg.domainLabel = "TVDSS";
        TrackConfigEntry e;
        e.id = TrackId("curve:merge:AC/GR");
        e.title = "AC/GR";
        e.kind = TrackKind::Curve;
        e.width = 140;
        e.xRange.scale = ScaleKind::Log;
        e.xRange.manual = std::make_pair(0.2, 2000.0);
        CurveAssignment a;
        a.curveId = CurveId("RT");
        a.style.rgba = 0xFFB91C1C;
        a.style.lineStyle = LineStyle::Dashed;
        a.style.lineWidth = 2.0;
        a.style.label = "RT";
        e.curves.push_back(a);
        cfg.tracks.push_back(e);
        TrackConfigEntry m;
        m.id = TrackId("tops");
        m.kind = TrackKind::Marker;
        m.width = 0;
        m.markerSet = MarkerSetId("tops");
        cfg.tracks.push_back(m);

        const QJsonObject json = cfg.toJson();
        const auto back = WellTrackViewConfig::fromJson(json);
        QVERIFY(back.has_value());
        QCOMPARE(back->templateId.c_str(), "laolong1");
        QCOMPARE(static_cast<int>(back->tracks.size()), 2);
        QCOMPARE(back->tracks[0].xRange.scale, ScaleKind::Log);
        QCOMPARE(back->tracks[0].xRange.manual->first, 0.2);
        QCOMPARE(back->tracks[0].curves[0].style.rgba, static_cast<std::uint32_t>(0xFFB91C1C));
        QCOMPARE(back->tracks[1].kind, TrackKind::Marker);
    }
    void rejectsUnknownSchema() {
        QJsonObject o;
        o["schemaVersion"] = 99;
        QVERIFY(!WellTrackViewConfig::fromJson(o).has_value());
    }
    void validateDuplicateIds() {
        WellTrackViewConfig cfg;
        TrackConfigEntry a;
        a.id = TrackId("x");
        a.width = 60;
        TrackConfigEntry b;
        b.id = TrackId("x");
        b.width = 60;
        cfg.tracks = {a, b};
        std::string err;
        QVERIFY(!cfg.validate(&err));
        QVERIFY(err.find("duplicate") != std::string::npos);
    }
    void validateWidthClamp() {
        WellTrackViewConfig cfg;
        TrackConfigEntry a;
        a.id = TrackId("x");
        a.width = 500;
        cfg.tracks = {a};
        QVERIFY(!cfg.validate());
    }
    void validateMarkerZeroWidth() {
        WellTrackViewConfig cfg;
        TrackConfigEntry a;
        a.id = TrackId("tops");
        a.kind = TrackKind::Marker;
        a.width = 10;
        cfg.tracks = {a};
        QVERIFY(!cfg.validate());
    }
};

class TestDocumentBuilder : public QObject {
    Q_OBJECT
private slots:
    void defaultOrderParity() {
        // build_qpainter_tracks order: depth -> system/series/formation ->
        // lithology -> facies -> systems tract -> ... -> curves (merged
        // first) -> marker overlay last.
        const SnapshotPtr snap = representativeSnapshot();
        const WellTrackViewConfig cfg = docbuild::buildDefaultDocument(*snap);
        const auto& tracks = cfg.tracks;
        QVERIFY(tracks.size() >= 8);
        QCOMPARE(tracks.front().kind, TrackKind::Depth);
        QCOMPARE(tracks[1].kind, TrackKind::Interval);
        QCOMPARE(tracks[1].id.value.c_str(), "strat:system");
        QCOMPARE(tracks[2].id.value.c_str(), "strat:series");
        QCOMPARE(tracks[3].id.value.c_str(), "strat:formation");
        QCOMPARE(tracks[4].kind, TrackKind::Lithology);
        QCOMPARE(tracks[5].kind, TrackKind::Facies);
        QVERIFY(cfg.tracks[5].intervals.nested);
        QCOMPARE(tracks[6].kind, TrackKind::SystemsTract);
        // curve merge groups
        bool foundAcGr = false, foundRtRxo = false;
        for (const auto& t : tracks) {
            if (t.title == "AC/GR") foundAcGr = true;
            if (t.title == "RT/RXO") foundRtRxo = true;
        }
        QVERIFY(foundAcGr && foundRtRxo);
        QCOMPARE(tracks.back().kind, TrackKind::Marker);
        QCOMPARE(tracks.back().width, 0);
    }
    void defaultWidthsParity() {
        const SnapshotPtr snap = representativeSnapshot();
        const WellTrackViewConfig cfg = docbuild::buildDefaultDocument(*snap);
        for (const auto& t : cfg.tracks) {
            QCOMPARE(t.width, defaultTrackWidth(t.kind));
        }
    }
    void logScaleParity() {
        const SnapshotPtr snap = representativeSnapshot();
        const WellTrackViewConfig cfg = docbuild::buildDefaultDocument(*snap);
        const TrackConfigEntry* rtRxo = nullptr;
        for (const auto& t : cfg.tracks) {
            if (t.title == "RT/RXO") rtRxo = &t;
        }
        QVERIFY(rtRxo);
        QCOMPARE(rtRxo->xRange.scale, ScaleKind::Log);
    }
    void emptySnapshotYieldsDepthOnly() {
        WellDataSnapshot empty;
        empty.well.id = WellId("W2");
        const WellTrackViewConfig cfg = docbuild::buildDefaultDocument(empty);
        QCOMPARE(static_cast<int>(cfg.tracks.size()), 1);
        QCOMPARE(cfg.tracks[0].kind, TrackKind::Depth);
    }
};

int main(int argc, char** argv) {
    int status = 0;
    {
        TestViewConfig t;
        status |= QTest::qExec(&t, argc, argv);
    }
    {
        TestDocumentBuilder t;
        status |= QTest::qExec(&t, argc, argv);
    }
    return status;
}
#include "t_config_builder.moc"
