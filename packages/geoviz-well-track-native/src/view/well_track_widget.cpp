#include "geoviz/well_track/view/well_track_widget.h"

#include <QLabel>
#include <QResizeEvent>
#include <QVBoxLayout>

#include <cmath>

#include "overlays.h"

namespace geoviz::well_track {

WellTrackWidget::WellTrackWidget(IWellTrackSurface* surface,
                                 std::shared_ptr<IWellTrackDataSource> source, QWidget* parent)
    : QWidget(parent), surface_(surface) {
    auto* layout = new QVBoxLayout(this);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(0);

    statusLabel_ = new QLabel(this);
    statusLabel_->setStyleSheet(QStringLiteral(
        "color:#0f172a;background:#e2e8f0;padding:2px 8px;font-size:12px;"));
    emptyLabel_ = new QLabel(this);
    emptyLabel_->setAlignment(Qt::AlignCenter);
    emptyLabel_->setStyleSheet(
        QStringLiteral("color:#64748b;background:#f8fafc;font-size:14px;"));

    if (surface_ && surface_->widget()) {
        // Ownership: the surface object parents to this widget; its viewport
        // widget is reparented into our layout.
        surface_->setParent(this);
        surface_->widget()->setParent(this);
        layout->addWidget(surface_->widget(), 1);

        crosshair_ = new CrosshairOverlay(this);
        splitter_ = new SplitterOverlay(this);

        connect(surface_, &IWellTrackSurface::cursorMoved, this,
                [this](double depth, const QString& trackId) {
                    Q_UNUSED(trackId);
                    lastInspection_ = controller_ ? controller_->inspectAt(depth)
                                                  : InspectionResult{};
                    if (crosshair_) {
                        const int y = surface_->yPosForDepth(depth);
                        if (y >= 0 && lastInspection_.isValid()) {
                            crosshair_->setInspection(lastInspection_, y);
                        } else {
                            crosshair_->clearInspection();
                        }
                    }
                    setStatusFromInspection(lastInspection_);
                    emit inspectionChanged(lastInspection_);
                });
        connect(surface_, &IWellTrackSurface::viewportResized, this,
                [this](int h) {
                    Q_UNUSED(h);
                    updateOverlaysGeometry();
                });
        connect(splitter_, &SplitterOverlay::widthDeltaRequested, this,
                [this](const TrackId& id, int delta) {
                    if (!controller_) return;
                    for (const auto& t : controller_->tracks()) {
                        if (t.id == id && t.kind != TrackKind::Marker) {
                            controller_->setTrackWidth(id, t.width + delta);
                            updateOverlaysGeometry();
                            return;
                        }
                    }
                });
    } else {
        emptyLabel_->setText(QStringLiteral(
            "未找到渲染内核（GeoViz::QgisWellTrack 不可用）。\n"
            "请链接 Prompt A 的 kernel 包后重试。"));
        layout->addWidget(emptyLabel_, 1);
    }

    layout->addWidget(statusLabel_);
    statusLabel_->setText(QStringLiteral("就绪"));

    controller_ = std::make_unique<WellTrackController>(surface_, this);
    connect(controller_.get(), &WellTrackController::depthRangeChanged, this,
            [this](double, double) { updateOverlaysGeometry(); });
    connect(controller_.get(), &WellTrackController::viewConfigChanged, this,
            [this]() {
                refreshEmptyState();
                updateOverlaysGeometry();
            });
    connect(controller_.get(), &WellTrackController::snapshotReplaced, this,
            [this](std::uint64_t) { refreshEmptyState(); });

    if (source) controller_->loadSource(source);
    refreshEmptyState();
}

WellTrackWidget::~WellTrackWidget() = default;

void WellTrackWidget::syncWith(WellTrackWidget* other) {
    if (!other || !controller_ || !other->controller_) return;
    controller_->addSyncPeer(other->controller_.get());
    other->controller_->addSyncPeer(controller_.get());
}

void WellTrackWidget::unsyncAll() {
    if (controller_) controller_->clearSyncPeers();
}

InspectionResult WellTrackWidget::inspectAtCursor() const { return lastInspection_; }

void WellTrackWidget::resizeEvent(QResizeEvent* event) {
    QWidget::resizeEvent(event);
    updateOverlaysGeometry();
}

void WellTrackWidget::updateOverlaysGeometry() {
    if (!surface_ || !surface_->widget()) return;
    const QRect content = surface_->widget()->geometry();
    if (crosshair_) {
        crosshair_->setGeometry(content);
        crosshair_->raise();
    }
    if (splitter_) splitter_->raise();
    if (splitter_) {
        splitter_->setGeometry(content);
        // One boundary per adjacent visible-column pair.
        std::vector<QPair<TrackId, QRectF>> boundaries;
        const auto& tracks = controller_ ? controller_->tracks()
                                         : std::vector<TrackConfigEntry>{};
        const TrackConfigEntry* prev = nullptr;
        QRectF prevRect;
        for (const auto& t : tracks) {
            if (!t.visible || t.kind == TrackKind::Marker) continue;
            const QRectF rect = surface_->trackGeometry(t.id);
            if (!rect.isValid() || rect.width() <= 0) continue;
            if (prev) {
                QRectF b;
                b.setLeft(prevRect.right());
                b.setTop(std::max(prevRect.top(), rect.top()));
                b.setBottom(std::min(prevRect.bottom(), rect.bottom()));
                b.setWidth(1);
                if (b.top() < b.bottom()) boundaries.emplace_back(prev->id, b);
            }
            prev = &t;
            prevRect = rect;
        }
        splitter_->setBoundaries(boundaries);
    }
}

void WellTrackWidget::setStatusFromInspection(const InspectionResult& result) {
    if (!result.isValid()) {
        statusLabel_->setText(QStringLiteral("就绪"));
        return;
    }
    QString text = QStringLiteral("%1 深度: %2 %3")
                       .arg(QString::fromStdString(result.domainLabel))
                       .arg(result.depth, 0, 'f', 2)
                       .arg(QString::fromStdString(result.depthUnit));
    for (const auto& rd : result.curves) {
        if (!std::isfinite(rd.value)) continue;
        text += QStringLiteral("  |  %1=%2%3")
                    .arg(QString::fromStdString(rd.name))
                    .arg(rd.value, 0, 'g', 6)
                    .arg(QString::fromStdString(rd.unit).isEmpty()
                             ? QString()
                             : QStringLiteral(" ") + QString::fromStdString(rd.unit));
    }
    for (const auto& h : result.intervals) {
        text += QStringLiteral("  |  %1: %2")
                    .arg(QString::fromStdString(h.trackTitle))
                    .arg(QString::fromStdString(h.category));
    }
    statusLabel_->setText(text);
}

void WellTrackWidget::refreshEmptyState() {
    if (!surface_ || !surface_->widget()) return;  // error label already shown
    const bool empty = !controller_ || !controller_->snapshot() ||
                       controller_->snapshot()->empty();
    emptyLabel_->setVisible(false);
    surface_->widget()->setVisible(!empty);
    if (empty) {
        emptyLabel_->setText(QStringLiteral("当前井无可视化数据"));
        emptyLabel_->setGeometry(surface_->widget()->geometry());
        emptyLabel_->raise();
        emptyLabel_->setVisible(true);
    }
}

}  // namespace geoviz::well_track
