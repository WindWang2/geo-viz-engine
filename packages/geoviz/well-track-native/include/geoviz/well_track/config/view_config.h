// Serializable view/track configuration (task §13). This is configuration,
// not data: no sample arrays, only ids, order, widths, visibility, curve
// assignments and styles. The host decides where it is stored — this package
// is not a second project authority.
#pragma once

#include <optional>
#include <string>
#include <vector>

#include <QJsonObject>

#include "geoviz/well_track/domain/curve_style.h"
#include "geoviz/well_track/domain/defaults.h"
#include "geoviz/well_track/domain/ids.h"

namespace geoviz::well_track {

constexpr int kViewConfigSchemaVersion = 1;

struct CurveAssignment {
    CurveId curveId;
    CurveStyle style;
};

struct IntervalBinding {
    IntervalSetId setId;
    std::string columnKey;  // single-column tracks; empty for facies nested
    bool nested = false;    // facies 3-subcolumn rendering
};

struct TrackConfigEntry {
    TrackId id;
    std::string title;
    TrackKind kind = TrackKind::Curve;
    int width = 60;  // clamped to [40, 300] on apply (Marker overlay: 0)
    bool visible = true;

    XRange xRange;                       // Curve tracks
    std::vector<CurveAssignment> curves; // Curve tracks
    IntervalBinding intervals;           // Interval/Lithology/Facies/SystemsTract
    std::string intervalColumnKeyExtra;  // reserved for secondary columns
    MarkerSetId markerSet;               // Marker tracks
    ImageSetId imageSet;                 // Image tracks

    QJsonObject toJson() const;
    static std::optional<TrackConfigEntry> fromJson(const QJsonObject& json);
};

struct WellTrackViewConfig {
    int schemaVersion = kViewConfigSchemaVersion;
    std::string templateId;  // optional host-side template reference
    std::string domainLabel; // optional header override; empty -> well label
    std::vector<TrackConfigEntry> tracks;  // layout order

    QJsonObject toJson() const;
    // Unknown major schema versions are rejected (nullopt).
    static std::optional<WellTrackViewConfig> fromJson(const QJsonObject& json);

    // Validation used by the controller before applying: unique track ids,
    // width clamping, marker overlays zero-width. Returns false + first
    // offending id via *err on failure.
    bool validate(std::string* err = nullptr) const;
};

}  // namespace geoviz::well_track
