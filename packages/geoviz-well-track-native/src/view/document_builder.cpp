#include "document_builder.h"

#include <QFileInfo>
#include <QString>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <unordered_set>

#include "geoviz/well_track/domain/pattern_catalog.h"

namespace geoviz::well_track::docbuild {

namespace {

std::string formatDepth(double v, double step) {
    char buf[64];
    const int decimals = step >= 1.0 ? 0 : (step >= 0.1 ? 1 : 2);
    std::snprintf(buf, sizeof(buf), "%.*f", decimals, v);
    return buf;
}

std::string formatRangeText(double lo, double hi, const std::string& unit) {
    char buf[96];
    std::snprintf(buf, sizeof(buf), "%.6g~%.6g%s%s", lo, hi, unit.empty() ? "" : " ",
                  unit.c_str());
    return buf;
}

CurveStyle defaultCurveStyle(const CurveMetadata& meta) {
    CurveStyle style;
    if (auto metaStyle = curveMetaStyle(meta.name)) style = *metaStyle;
    style.label = meta.name;
    return style;
}

QString patternAssetPath(const QString& dir, const std::string& patternKey) {
    // pattern_engine.py naming: hyphen -> underscore; facies/ subdir first.
    // Results are memoized: row assembly must not stat the filesystem per
    // interval (docs 09).
    if (dir.isEmpty() || patternKey.empty()) return QString();
    static std::unordered_map<std::string, QString> cache;  // GUI-thread only
    const auto it = cache.find(patternKey);
    if (it != cache.end()) return it->second;
    std::string file = patternKey;
    std::replace(file.begin(), file.end(), '-', '_');
    const QString name = QString::fromStdString(file) + QStringLiteral(".svg");
    QString resolved;
    if (QFileInfo::exists(dir + QStringLiteral("/facies/") + name)) {
        resolved = dir + QStringLiteral("/facies/") + name;
    } else if (QFileInfo::exists(dir + QStringLiteral("/") + name)) {
        resolved = dir + QStringLiteral("/") + name;
    }
    cache[patternKey] = resolved;
    return resolved;
}

std::vector<SurfaceIntervalRow> intervalRows(const IntervalColumn& column, TrackKind kind,
                                             const QString& patternDir) {
    std::vector<SurfaceIntervalRow> rows;
    const auto& catalog = PatternCatalog::builtin();
    for (std::size_t i = 0; i < column.items.size(); ++i) {
        const auto& it = column.items[i];
        SurfaceIntervalRow r;
        r.top = it.top;
        r.bottom = it.bottom;
        r.label = it.category;
        switch (kind) {
            case TrackKind::Lithology: {
                r.fillRgba = catalog.fallbackColorFor(it.category);
                if (auto key = catalog.patternKeyFor(it.category)) {
                    const QString path = patternAssetPath(patternDir, *key);
                    if (!path.isEmpty()) r.patternAssetPath = path.toStdString();
                }
                break;
            }
            case TrackKind::Facies: {
                r.fillRgba = catalog.fallbackColorFor(it.category);
                if (auto key = catalog.patternKeyFor(it.category)) {
                    const QString path = patternAssetPath(patternDir, *key);
                    if (!path.isEmpty()) r.patternAssetPath = path.toStdString();
                }
                break;
            }
            case TrackKind::SystemsTract:
                r.fillRgba = systemsTractStyle(it.category, i).rgba;
                r.shape = systemsTractStyle(it.category, i).shape;
                break;
            default:
                r.fillRgba = intervalStyleFor(it, i).rgba;
                break;
        }
        rows.push_back(std::move(r));
    }
    return rows;
}

TrackConfigEntry makeEntry(TrackId id, std::string title, TrackKind kind) {
    TrackConfigEntry e;
    e.id = std::move(id);
    e.title = std::move(title);
    e.kind = kind;
    e.width = defaultTrackWidth(kind);
    return e;
}

}  // namespace

WellTrackViewConfig buildDefaultDocument(const WellDataSnapshot& snapshot) {
    WellTrackViewConfig cfg;
    cfg.domainLabel = snapshot.well.domainLabel;

    // 1. Depth track (always).
    {
        TrackConfigEntry e = makeEntry(TrackId("depth"),
                                       "深度 (" + snapshot.well.depthUnitLabel + ")",
                                       TrackKind::Depth);
        cfg.tracks.push_back(std::move(e));
    }

    // 2. Stratigraphy: system / series / formation (skip empty).
    if (const IntervalSetData* strat = snapshot.intervalSet(IntervalSetId(kStratSetId))) {
        static const struct {
            const char* column;
            const char* title;
        } kFields[] = {{"system", "系"}, {"series", "统"}, {"formation", "组"}};
        for (const auto& f : kFields) {
            if (!strat->column(f.column) || strat->column(f.column)->items.empty()) continue;
            TrackConfigEntry e = makeEntry(TrackId(std::string("strat:") + f.column), f.title,
                                           TrackKind::Interval);
            e.intervals.setId = IntervalSetId(kStratSetId);
            e.intervals.columnKey = f.column;
            cfg.tracks.push_back(std::move(e));
        }
    }

    // 3. Lithology.
    if (const IntervalSetData* set = snapshot.intervalSet(IntervalSetId(kLithoSetId))) {
        if (!set->columns.empty() && !set->columns.front().items.empty()) {
            TrackConfigEntry e = makeEntry(TrackId("lithology"), "岩性", TrackKind::Lithology);
            e.intervals.setId = IntervalSetId(kLithoSetId);
            e.intervals.columnKey = set->columns.front().key;
            cfg.tracks.push_back(std::move(e));
        }
    }

    // 4. Facies: nested when the adapter supplied the phase/sub/micro columns.
    if (const IntervalSetData* facies = snapshot.intervalSet(IntervalSetId(kFaciesSetId))) {
        const bool hasPhase = facies->column("phase") && !facies->column("phase")->items.empty();
        const bool hasSub =
            facies->column("sub_phase") && !facies->column("sub_phase")->items.empty();
        const bool hasMicro =
            facies->column("micro_phase") && !facies->column("micro_phase")->items.empty();
        const bool hasAny = hasPhase || hasSub || hasMicro;
        if (hasAny) {
            TrackConfigEntry e = makeEntry(TrackId("facies"), "沉积相", TrackKind::Facies);
            e.intervals.setId = IntervalSetId(kFaciesSetId);
            e.intervals.nested = hasPhase && (hasSub || hasMicro);
            if (!e.intervals.nested) {
                // Single-level facies: use whichever column carries data.
                e.intervals.columnKey = hasPhase    ? "phase"
                                        : hasSub    ? "sub_phase"
                                                    : "micro_phase";
            }
            cfg.tracks.push_back(std::move(e));
        }
    }

    // 5. Systems tract.
    if (const IntervalSetData* set = snapshot.intervalSet(IntervalSetId(kTractSetId))) {
        if (!set->columns.empty() && !set->columns.front().items.empty()) {
            TrackConfigEntry e = makeEntry(TrackId("systems_tract"), "体系域",
                                           TrackKind::SystemsTract);
            e.intervals.setId = IntervalSetId(kTractSetId);
            e.intervals.columnKey = set->columns.front().key;
            cfg.tracks.push_back(std::move(e));
        }
    }

    // 6. Sequence.
    if (const IntervalSetData* set = snapshot.intervalSet(IntervalSetId(kSeqSetId))) {
        if (!set->columns.empty() && !set->columns.front().items.empty()) {
            TrackConfigEntry e = makeEntry(TrackId("sequence"), "层序", TrackKind::Interval);
            e.intervals.setId = IntervalSetId(kSeqSetId);
            e.intervals.columnKey = set->columns.front().key;
            cfg.tracks.push_back(std::move(e));
        }
    }

    // 7. Core photos.
    if (const ImageSetData* set = snapshot.imageSet(ImageSetId(kPhotosSetId))) {
        if (!set->segments.empty()) {
            TrackConfigEntry e = makeEntry(TrackId("core_photos"), "照片/文本描述",
                                           TrackKind::Image);
            e.imageSet = ImageSetId(kPhotosSetId);
            cfg.tracks.push_back(std::move(e));
        }
    }

    // 8. Curve tracks: merge groups first, then one track per remaining
    // curve. Duplicate mnemonics all render (#584): adapter gave them
    // distinct CurveIds.
    std::unordered_set<std::string> used;
    for (const auto& [names, title] : mergeGroups()) {
        std::vector<CurveId> members;
        bool anyLog = false;
        for (const auto& n : names) {
            for (const auto& [cid, buf] : snapshot.curves) {
                if (buf && buf->meta().name == n) {
                    members.push_back(cid);
                    anyLog = anyLog || isLogScaleCurve(n);
                }
            }
        }
        if (members.empty()) continue;
        TrackConfigEntry e = makeEntry(TrackId("curve:merge:" + title), title, TrackKind::Curve);
        if (anyLog) e.xRange.scale = ScaleKind::Log;
        for (const auto& cid : members) {
            const CurveBuffer* buf = snapshot.curve(cid);
            CurveAssignment a;
            a.curveId = cid;
            a.style = defaultCurveStyle(buf ? buf->meta() : CurveMetadata{});
            e.curves.push_back(std::move(a));
            used.insert(cid.value);
        }
        cfg.tracks.push_back(std::move(e));
    }
    for (const auto& [cid, buf] : snapshot.curves) {
        if (used.count(cid.value)) continue;
        TrackConfigEntry e =
            makeEntry(TrackId("curve:" + cid.value), buf ? buf->meta().name : cid.value,
                      TrackKind::Curve);
        if (buf && isLogScaleCurve(buf->meta().name)) e.xRange.scale = ScaleKind::Log;
        CurveAssignment a;
        a.curveId = cid;
        a.style = defaultCurveStyle(buf ? buf->meta() : CurveMetadata{});
        e.curves.push_back(std::move(a));
        cfg.tracks.push_back(std::move(e));
    }

    // 9. Marker overlay (zero-width, full canvas).
    if (const MarkerSetData* set = snapshot.markerSet(MarkerSetId(kTopsSetId))) {
        if (!set->tops.empty()) {
            TrackConfigEntry e = makeEntry(TrackId("tops"), "", TrackKind::Marker);
            e.width = 0;
            e.markerSet = MarkerSetId(kTopsSetId);
            cfg.tracks.push_back(std::move(e));
        }
    }

    return cfg;
}

// Public API (curve_style.h): manual ranges are kept when sane, robust
// range otherwise. Sanity parity (curve_track.py:96-108).
std::pair<std::pair<double, double>, bool> resolveXRange(const XRange& range,
                                                         const CurveBuffer& buffer,
                                                         const std::string& curveName) {
    if (range.manual) {
        const auto [lo, hi] = *range.manual;
        const bool sane = lo < hi && lo > -100.0 && hi <= 1e5;
        if (sane) return {*range.manual, false};
    }
    if (buffer.empty()) return {{0.0, 100.0}, true};
    return {computeRobustDisplayRange(buffer.values().data(), buffer.size(), curveName), true};
}

std::pair<std::pair<double, double>, bool> effectiveRange(const XRange& range,
                                                          const CurveBuffer* buffer,
                                                          const std::string& curveName) {
    if (!buffer) return {{0.0, 100.0}, true};
    return resolveXRange(range, *buffer, curveName);
}

std::optional<SurfaceTrackColumn> assembleColumn(const TrackConfigEntry& entry,
                                                 const WellDataSnapshot* snapshot,
                                                 const DepthRange& depthRange, int contentHeight,
                                                 const QString& patternAssetDir,
                                                 bool imagesSupported) {
    SurfaceTrackColumn col;
    col.trackId = entry.id;
    col.title = entry.title;
    col.width = entry.width;

    switch (entry.kind) {
        case TrackKind::Depth: {
            col.kind = SurfaceColumnKind::DepthAxis;
            const double h = contentHeight > 0 ? contentHeight : 600.0;
            const double step = niceDepthInterval(depthRange.span(), h);
            for (double d : depthTicks(depthRange.top, depthRange.bottom, h)) {
                SurfaceTick t;
                t.depth = d;
                t.text = formatDepth(d, step);
                col.ticks.push_back(std::move(t));
            }
            break;
        }
        case TrackKind::Curve: {
            col.kind = SurfaceColumnKind::Curve;
            if (!snapshot) break;
            for (const auto& a : entry.curves) {
                const CurveBuffer* buf = snapshot->curve(a.curveId);
                SurfaceCurveLayer layer;
                layer.curveId = a.curveId;
                const auto it = snapshot->curves.find(a.curveId);
                layer.data = it != snapshot->curves.end() ? it->second : nullptr;
                const std::string curveName = buf ? buf->meta().name : a.curveId.value;
                layer.label = a.style.label.empty() ? curveName : a.style.label;
                layer.color = QColor((a.style.rgba >> 16) & 0xFF, (a.style.rgba >> 8) & 0xFF,
                                     a.style.rgba & 0xFF, (a.style.rgba >> 24) & 0xFF);
                layer.lineWidth = a.style.lineWidth;
                layer.lineStyle = a.style.lineStyle;
                XRange effective = entry.xRange;
                const auto [vals, usedRobust] = effectiveRange(entry.xRange, buf, curveName);
                effective.manual = vals;  // resolved concrete range for the kernel
                layer.xRange = effective;
                col.curves.push_back(std::move(layer));

                SurfaceHeaderEntry hdr;
                hdr.hasSwatch = true;
                hdr.swatchRgba = a.style.rgba;
                hdr.line1 = layer.label;
                hdr.line2 = formatRangeText(vals.first, vals.second,
                                            buf ? buf->meta().unit : "");
                col.headerEntries.push_back(std::move(hdr));
            }
            break;
        }
        case TrackKind::Interval:
        case TrackKind::Lithology:
        case TrackKind::Facies:
        case TrackKind::SystemsTract: {
            col.kind = SurfaceColumnKind::Interval;
            if (!snapshot) break;
            const IntervalSetData* set = snapshot->intervalSet(entry.intervals.setId);
            if (!set) break;
            if (entry.intervals.nested) {
                static const char* kNested[3] = {"phase", "sub_phase", "micro_phase"};
                for (int sub = 0; sub < 3; ++sub) {
                    if (const IntervalColumn* c = set->column(kNested[sub])) {
                        auto rows = intervalRows(*c, entry.kind, patternAssetDir);
                        for (auto& r : rows) {
                            r.subColumn = sub;
                            r.subColumnCount = 3;
                            col.intervals.push_back(std::move(r));
                        }
                    }
                }
            } else if (const IntervalColumn* c = set->column(entry.intervals.columnKey)) {
                col.intervals = intervalRows(*c, entry.kind, patternAssetDir);
            }
            if (!entry.title.empty()) {
                SurfaceHeaderEntry hdr;
                hdr.line1 = entry.title;
                col.headerEntries.push_back(std::move(hdr));
            }
            break;
        }
        case TrackKind::Marker: {
            col.kind = SurfaceColumnKind::MarkerOverlay;
            if (!snapshot) break;
            const MarkerSetData* set = snapshot->markerSet(entry.markerSet);
            if (!set) break;
            for (std::size_t i = 0; i < set->tops.size(); ++i) {
                const auto& t = set->tops[i];
                SurfaceMarkerRow row;
                row.depth = t.depth;
                row.label = t.name;
                const std::uint32_t rgba = t.rgba != 0 ? t.rgba : markerPaletteColor(i);
                row.color = QColor((rgba >> 16) & 0xFF, (rgba >> 8) & 0xFF, rgba & 0xFF,
                                   (rgba >> 24) & 0xFF);
                col.markers.push_back(std::move(row));
            }
            break;
        }
        case TrackKind::Image: {
            if (!imagesSupported) return std::nullopt;
            col.kind = SurfaceColumnKind::Image;
            if (!snapshot) break;
            const ImageSetData* set = snapshot->imageSet(entry.imageSet);
            if (!set) break;
            col.images = set->segments;
            if (!entry.title.empty()) {
                SurfaceHeaderEntry hdr;
                hdr.line1 = entry.title;
                col.headerEntries.push_back(std::move(hdr));
            }
            break;
        }
    }
    return col;
}

}  // namespace geoviz::well_track::docbuild
