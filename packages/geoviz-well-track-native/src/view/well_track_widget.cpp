#include "geoviz/well_track/view/well_track_widget.h"

#include <QEvent>
#include <QLabel>
#include <QMouseEvent>
#include <QResizeEvent>
#include <QVBoxLayout>

#include <cmath>

#include "overlays.h"

namespace geoviz::well_track {

WellTrackWidget::WellTrackWidget(IWellTrackSurface* surface,
                                 std::shared_ptr<IWellTrackDataSource> source, QWidget* parent)
    : QWidget(parent), surface_(surface) {  // QPointer: null-safe if a host
                                             // destroys the surface early
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
        splitter_ = new SplitterOverlay(this);  // paint-only; input via filter

        // Product splitter drags: the kernel viewport stays the single input
        // surface; we intercept only presses inside the 6px boundary zones
        // (Round 2: an input-hungry overlay killed zoom/inspect in real
        // kernel integration).
        surface_->widget()->installEventFilter(this);

        connect(surface_, &IWellTrackSurface::viewportResized, this,
                [this](int h) {
                    Q_UNUSED(h);
                    updateOverlaysGeometry();
                });
    } else {
        // Surface without a viewport widget: still take ownership so the
        // QObject is cleaned up with this widget.
        if (surface_) surface_->setParent(this);
        emptyLabel_->setText(QStringLiteral(
            "未找到渲染内核（GeoViz::QgisWellTrack 不可用）。\n"
            "请链接 Prompt A 的 kernel 包后重试。"));
        layout->addWidget(emptyLabel_, 1);
    }

    layout->addWidget(statusLabel_);
    statusLabel_->setText(QStringLiteral("就绪"));

    // Owned solely by the unique_ptr member (destroyed before the surface
    // child) — deliberately not QObject-parented to avoid double ownership.
    controller_ = std::make_unique<WellTrackController>(surface_);

    // Single inspection path: the controller turns surface cursor movement
    // into InspectionResult; this widget only renders it.
    connect(controller_.get(), &WellTrackController::inspectionChanged, this,
            [this](const InspectionResult& result) {
                lastInspection_ = result;
                if (crosshair_) {
                    const int y = surface_ ? surface_->yPosForDepth(result.depth) : -1;
                    const bool inView = y >= 0 && crosshair_ && y <= crosshair_->height();
                    if (result.isValid() && inView) {
                        crosshair_->setInspection(result, y);
                    } else {
                        crosshair_->clearInspection();
                    }
                }
                setStatusFromInspection(result);
                emit inspectionChanged(result);
            });
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
    if (emptyLabel_ && emptyLabel_->isVisible()) {
        // Empty state is not layout-managed (it overlays the hidden viewport
        // area) — keep it spanning the content area on resize.
        emptyLabel_->setGeometry(QRect(0, 0, width(), std::max(height() - 28, 0)));
    }
}

bool WellTrackWidget::eventFilter(QObject* watched, QEvent* event) {
    if (surface_ && watched == surface_->widget()) {
        switch (event->type()) {
            case QEvent::MouseButtonPress: {
                auto* me = static_cast<QMouseEvent*>(event);
                if (me->button() == Qt::LeftButton &&
                    handleSplitterPress(me->position())) {
                    return true;  // consumed: boundary drag, not a kernel tool
                }
                break;
            }
            case QEvent::MouseMove: {
                auto* me = static_cast<QMouseEvent*>(event);
                if (splitterDragging_) {
                    handleSplitterDrag(me->position());
                    return true;
                }
                break;
            }
            case QEvent::MouseButtonRelease: {
                if (splitterDragging_) {
                    handleSplitterRelease();
                    return true;
                }
                break;
            }
            default:
                break;
        }
    }
    return QWidget::eventFilter(watched, event);
}

bool WellTrackWidget::handleSplitterPress(const QPointF& pos) {
    if (!splitter_) return false;
    const auto& bounds = splitter_->boundaries();
    for (const auto& [id, rect] : bounds) {
        if (std::abs(pos.x() - rect.center().x()) <= SplitterOverlay::kHitZonePx &&
            pos.y() >= rect.top() && pos.y() <= rect.bottom()) {
            splitterDragTrack_ = id;
            splitterLastX_ = static_cast<int>(pos.x());
            splitterDragging_ = true;
            return true;
        }
    }
    return false;
}

void WellTrackWidget::handleSplitterDrag(const QPointF& pos) {
    const int x = static_cast<int>(pos.x());
    const int delta = x - splitterLastX_;
    splitterLastX_ = x;
    if (delta == 0 || !controller_) return;
    for (const auto& t : controller_->tracks()) {
        if (t.id == splitterDragTrack_ && t.kind != TrackKind::Marker) {
            controller_->setTrackWidth(t.id, t.width + delta);
            updateOverlaysGeometry();
            return;
        }
    }
}

void WellTrackWidget::handleSplitterRelease() {
    splitterDragging_ = false;
    splitterDragTrack_ = TrackId{};
}

void WellTrackWidget::updateOverlaysGeometry() {
    if (!surface_ || !surface_->widget()) return;
    const QRect content = surface_->widget()->geometry();
    if (crosshair_) {
        crosshair_->setGeometry(content);
        crosshair_->raise();
    }
    if (splitter_) splitter_->raise();
    if (!splitter_ || !controller_) return;
    // One boundary per adjacent visible-column pair. The track list is
    // referenced, never copied (config entries hold strings/vectors).
    std::vector<QPair<TrackId, QRectF>> boundaries;
    const std::vector<TrackConfigEntry>& tracks = controller_->tracks();
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
    for (const auto& m : result.markers) {
        text += QStringLiteral("  |  层位 %1").arg(QString::fromStdString(m.name));
    }
    statusLabel_->setText(text);
}

void WellTrackWidget::refreshEmptyState() {
    if (!surface_ || !surface_->widget()) return;  // error label already shown
    const bool empty =
        !controller_ || !controller_->snapshot() || controller_->snapshot()->empty();
    emptyLabel_->setVisible(false);
    surface_->widget()->setVisible(!empty);
    if (empty) {
        emptyLabel_->setText(QStringLiteral("当前井无可视化数据"));
        emptyLabel_->setGeometry(QRect(0, 0, width(), std::max(height() - 28, 0)));
        emptyLabel_->raise();
        emptyLabel_->setVisible(true);
    }
}

}  // namespace geoviz::well_track
