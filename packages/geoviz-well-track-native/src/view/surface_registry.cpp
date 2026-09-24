#include "geoviz/well_track/view/surface_factory.h"

#include <QCoreApplication>
#include <QDir>
#include <QFileInfo>
#include <QStandardPaths>

namespace geoviz::well_track {

#ifdef GEOVIZ_WELL_TRACK_WITH_QGIS_KERNEL
// Defined in qgis_surface.cpp; calling it from createPreferred forces the
// archive member (and its factory self-registration) to be linked.
bool qgisSurfaceFactorySelfRegister();
#endif

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
#ifdef GEOVIZ_WELL_TRACK_WITH_QGIS_KERNEL
    (void)qgisSurfaceFactorySelfRegister();  // archive keep-alive
#endif
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
    // Resolved once per process (column assembly calls this per rebuild).
    static const QString cached = []() -> QString {
        const QByteArray env = qgetenv("GEOVIZ_WELL_TRACK_PATTERN_DIR");
        if (!env.isEmpty() && QFileInfo::exists(QString::fromUtf8(env))) {
            return QString::fromUtf8(env);
        }
        QDir appDir(QCoreApplication::applicationDirPath());
        const QStringList candidates = {
            appDir.filePath(QStringLiteral("../share/geoviz/well-track/patterns")),
            appDir.filePath(QStringLiteral("share/geoviz/well-track/patterns")),
            appDir.filePath(
                QStringLiteral("../../packages/geoviz-well-track-native/assets/patterns")),
        };
        for (const QString& c : candidates) {
            if (QFileInfo::exists(c)) return QDir(c).canonicalPath();
        }
        return QString();
    }();
    return cached;
}

}  // namespace geoviz::well_track
