// Shared inline test fixtures (parity: Python tests build data inline).
#pragma once

#include <cmath>
#include <map>
#include <memory>

#include "geoviz/well_track/data/snapshot.h"

namespace geoviz::well_track::testing {

inline CurveBufferPtr makeCurve(const std::string& name, const std::string& unit,
                                const std::vector<double>& depths,
                                const std::vector<double>& values,
                                std::uint64_t revision = 1) {
    return std::make_shared<const CurveBuffer>(depths, values, CurveMetadata{name, unit},
                                               revision);
}

// Representative well: AC/GR/RT/RXO curves + stratigraphy + lithology +
// nested facies + systems tract + tops. Returns a *mutable* snapshot so
// tests can tweak payloads before handing it over as SnapshotPtr.
inline std::shared_ptr<WellDataSnapshot> representativeSnapshot(std::uint64_t revision = 1) {
    auto s = std::make_shared<WellDataSnapshot>();
    s->revision = revision;
    s->well.id = WellId("W1");
    s->well.displayName = "Well-1";
    s->fullRange = DepthRange{1000.0, 2000.0};

    std::vector<double> d;
    for (double x = 1000.0; x <= 2000.0; x += 1.0) d.push_back(x);

    std::vector<double> gr(d.size());
    for (std::size_t i = 0; i < d.size(); ++i) gr[i] = 80.0 + 40.0 * std::sin(i * 0.05);
    std::vector<double> ac(d.size(), 240.0);
    std::vector<double> rt(d.size());
    for (std::size_t i = 0; i < d.size(); ++i) rt[i] = 10.0 * std::pow(10.0, 0.3 * std::sin(i * 0.03));
    std::vector<double> rxo = rt;

    s->curves[CurveId("AC")] = makeCurve("AC", "us/m", d, ac, revision);
    s->curves[CurveId("GR")] = makeCurve("GR", "API", d, gr, revision);
    s->curves[CurveId("RT")] = makeCurve("RT", "ohm.m", d, rt, revision);
    s->curves[CurveId("RXO")] = makeCurve("RXO", "ohm.m", d, rxo, revision);

    auto strat = std::make_shared<IntervalSetData>();
    IntervalColumn system;
    system.key = "system";
    system.items = {{1000.0, 1500.0, "石炭系"}, {1500.0, 2000.0, "泥盆系"}};
    IntervalColumn series;
    series.key = "series";
    series.items = {{1000.0, 1300.0, "上统"}, {1300.0, 2000.0, "下统"}};
    IntervalColumn formation;
    formation.key = "formation";
    formation.items = {{1000.0, 1250.0, "F1"}, {1250.0, 2000.0, "F2"}};
    strat->columns = {system, series, formation};
    strat->finalize();
    s->intervalSets[IntervalSetId("stratigraphy")] = strat;

    auto litho = std::make_shared<IntervalSetData>();
    IntervalColumn lc;
    lc.key = "lithology";
    lc.items = {{1000.0, 1400.0, "砂岩", "细砂岩"}, {1400.0, 1700.0, "灰岩", "生物碎屑灰岩"},
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
    sub.items = {{1000.0, 1200.0, "砂坪"}, {1200.0, 1500.0, "泥坪"}, {1500.0, 2000.0, "泥质陆棚"}};
    IntervalColumn micro;
    micro.key = "micro_phase";
    micro.items = {{1000.0, 1100.0, "潮道"}, {1100.0, 2000.0, ""}};
    facies->columns = {phase, sub, micro};
    facies->finalize();
    s->intervalSets[IntervalSetId("facies")] = facies;

    auto tract = std::make_shared<IntervalSetData>();
    IntervalColumn tc;
    tc.key = "tract";
    tc.items = {{1000.0, 1300.0, "TST"}, {1300.0, 1700.0, "HST"}, {1700.0, 2000.0, "LST"}};
    tract->columns = {tc};
    tract->finalize();
    s->intervalSets[IntervalSetId("systems_tract")] = tract;

    auto tops = std::make_shared<MarkerSetData>();
    tops->tops = {{1250.0, "F2-top"}, {1700.0, "LST-top"}};
    tops->finalize();
    s->markerSets[MarkerSetId("tops")] = tops;

    return s;
}

class StaticSource final : public IWellTrackDataSource {
public:
    explicit StaticSource(SnapshotPtr snap) : snap_(std::move(snap)) {}
    WellDescriptor descriptor() const override { return snap_->well; }
    SnapshotPtr snapshot() const override { return snap_; }
    void setSnapshot(SnapshotPtr snap) { snap_ = std::move(snap); }

private:
    SnapshotPtr snap_;
};

}  // namespace geoviz::well_track::testing
