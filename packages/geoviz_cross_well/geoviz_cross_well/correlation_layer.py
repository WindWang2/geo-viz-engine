from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainter, QColor, QPen, QPainterPath
from PySide6.QtWidgets import QWidget

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from geoviz_well_log.renderer.canvas import WellLogCanvas
    from geoviz_well_log.connection_overlay import ConnectionOverlay

from .picks_model import HorizonPick
from .tops_model import _FORMATION_PALETTE


def _depth_to_y(canvas: Any, overlay: ConnectionOverlay, depth: float) -> float:
    return overlay.depth_to_y(canvas, depth)


def _formation_color(name: str) -> str:
    return _FORMATION_PALETTE[sum(ord(c) for c in name) % len(_FORMATION_PALETTE)]


class CorrelationLayer:
    @staticmethod
    def paint(
        painter: QPainter,
        picks: list[HorizonPick],
        canvases: list,
        well_names: list[str],
        overlay: ConnectionOverlay,
        selected_pick_id: str | None = None,
        hover_pick_id: str | None = None,
    ) -> None:
        if not picks or not canvases:
            return

        name_to_canvas: dict[str, object] = {}
        for i, c in enumerate(canvases):
            if i < len(well_names):
                name_to_canvas[well_names[i]] = c

        for pick in picks:
            connected = pick.connected_wells()
            if len(connected) < 2:
                CorrelationLayer._paint_pick_dots(
                    painter, pick, name_to_canvas, overlay, selected_pick_id, hover_pick_id
                )
                continue

            color = QColor(_formation_color(pick.formation_name))
            is_dtw = pick.source == "dtw"
            is_selected = pick.pick_id == selected_pick_id
            is_hover = pick.pick_id == hover_pick_id

            if is_dtw:
                pen = QPen(color, 1.5, Qt.PenStyle.DashLine)
                color.setAlpha(100)
            elif is_selected or is_hover:
                pen = QPen(color, 3.0)
            else:
                pen = QPen(color, 2.0)
            painter.setPen(pen)
            painter.setBrush(color if not is_dtw else QColor(0, 0, 0, 0))

            for idx in range(len(connected) - 1):
                w1 = connected[idx]
                w2 = connected[idx + 1]
                c1 = name_to_canvas.get(w1)
                c2 = name_to_canvas.get(w2)
                if c1 is None or c2 is None:
                    continue
                d1 = pick.depth_for_well(w1)
                d2 = pick.depth_for_well(w2)
                if d1 is None or d2 is None:
                    continue

                y1 = _depth_to_y(c1, overlay, d1)
                y2 = _depth_to_y(c2, overlay, d2)

                src_right = overlay._canvas_right(c1)
                tgt_left = overlay._canvas_left(c2)
                span = tgt_left - src_right

                cp1 = QPointF(src_right + span / 3, y1)
                cp2 = QPointF(src_right + 2 * span / 3, y2)

                path = QPainterPath()
                path.moveTo(src_right, y1)
                path.cubicTo(cp1, cp2, QPointF(tgt_left, y2))
                painter.drawPath(path)

            CorrelationLayer._paint_pick_dots(
                painter, pick, name_to_canvas, overlay, selected_pick_id, hover_pick_id
            )

    @staticmethod
    def _paint_pick_dots(
        painter: QPainter,
        pick: HorizonPick,
        name_to_canvas: dict[str, object],
        overlay: ConnectionOverlay,
        selected_pick_id: str | None,
        hover_pick_id: str | None,
    ) -> None:
        color = QColor(_formation_color(pick.formation_name))
        is_dtw = pick.source == "dtw"
        is_selected = pick.pick_id == selected_pick_id
        radius = 6 if is_selected else 4

        if is_dtw:
            fill = QColor(color)
            fill.setAlpha(100)
            painter.setBrush(fill)
            painter.setPen(QPen(color, 1.0, Qt.PenStyle.DashLine))
        else:
            painter.setBrush(color)
            painter.setPen(QPen(color.darker(120), 1.5))

        for well, depth in pick.well_depths:
            if depth is None:
                continue
            canvas = name_to_canvas.get(well)
            if canvas is None:
                continue
            y = _depth_to_y(canvas, overlay, depth)
            x = overlay._canvas_right(canvas)
            painter.drawEllipse(QPointF(x, y), radius, radius)
