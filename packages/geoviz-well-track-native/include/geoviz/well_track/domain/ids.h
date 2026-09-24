// Strong string ids for the well-track domain.
//
// Ids are stable across sessions (safe to persist inside view configs) and
// unique within one WellDataSnapshot. Domain layer is Qt-free by design.
#pragma once

#include <cstddef>
#include <functional>
#include <string>
#include <utility>

namespace geoviz::well_track {

template <class Tag>
struct StrongId {
    std::string value;

    StrongId() = default;
    explicit StrongId(std::string v) : value(std::move(v)) {}

    bool operator==(const StrongId& o) const { return value == o.value; }
    bool operator!=(const StrongId& o) const { return value != o.value; }
    bool operator<(const StrongId& o) const { return value < o.value; }

    explicit operator bool() const { return !value.empty(); }
    bool empty() const { return value.empty(); }
};

struct TrackIdTag {
};
using TrackId = StrongId<TrackIdTag>;

struct CurveIdTag {
};
using CurveId = StrongId<CurveIdTag>;

struct IntervalSetIdTag {
};
using IntervalSetId = StrongId<IntervalSetIdTag>;

struct MarkerSetIdTag {
};
using MarkerSetId = StrongId<MarkerSetIdTag>;

struct ImageSetIdTag {
};
using ImageSetId = StrongId<ImageSetIdTag>;

struct WellIdTag {
};
using WellId = StrongId<WellIdTag>;

}  // namespace geoviz::well_track

namespace std {
template <class Tag>
struct hash<geoviz::well_track::StrongId<Tag>> {
    std::size_t operator()(const geoviz::well_track::StrongId<Tag>& id) const noexcept {
        return std::hash<std::string>()(id.value);
    }
};
}  // namespace std
