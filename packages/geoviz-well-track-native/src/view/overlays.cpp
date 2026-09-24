#include "overlays.h"

#include <QMouseEvent>
#include <QPainter>
#include <QPainterPath>
#include <QStringList>

#include <cmath>

namespace geoviz::well_track {

CrosshairOverlay::CrosshairOverlay(QWidget* parent) : QWidget(parent) {
    setAttribute(Qt::WA_TransparentForMouseEvents);
    setAttribute(Qt::WA_NoSystemBackground);
}

void CrosshairOverlay::setInspection(const InspectionResult& result, int y) {
    result_ = result;
    y_ = y;
    visible_ = true;
    update();
}

void CrosshairOverlay::clearInspection() {
    if (!visible_) return;
    visible_ = false;
    update();
}

void CrosshairOverlay::paintEvent(QPaintEvent* event) {
    Q_UNUSED(event);
    if (!visible_) return;
    QPainter p(this);
    p.setRenderHint(QPainter::Antialiasing);

    QPen pen(QColor(0xEF, 0x44, 0x44), 1.0, Qt::DashLine);
    p.setPen(pen);
    p.drawLine(0, y_, width(), y_);

    // Compact info panel at the top-right (CrosshairOverlay parity).
    QFont f = font();
    f.setPointSizeF(8.5);
    p.setFont(f);

    QStringList lines;
    if (std::isfinite(result_.depth)) {
        lines << QStringLiteral("深度: %1 %2")
                     .arg(result_.depth, 0, 'f', 2)
                     .arg(QString::fromStdString(result_.depthUnit));
    }
    for (const auto& rd : result_.curves) {
        if (!std::isfinite(rd.value)) continue;
        lines << QStringLiteral("%1: %2%3")
                     .arg(QString::fromStdString(rd.name))
                     .arg(rd.value, 0, 'g', 6)
                     .arg(QString::fromStdString(rd.unit).isEmpty()
                              ? QString()
                              : QStringLiteral(" ") + QString::fromStdString(rd.unit));
    }
    for (const auto& h : result_.intervals) {
        lines << QStringLiteral("%1: %2")
                     .arg(QString::fromStdString(h.trackTitle))
                     .arg(QString::fromStdString(h.category));
    }
    for (const auto& h : result_.markers) {
        lines << QString::fromStdString(h.name);
    }
    if (lines.isEmpty()) return;

    const QFontMetrics fm(f);
    int textWidth = 0;
    for (const QString& l : lines) textWidth = std::max(textWidth, fm.horizontalAdvance(l));
    const int panelW = textWidth + 16;
    const int lineHeight = fm.height();
    const int panelH = static_cast<int>(lines.size()) * lineHeight + 10;

    int px = std::max(0, width() - panelW - 8);
    int py = std::max(0, y_ + 6);
    if (py + panelH > height()) py = std::max(0, y_ - panelH - 6);

    QPainterPath path;
    path.addRoundedRect(QRectF(px, py, panelW, panelH), 6.0, 6.0);
    p.fillPath(path, QColor(15, 23, 42, 216));
    p.setPen(QPen(QColor(0x94, 0xA3, 0xB8), 1.0));
    p.drawPath(path);

    p.setPen(QPen(QColor(0xE2, 0xE8, 0xF0), 1.0));
    for (int i = 0; i < lines.size(); ++i) {
        p.drawText(QPoint(px + 8, py + 5 + (i + 1) * lineHeight - fm.descent()), lines[i]);
    }
}

SplitterOverlay::SplitterOverlay(QWidget* parent) : QWidget(parent) {
    setAttribute(Qt::WA_TransparentForMouseEvents);
    setAttribute(Qt::WA_NoSystemBackground);
}

void SplitterOverlay::setBoundaries(const std::vector<QPair<TrackId, QRectF>>& boundaries) {
    boundaries_ = boundaries;
    update();
}

void SplitterOverlay::paintEvent(QPaintEvent* event) {
    Q_UNUSED(event);
    QPainter p(this);
    p.setPen(QPen(QColor(0x94, 0xA3, 0xB8, 200), 1.0));
    for (const auto& [id, rect] : boundaries_) {
        Q_UNUSED(id);
        p.drawLine(QPointF(rect.center().x(), rect.top()), QPointF(rect.center().x(), rect.bottom()));
    }
}

}  // namespace geoviz::well_track
