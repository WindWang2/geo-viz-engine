#include "geoviz/well_track/view/surface_factory.h"

#include <QCoreApplication>
#include <QDir>
#include <QFileInfo>
#include <QStandardPaths>

namespace geoviz::well_track {

SurfaceRegistry& SurfaceRegistry::instance() {
    static SurfaceRegistry registry;
    return registry;
}

void SurfaceRegistry::registerFactory(std::shared_ptr<ISurfaceFactory> factory) {
    if (!factory) return;
    for (auto& f : factories_) {
        if (f->name() == factory->name()) {
            f = std::move(factory);
            return;
        }
    }
    factories_.push_back(std::move(factory));
}

IWellTrackSurface* SurfaceRegistry::createPreferred(QWidget* parent) const {
    if (factories_.empty()) return nullptr;
    return factories_.back()->create(parent);
}

std::vector<QString> SurfaceRegistry::registeredNames() const {
    std::vector<QString> names;
    names.reserve(factories_.size());
    for (const auto& f : factories_) names.push_back(f->name());
    return names;
}

QString defaultPatternAssetDir() {
    // Explicit override first.
    const QByteArray env = qgetenv("GEOVIZ_WELL_TRACK_PATTERN_DIR");
    if (!env.isEmpty() && QFileInfo::exists(QString::fromUtf8(env))) {
        return QString::fromUtf8(env);
    }
    // Install-prefix layout: <prefix>/share/geoviz/well-track/patterns
    QDir appDir(QCoreApplication::applicationDirPath());
    const QStringList candidates = {
        appDir.filePath(QStringLiteral("../share/geoviz/well-track/patterns")),
        appDir.filePath(QStringLiteral("share/geoviz/well-track/patterns")),
        appDir.filePath(QStringLiteral("../../packages/geoviz-well-track-native/assets/patterns")),
    };
    for (const QString& c : candidates) {
        if (QFileInfo::exists(c)) return QDir(c).canonicalPath();
    }
    (void)QStandardPaths::AppDataLocation;  // kept for future host-managed assets
    return QString();
}

}  // namespace geoviz::well_track
