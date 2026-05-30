from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QPointF, QEvent, QObject
from PySide6.QtGui import QPainter, QColor, QPen, QPolygonF, QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout

from geoviz_well_log.cross_well_widget import CrossWellWidget
from geoviz_well_log.renderer.canvas import WellLogCanvas

from .tops_model import FormationTopsModel, FormationTop, _FORMATION_PALETTE
from .picks_model import HorizonPicksModel, HorizonPick, AddPickCmd, ConnectPickCmd
from .correlation_layer import CorrelationLayer
from .dtw_engine import DTWEngine
from .seismic_tie import SeismicTie


class PickingOverlay(QWidget):
    """Transparent overlay painting formation tops, correlation ties, and selection highlights."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self._tops_model: FormationTopsModel | None = None
        self._picks_model: HorizonPicksModel | None = None
        self._widget: CrossWellWidget | None = None
        self._selected_pick_id: str | None = None
        self._hover_pick_id: str | None = None
        self._depth_domain = "MD"
        self._seismic_tie: SeismicTie | None = None

    def set_models(self, tops: FormationTopsModel, picks: HorizonPicksModel, widget: CrossWellWidget):
        self._tops_model = tops
        self._picks_model = picks
        self._widget = widget
        tops.tops_changed.connect(self.update)
        picks.picks_changed.connect(self.update)

    def set_selected(self, pick_id: str | None):
        self._selected_pick_id = pick_id
        self.update()

    def set_hover(self, pick_id: str | None):
        self._hover_pick_id = pick_id
        self.update()

    def set_depth_domain(self, domain: str):
        self._depth_domain = domain
        self.update()

    def set_seismic_tie(self, tie: SeismicTie | None):
        self._seismic_tie = tie
        self.update()

    def paintEvent(self, event):
        if self._widget is None or self._tops_model is None or self._picks_model is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._paint_tops(painter)
        self._paint_ties(painter)
        if self._depth_domain == "TWT" and self._seismic_tie is not None:
            self._paint_twt_axis(painter)
        painter.end()

    def _paint_tops(self, painter: QPainter):
        overlay = self._widget._overlay
        for i, canvas in enumerate(self._widget._canvases):
            if i >= len(self._widget._well_names):
                break
            well = self._widget._well_names[i]
            tops = self._tops_model.tops_for_well(well)
            left = overlay._canvas_left(canvas)
            right = overlay._canvas_right(canvas)

            for top in tops:
                y = overlay.depth_to_y(canvas, top.depth_m)
                color = QColor(top.color)
                pen = QPen(color, 1.5, Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.drawLine(QPointF(left, y), QPointF(right, y))

                painter.setPen(QPen(color, 1.0))
                font = QFont()
                font.setPointSize(8)
                painter.setFont(font)
                painter.drawText(QPointF(left + 4, y - 3), top.formation_name)

    def _paint_ties(self, painter: QPainter):
        overlay = self._widget._overlay
        CorrelationLayer.paint(
            painter,
            self._picks_model.all_picks(),
            self._widget._canvases,
            self._widget._well_names,
            overlay,
            self._selected_pick_id,
            self._hover_pick_id,
        )

    def _paint_twt_axis(self, painter: QPainter):
        """Render TWT axis labels alongside the leftmost canvas depth axis."""
        overlay = self._widget._overlay
        if not self._widget._canvases:
            return
        first_canvas = self._widget._canvases[0]
        if not self._seismic_tie.well_names():
            return
        well = self._seismic_tie.well_names()[0]

        font = QFont()
        font.setPointSize(7)
        painter.setFont(font)
        twt_color = QColor(0, 100, 180)
        painter.setPen(QPen(twt_color, 1.0))

        canvas_left = overlay._canvas_left(first_canvas)
        axis_x = canvas_left - 42

        depth_top = CrossWellWidget._y_to_depth(first_canvas, 0)
        depth_bot = CrossWellWidget._y_to_depth(first_canvas, first_canvas.height())
        if depth_top is None or depth_bot is None:
            return

        depth_range = np.linspace(depth_top, depth_bot, 10)
        twt_values = self._seismic_tie.table_for_well(well).calibration.depth_to_twt(depth_range)

        for depth, twt in zip(depth_range, twt_values):
            y = overlay.depth_to_y(first_canvas, depth)
            painter.drawText(QPointF(axis_x, y + 3), f"{twt:.0f}")

        painter.drawText(QPointF(axis_x, overlay.depth_to_y(first_canvas, depth_top) - 10), "TWT(ms)")


class _PickEventFilter(QObject):
    """Event filter that intercepts mouse events in pick mode."""

    def __init__(self, canvas: CrossWellCanvas):
        super().__init__(canvas)
        self._canvas = canvas

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if not self._canvas._pick_mode:
            return False

        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                return self._canvas._handle_pick_click(event)
            elif event.button() == Qt.MouseButton.RightButton:
                return self._canvas._handle_pick_right_click(event)

        if event.type() == QEvent.Type.MouseMove:
            return self._canvas._handle_pick_hover(event)

        return False


class CrossWellCanvas(QWidget):
    """Composes CrossWellWidget + PickingOverlay with pick mode event filter."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._widget = CrossWellWidget(self)
        self._overlay = PickingOverlay(self)
        self._overlay.setAutoFillBackground(False)

        self._tops_model = FormationTopsModel(self)
        self._picks_model = HorizonPicksModel(self)
        self._dtw_engine = DTWEngine()
        self._seismic_tie = SeismicTie()

        self._overlay.set_models(self._tops_model, self._picks_model, self._widget)
        self._overlay.set_seismic_tie(self._seismic_tie)

        self._pick_mode = False
        self._active_formation: str | None = None
        self._active_pick_id: str | None = None
        self._event_filter = _PickEventFilter(self)
        self._widget.installEventFilter(self._event_filter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._widget, 1)

    @property
    def widget(self) -> CrossWellWidget:
        return self._widget

    @property
    def tops_model(self) -> FormationTopsModel:
        return self._tops_model

    @property
    def picks_model(self) -> HorizonPicksModel:
        return self._picks_model

    @property
    def dtw_engine(self) -> DTWEngine:
        return self._dtw_engine

    @property
    def seismic_tie(self) -> SeismicTie:
        return self._seismic_tie

    @property
    def pick_mode(self) -> bool:
        return self._pick_mode

    @pick_mode.setter
    def pick_mode(self, value: bool):
        self._pick_mode = value
        if not value:
            self._active_formation = None
            self._active_pick_id = None
        self._widget.setCursor(
            Qt.CursorShape.CrossCursor if value else Qt.CursorShape.ArrowCursor
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._overlay.setGeometry(self.rect())
        self._overlay.raise_()

    def _handle_pick_click(self, event) -> bool:
        pos = event.pos()

        # Check if clicking on an existing DTW ghost pick → accept it
        existing = self._pick_at(pos)
        if existing is not None and existing.source == "dtw":
            self._picks_model.accept_dtw_pick(existing.pick_id)
            return True

        canvas, well_idx = self._canvas_at(pos)
        if canvas is None:
            return False

        well_name = self._widget._well_names[well_idx]
        local_pos = canvas.mapFrom(self._widget, pos)
        depth = CrossWellWidget._y_to_depth(canvas, local_pos.y())
        if depth is None:
            return False

        modifiers = event.modifiers()
        if modifiers & Qt.KeyboardModifier.ShiftModifier and self._active_pick_id:
            self._picks_model.connect_picks(self._active_pick_id, well_name, depth)
        else:
            formation = self._active_formation or f"Horizon-{len(self._picks_model.all_picks()) + 1}"
            self._active_pick_id = self._picks_model.add_pick(formation, well_name, depth)
            self._active_formation = formation

        return True

    def _handle_pick_right_click(self, event) -> bool:
        pos = event.pos()
        pick = self._pick_at(pos)
        if pick is not None:
            if pick.source == "dtw":
                self._picks_model.reject_dtw_pick(pick.pick_id)
            else:
                self._picks_model.delete_pick(pick.pick_id)
            return True
        return False

    def _handle_pick_hover(self, event) -> bool:
        pos = event.pos()
        pick = self._pick_at(pos)
        new_hover = pick.pick_id if pick else None
        if new_hover != self._overlay._hover_pick_id:
            self._overlay.set_hover(new_hover)
        return False

    def _canvas_at(self, pos) -> tuple[WellLogCanvas | None, int]:
        for i, canvas in enumerate(self._widget._canvases):
            canvas_pos = canvas.mapTo(self._widget, canvas.rect().topLeft())
            canvas_rect = canvas.rect().translated(canvas_pos)
            if canvas_rect.contains(pos):
                return canvas, i
        return None, -1

    def _pick_at(self, pos) -> HorizonPick | None:
        for i, canvas in enumerate(self._widget._canvases):
            if i >= len(self._widget._well_names):
                break
            well = self._widget._well_names[i]
            canvas_pos = canvas.mapTo(self._widget, canvas.rect().topLeft())
            canvas_rect = canvas.rect().translated(canvas_pos)
            if not canvas_rect.contains(pos):
                continue
            local_pos = canvas.mapFrom(self._widget, pos)
            depth = CrossWellWidget._y_to_depth(canvas, local_pos.y())
            if depth is None:
                continue
            for pick in self._picks_model.picks_for_well(well):
                pick_depth = pick.depth_for_well(well)
                if pick_depth is not None and abs(pick_depth - depth) < 5.0:
                    return pick
        return None
