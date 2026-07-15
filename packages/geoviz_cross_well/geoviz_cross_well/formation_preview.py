from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import QWidget

from .tops_model import FormationTop


class FormationTopsPreviewWidget(QWidget):
    """Small, self-contained canvas for comparing formation tops between wells."""

    hovered_top_changed = Signal(str, str, float)

    _LEFT = 64.0
    _RIGHT = 120.0
    _TOP = 38.0
    _BOTTOM = 38.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tops: tuple[FormationTop, ...] = ()
        self._well_names: tuple[str, ...] = ()
        self._full_depth_range = (0.0, 1.0)
        self._view_depth_range = (0.0, 1.0)
        self._drag_start_y: float | None = None
        self._drag_start_range = (0.0, 1.0)
        self._hovered_top: FormationTop | None = None
        self.setMouseTracking(True)
        self.setMinimumSize(320, 220)

    @property
    def tops(self) -> tuple[FormationTop, ...]:
        return self._tops

    @property
    def well_names(self) -> tuple[str, ...]:
        return self._well_names

    @property
    def full_depth_range(self) -> tuple[float, float]:
        return self._full_depth_range

    @property
    def view_depth_range(self) -> tuple[float, float]:
        return self._view_depth_range

    def set_tops(
        self, tops: list[FormationTop] | tuple[FormationTop, ...]
    ) -> None:
        self._tops = tuple(tops)
        self._well_names = tuple(sorted({top.well_name for top in self._tops}))
        depths = [top.depth_m for top in self._tops]
        self._full_depth_range = (
            (min(depths), max(depths)) if depths else (0.0, 1.0)
        )
        self._view_depth_range = self._full_depth_range
        self._hovered_top = None
        self.update()

    def clear(self) -> None:
        self._tops = ()
        self._well_names = ()
        self._full_depth_range = (0.0, 1.0)
        self._view_depth_range = (0.0, 1.0)
        self._drag_start_y = None
        self._hovered_top = None
        self.update()

    def _plot_height(self) -> float:
        return max(1.0, self.height() - self._TOP - self._BOTTOM)

    def _well_x(self, index: int) -> float:
        left = self._LEFT
        right = max(left, self.width() - self._RIGHT)
        if len(self._well_names) <= 1:
            return (left + right) / 2.0
        return left + index * (right - left) / (len(self._well_names) - 1)

    def _depth_y(self, depth: float) -> float:
        minimum, maximum = self._view_depth_range
        span = maximum - minimum
        if span <= 0.0:
            return self._TOP + self._plot_height() / 2.0
        return self._TOP + (depth - minimum) / span * self._plot_height()

    def _depth_at_y(self, y: float) -> float:
        minimum, maximum = self._view_depth_range
        ratio = min(1.0, max(0.0, (y - self._TOP) / self._plot_height()))
        return minimum + ratio * (maximum - minimum)

    def _top_points(self):
        well_indices = {name: index for index, name in enumerate(self._well_names)}
        for top in self._tops:
            yield top, QPointF(
                self._well_x(well_indices[top.well_name]), self._depth_y(top.depth_m)
            )

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), self.palette().base())
        if not self._well_names:
            painter.setPen(self.palette().text().color())
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No formation tops")
            return

        axis_pen = QPen(self.palette().mid().color(), 1.0)
        painter.setPen(axis_pen)
        for index, well_name in enumerate(self._well_names):
            x = self._well_x(index)
            painter.drawLine(
                QPointF(x, self._TOP), QPointF(x, self.height() - self._BOTTOM)
            )
            painter.drawText(
                int(x - 55), 5, 110, 25, Qt.AlignmentFlag.AlignCenter, well_name
            )

        minimum, maximum = self._view_depth_range
        painter.drawText(4, int(self._TOP + 5), f"{minimum:g} m")
        painter.drawText(4, int(self.height() - self._BOTTOM), f"{maximum:g} m")

        by_well_and_formation = {
            (top.well_name, top.formation_name): top for top in self._tops
        }
        for left_index in range(len(self._well_names) - 1):
            left_well = self._well_names[left_index]
            right_well = self._well_names[left_index + 1]
            formations = sorted(
                {top.formation_name for top in self._tops if top.well_name == left_well}
                & {top.formation_name for top in self._tops if top.well_name == right_well}
            )
            for formation in formations:
                left_top = by_well_and_formation[(left_well, formation)]
                right_top = by_well_and_formation[(right_well, formation)]
                painter.setPen(QPen(QColor(left_top.color), 1.4))
                painter.drawLine(
                    QPointF(self._well_x(left_index), self._depth_y(left_top.depth_m)),
                    QPointF(
                        self._well_x(left_index + 1),
                        self._depth_y(right_top.depth_m),
                    ),
                )

        for top, point in self._top_points():
            if (
                point.y() < self._TOP - 5
                or point.y() > self.height() - self._BOTTOM + 5
            ):
                continue
            color = QColor(top.color)
            painter.setPen(QPen(color.darker(120), 1.0))
            painter.setBrush(color)
            painter.drawEllipse(point, 4.0, 4.0)
            painter.setPen(color.darker(130))
            painter.drawText(point + QPointF(7.0, -4.0), top.formation_name)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt API
        delta = event.angleDelta().y()
        if delta == 0:
            return
        minimum, maximum = self._view_depth_range
        span = maximum - minimum
        if span <= 0.0:
            return
        anchor = self._depth_at_y(event.position().y())
        ratio = (anchor - minimum) / span
        factor = 0.8 if delta > 0 else 1.25
        new_span = max(1e-6, span * factor)
        self._view_depth_range = (
            anchor - ratio * new_span,
            anchor + (1.0 - ratio) * new_span,
        )
        self.update()
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() is Qt.MouseButton.LeftButton:
            self._drag_start_y = event.position().y()
            self._drag_start_range = self._view_depth_range
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if self._drag_start_y is not None:
            minimum, maximum = self._drag_start_range
            shift = -(event.position().y() - self._drag_start_y) / self._plot_height() * (
                maximum - minimum
            )
            self._view_depth_range = (minimum + shift, maximum + shift)
            self.update()
            event.accept()
            return

        nearest: FormationTop | None = None
        nearest_distance = 9.0
        position = event.position()
        for top, point in self._top_points():
            distance = math.hypot(point.x() - position.x(), point.y() - position.y())
            if distance < nearest_distance:
                nearest = top
                nearest_distance = distance
        if nearest != self._hovered_top:
            self._hovered_top = nearest
            if nearest is None:
                self.hovered_top_changed.emit("", "", math.nan)
            else:
                self.hovered_top_changed.emit(
                    nearest.well_name, nearest.formation_name, nearest.depth_m
                )

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() is Qt.MouseButton.LeftButton and self._drag_start_y is not None:
            self._drag_start_y = None
            self.unsetCursor()
            event.accept()


__all__ = ["FormationTopsPreviewWidget"]
