// Host integration example / representative-well smoke (docs 06 §14).
//
// Without the Prompt A kernel this binary still runs: the widget reports the
// "no render kernel" state — proving link-level integration of
// GeoViz::WellTrackNative. With -DGEOVIZ_WELL_TRACK_WITH_QGIS_KERNEL=ON the
// same binary drives the real QGIS-backed surface (full smoke path:
// representative well -> pan/zoom -> crosshair inspection -> reorder/hide ->
// close).
#include <QApplication>
#include <QCommandLineOption>
#include <QCommandLineParser>
#include <QJsonArray>
#include <QTimer>
#include <QVBoxLayout>
#include <QWidget>

#ifdef GEOVIZ_WELL_TRACK_WITH_QGIS_KERNEL
#include <qgsapplication.h>
#endif

#include <cmath>
#include <cstdio>
#include <memory>

#include "geoviz/well_track/well_track.h"

using namespace geoviz::well_track;

namespace {

class ExampleSource final : public IWellTrackDataSource {
public:
    ExampleSource(SnapshotPtr snap) : snap_(std::move(snap)) {}
    WellDescriptor descriptor() const override { return snap_->well; }
    SnapshotPtr snapshot() const override { return snap_; }

private:
    SnapshotPtr snap_;
};

// Inline representative well (mirrors the Python test fixtures).
SnapshotPtr makeRepresentativeWell() {
    auto s = std::make_shared<WellDataSnapshot>();
    s->revision = 1;
    s->well.id = WellId("EXAMPLE-1");
    s->well.displayName = "Example Well 1";
    s->fullRange = DepthRange{1000.0, 2000.0};

    std::vector<double> d;
    for (double x = 1000.0; x <= 2000.0; x += 0.5) d.push_back(x);
    std::vector<double> gr(d.size()), rt(d.size()), ac(d.size(), 240.0);
    for (std::size_t i = 0; i < d.size(); ++i) {
        gr[i] = 80.0 + 40.0 * std::sin(i * 0.02);
        rt[i] = 10.0 * std::pow(10.0, 0.3 * std::sin(i * 0.013));
    }
    s->curves[CurveId("AC")] = std::make_shared<const CurveBuffer>(d, ac, CurveMetadata{"AC", "us/m"});
    s->curves[CurveId("GR")] = std::make_shared<const CurveBuffer>(d, gr, CurveMetadata{"GR", "API"});
    s->curves[CurveId("RT")] = std::make_shared<const CurveBuffer>(d, rt, CurveMetadata{"RT", "ohm.m"});

    auto litho = std::make_shared<IntervalSetData>();
    IntervalColumn lc;
    lc.key = "lithology";
    lc.items = {{1000.0, 1400.0, "砂岩", "细砂岩"},
                {1400.0, 1700.0, "灰岩", ""},
                {1700.0, 2000.0, "泥岩", ""}};
    litho->columns = {lc};
    litho->finalize();
    s->intervalSets[IntervalSetId("lithology")] = litho;

    auto facies = std::make_shared<IntervalSetData>();
    IntervalColumn phase;
    phase.key = "phase";
    phase.items = {{1000.0, 1500.0, "潮坪"}, {1500.0, 2000.0, "陆棚"}};
    IntervalColumn sub;
    sub.key = "sub_phase";
    sub.items = {{1000.0, 1200.0, "砂坪"}, {1200.0, 2000.0, "泥坪"}};
    IntervalColumn micro;
    micro.key = "micro_phase";
    micro.items = {{1000.0, 1100.0, "潮道"}, {1100.0, 2000.0, ""}};
    facies->columns = {phase, sub, micro};
    facies->finalize();
    s->intervalSets[IntervalSetId("facies")] = facies;

    auto tops = std::make_shared<MarkerSetData>();
    tops->tops = {{1250.0, "F2-top"}, {1700.0, "LST-top"}};
    tops->finalize();
    s->markerSets[MarkerSetId("tops")] = tops;
    return s;
}

}  // namespace

int run(int argc, char** argv) {
    // main() may already have created a QgsApplication (QApplication
    // subclass) when the QGIS kernel is enabled — never construct a second
    // application object.
    QApplication* app = static_cast<QApplication*>(QApplication::instance());
    if (!app) app = new QApplication(argc, argv);
    QCommandLineParser parser;
    QCommandLineOption smokeOption("smoke", "run scripted smoke then exit");
    parser.addOption(smokeOption);
    parser.process(*app);

    WellTrackViewFactory factory;
    auto source = std::make_shared<ExampleSource>(makeRepresentativeWell());
    WellTrackWidget* view = factory.create(source);

    auto* window = new QWidget;
    auto* layout = new QVBoxLayout(window);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->addWidget(view);
    window->resize(900, 700);
    window->show();

    WellTrackController* c = view->controller();
    if (parser.isSet(smokeOption)) {
        QTimer::singleShot(200, [c, view, window]() {
            // Scripted smoke: zoom at an anchor, inspect, manage tracks, close.
            c->zoomAt(1500.0, 0.2);
            const InspectionResult r = c->inspectAt(1250.0);
            std::printf("smoke: tracks=%zu depth=%.2f curves=%zu intervals=%zu markers=%zu\n",
                        c->tracks().size(), r.depth, r.curves.size(), r.intervals.size(),
                        r.markers.size());
            c->setTrackVisible(TrackId("lithology"), false);
            c->moveTrack(TrackId("facies"), 0);
            const QJsonObject cfg = c->viewConfig().toJson();
            std::printf("smoke: config tracks=%d roundtrip=%s\n",
                        cfg["tracks"].toArray().size(),
                        WellTrackViewConfig::fromJson(cfg) ? "ok" : "FAIL");
            window->close();
        });
    }
    return app->exec();
}

int main(int argc, char** argv) {
#ifdef GEOVIZ_WELL_TRACK_WITH_QGIS_KERNEL
    // QGIS-backed kernel: symbol/text registries need QgsApplication (A's
    // documented bootstrap; see A's examples/welltrack_demo).
    QgsApplication app(argc, argv, true);
    QgsApplication::setPrefixPath(QString::fromLocal8Bit(qgetenv("QT_QGIS_PREFIX_DIR")), true);
    QgsApplication::init();
    QgsApplication::initQgis();
    const int rc = run(argc, argv);
    QgsApplication::exitQgis();
    return rc;
#else
    return run(argc, argv);
#endif
}
