#include "geoviz/well_track/config/view_config.h"

#include <QJsonArray>

#include <algorithm>
#include <unordered_set>

namespace geoviz::well_track {

namespace {

constexpr int kMinTrackWidth = 40;   // canvas.py width clamp
constexpr int kMaxTrackWidth = 300;

QString qstr(const std::string& s) { return QString::fromStdString(s); }
std::string stdstr(const QString& s) { return s.toStdString(); }

const char* trackKindKey(TrackKind k) {
    switch (k) {
        case TrackKind::Depth: return "depth";
        case TrackKind::Curve: return "curve";
        case TrackKind::Interval: return "interval";
        case TrackKind::Lithology: return "lithology";
        case TrackKind::Facies: return "facies";
        case TrackKind::SystemsTract: return "systems_tract";
        case TrackKind::Marker: return "marker";
        case TrackKind::Image: return "image";
    }
    return "curve";
}

std::optional<TrackKind> trackKindFrom(const QString& s) {
    if (s == "depth") return TrackKind::Depth;
    if (s == "curve") return TrackKind::Curve;
    if (s == "interval") return TrackKind::Interval;
    if (s == "lithology") return TrackKind::Lithology;
    if (s == "facies") return TrackKind::Facies;
    if (s == "systems_tract") return TrackKind::SystemsTract;
    if (s == "marker") return TrackKind::Marker;
    if (s == "image") return TrackKind::Image;
    return std::nullopt;
}

int lineStyleKey(LineStyle s) {
    switch (s) {
        case LineStyle::Solid: return 0;
        case LineStyle::Dashed: return 1;
        case LineStyle::Dotted: return 2;
    }
    return 0;
}

std::optional<LineStyle> lineStyleFrom(int v) {
    if (v == 0) return LineStyle::Solid;
    if (v == 1) return LineStyle::Dashed;
    if (v == 2) return LineStyle::Dotted;
    return std::nullopt;
}

QJsonObject xRangeToJson(const XRange& r) {
    QJsonObject o;
    if (r.manual) {
        QJsonObject m;
        m["lo"] = r.manual->first;
        m["hi"] = r.manual->second;
        o["manual"] = m;
    }
    o["scale"] = r.scale == ScaleKind::Log ? "log" : "linear";
    return o;
}

std::optional<XRange> xRangeFrom(const QJsonObject& o) {
    XRange r;
    if (o.contains("manual")) {
        const QJsonObject m = o["manual"].toObject();
        if (!m.contains("lo") || !m.contains("hi")) return std::nullopt;
        r.manual = std::make_pair(m["lo"].toDouble(), m["hi"].toDouble());
    }
    r.scale = o["scale"].toString() == "log" ? ScaleKind::Log : ScaleKind::Linear;
    return r;
}

QJsonObject curveStyleToJson(const CurveStyle& s) {
    QJsonObject o;
    o["rgba"] = static_cast<double>(s.rgba);
    o["lineWidth"] = s.lineWidth;
    o["lineStyle"] = lineStyleKey(s.lineStyle);
    o["visible"] = s.visible;
    if (!s.label.empty()) o["label"] = qstr(s.label);
    return o;
}

std::optional<CurveStyle> curveStyleFrom(const QJsonObject& o) {
    CurveStyle s;
    s.rgba = static_cast<std::uint32_t>(o["rgba"].toDouble(0xFF63B3ED));
    s.lineWidth = o["lineWidth"].toDouble(1.5);
    if (o.contains("lineStyle")) {
        const auto ls = lineStyleFrom(o["lineStyle"].toInt(0));
        if (!ls) return std::nullopt;
        s.lineStyle = *ls;
    }
    s.visible = o["visible"].toBool(true);
    s.label = stdstr(o["label"].toString());
    return s;
}

}  // namespace

QJsonObject TrackConfigEntry::toJson() const {
    QJsonObject o;
    o["id"] = qstr(id.value);
    o["title"] = qstr(title);
    o["kind"] = trackKindKey(kind);
    o["width"] = width;
    o["visible"] = visible;
    o["xRange"] = xRangeToJson(xRange);
    QJsonArray arr;
    for (const auto& c : curves) {
        QJsonObject co;
        co["curveId"] = qstr(c.curveId.value);
        co["style"] = curveStyleToJson(c.style);
        arr.append(co);
    }
    o["curves"] = arr;
    if (kind == TrackKind::Interval || kind == TrackKind::Lithology || kind == TrackKind::Facies ||
        kind == TrackKind::SystemsTract) {
        QJsonObject io;
        io["setId"] = qstr(intervals.setId.value);
        io["columnKey"] = qstr(intervals.columnKey);
        io["nested"] = intervals.nested;
        o["intervals"] = io;
    }
    if (kind == TrackKind::Marker) o["markerSet"] = qstr(markerSet.value);
    if (kind == TrackKind::Image) o["imageSet"] = qstr(imageSet.value);
    return o;
}

std::optional<TrackConfigEntry> TrackConfigEntry::fromJson(const QJsonObject& o) {
    TrackConfigEntry e;
    e.id = TrackId(stdstr(o["id"].toString()));
    if (e.id.empty()) return std::nullopt;
    e.title = stdstr(o["title"].toString());
    const auto kind = trackKindFrom(o["kind"].toString());
    if (!kind) return std::nullopt;
    e.kind = *kind;
    e.width = o["width"].toInt(defaultTrackWidth(e.kind));
    if (e.kind != TrackKind::Marker) {
        // Historical configs with out-of-clamp widths load clamped instead
        // of being rejected wholesale.
        e.width = std::clamp(e.width, kMinTrackWidth, kMaxTrackWidth);
    }
    e.visible = o["visible"].toBool(true);
    if (o.contains("xRange")) {
        const auto r = xRangeFrom(o["xRange"].toObject());
        if (!r) return std::nullopt;
        e.xRange = *r;
    }
    for (const auto& v : o["curves"].toArray()) {
        const QJsonObject co = v.toObject();
        CurveAssignment a;
        a.curveId = CurveId(stdstr(co["curveId"].toString()));
        if (a.curveId.empty()) return std::nullopt;
        const auto st = curveStyleFrom(co["style"].toObject());
        if (!st) return std::nullopt;
        a.style = *st;
        e.curves.push_back(std::move(a));
    }
    if (o.contains("intervals")) {
        const QJsonObject io = o["intervals"].toObject();
        e.intervals.setId = IntervalSetId(stdstr(io["setId"].toString()));
        e.intervals.columnKey = stdstr(io["columnKey"].toString());
        e.intervals.nested = io["nested"].toBool(false);
    }
    e.markerSet = MarkerSetId(stdstr(o["markerSet"].toString()));
    e.imageSet = ImageSetId(stdstr(o["imageSet"].toString()));
    return e;
}

QJsonObject WellTrackViewConfig::toJson() const {
    QJsonObject o;
    o["schemaVersion"] = schemaVersion;
    if (!templateId.empty()) o["templateId"] = qstr(templateId);
    if (!domainLabel.empty()) o["domainLabel"] = qstr(domainLabel);
    QJsonArray arr;
    for (const auto& t : tracks) arr.append(t.toJson());
    o["tracks"] = arr;
    return o;
}

std::optional<WellTrackViewConfig> WellTrackViewConfig::fromJson(const QJsonObject& json) {
    WellTrackViewConfig cfg;
    cfg.schemaVersion = json["schemaVersion"].toInt(0);
    if (cfg.schemaVersion != kViewConfigSchemaVersion) return std::nullopt;
    cfg.templateId = stdstr(json["templateId"].toString());
    cfg.domainLabel = stdstr(json["domainLabel"].toString());
    for (const auto& v : json["tracks"].toArray()) {
        auto entry = TrackConfigEntry::fromJson(v.toObject());
        if (!entry) return std::nullopt;
        cfg.tracks.push_back(std::move(*entry));
    }
    return cfg;
}

bool WellTrackViewConfig::validate(std::string* err) const {
    std::unordered_set<std::string> seen;
    for (const auto& t : tracks) {
        if (t.id.empty() || !seen.insert(t.id.value).second) {
            if (err) *err = "duplicate or empty track id: " + t.id.value;
            return false;
        }
        if (t.kind == TrackKind::Marker) {
            if (t.width != 0) {
                if (err) *err = "marker overlay must be zero-width: " + t.id.value;
                return false;
            }
        } else if (t.width < kMinTrackWidth || t.width > kMaxTrackWidth) {
            if (err) *err = "width out of [40,300]: " + t.id.value;
            return false;
        }
    }
    return true;
}

}  // namespace geoviz::well_track
