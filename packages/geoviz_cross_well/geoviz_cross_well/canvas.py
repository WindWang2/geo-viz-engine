from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QPointF, QEvent, QObject
from PySide6.QtGui import QPainter, QColor, QPen, QPolygonF, QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout

import numpy as np

from geoviz_well_log.cross_well_widget import CrossWellWidget
from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_well_log.renderer.curve_track import CurveTrack

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
        self._tops_visible = True

        self._parent_canvas = parent
        self._hover_well_idx: int | None = None
        self._hover_snapped_depth: float | None = None
        self._active_curve: str = "GR"

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

    def set_hover_snapped(self, well_idx: int | None, depth: float | None, curve_name: str):
        self._hover_well_idx = well_idx
        self._hover_snapped_depth = depth
        self._active_curve = curve_name
        self.update()

    def set_depth_domain(self, domain: str):
        self._depth_domain = domain
        self.update()

    def set_seismic_tie(self, tie: SeismicTie | None):
        self._seismic_tie = tie
        self.update()

    def set_tops_visible(self, visible: bool):
        self._tops_visible = bool(visible)
        self.update()

    def paintEvent(self, event):
        if self._widget is None or self._tops_model is None or self._picks_model is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._paint_tops(painter)
        self._paint_ties(painter)
        self._paint_hover_snap(painter)
        if self._depth_domain == "TWT" and self._seismic_tie is not None:
            self._paint_twt_axis(painter)
        painter.end()

    def _paint_hover_snap(self, painter: QPainter):
        if self._hover_well_idx is None or self._hover_snapped_depth is None or not self._active_curve:
            return
        
        i = self._hover_well_idx
        if i >= len(self._widget._canvases) or i >= len(self._widget._well_names):
            return
            
        canvas = self._widget._canvases[i]
        overlay = self._widget._overlay
        left = overlay._canvas_left(canvas)
        right = overlay._canvas_right(canvas)
        y = overlay.depth_to_y(canvas, self._hover_snapped_depth)
        
        # 1. Draw horizontal snapped preview line
        pen = QPen(QColor(31, 102, 212, 180), 1.0, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(QPointF(left, y), QPointF(right, y))
        
        # 2. Draw highlighted dot on the active curve line
        if self._parent_canvas is not None:
            curve_data = self._parent_canvas._extract_curve(canvas, preferred=(self._active_curve,))
            if curve_data is not None:
                depths, values = curve_data
                idx = np.argmin(np.abs(depths - self._hover_snapped_depth))
                val = values[idx]
                
                from geoviz_well_log.renderer.curve_track import CurveTrack
                for track in canvas.tracks:
                    if isinstance(track, CurveTrack):
                        for curve in track._curves:
                            if curve.name.upper() == self._active_curve.upper():
                                track_x = track.mapTo(self._widget, QPointF(0, 0)).x()
                                track_rect = QRectF(track_x, 0, track.width(), canvas.height())
                                x = track._value_to_x(val, curve.display_range, track_rect)
                                
                                painter.setBrush(QColor(31, 102, 212))
                                painter.setPen(QPen(Qt.GlobalColor.white, 1.5))
                                painter.drawEllipse(QPointF(x, y), 4.5, 4.5)
                                break


    def _paint_tops(self, painter: QPainter):
        if not self._tops_visible:
            return
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
        self._canvas = canvas
        super().__init__(canvas)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if not hasattr(self, "_canvas") or self._canvas is None:
            return False
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

        # Export tops/picks (screen-visible interpretation) into composite
        # exports — the workbench exports through CrossWellWidget.
        self._widget.set_interpretation_painter(self._paint_interpretation_composite)
        
        # Repaint PickingOverlay when any underlying well canvas zooms or pans
        self._widget.canvas_depth_changed.connect(self._overlay.update)

        self._pick_mode = False
        self._active_formation: str | None = None
        self._active_pick_id: str | None = None
        self._active_curve = "GR"
        self._snap_type = "none"
        self._snap_window_m = 1.5
        self._curve_groups = {
            "AC/GR": ["AC", "GR"],
            "RT/RXO": ["RT", "RXO"]
        }
        self._hover_well_idx = None
        self._hover_snapped_depth = None
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

    def set_tops_visible(self, visible: bool):
        self._overlay.set_tops_visible(visible)

    def _paint_interpretation_composite(self, painter: QPainter):
        """Paint tops + picks into the composite export painter.

        Invoked by CrossWellWidget._paint_composite in a painter whose world
        transform maps widget coordinates to composite coordinates, so the
        exact same drawing code as the on-screen PickingOverlay produces
        screen-aligned output (labels, depths and x offsets all included).
        """
        self._overlay._paint_tops(painter)
        self._overlay._paint_ties(painter)

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

    @property
    def active_formation(self) -> str | None:
        return self._active_formation

    @active_formation.setter
    def active_formation(self, value: str | None):
        self._active_formation = value

    @property
    def active_curve(self) -> str:
        return self._active_curve

    @active_curve.setter
    def active_curve(self, value: str):
        self._active_curve = value
        self._overlay.set_hover_snapped(self._hover_well_idx, self._hover_snapped_depth, value)

    @property
    def snap_type(self) -> str:
        return self._snap_type

    @snap_type.setter
    def snap_type(self, value: str):
        self._snap_type = value

    @property
    def snap_window_m(self) -> float:
        return self._snap_window_m

    @snap_window_m.setter
    def snap_window_m(self, value: float):
        self._snap_window_m = value

    @property
    def curve_groups(self) -> dict[str, list[str]]:
        return self._curve_groups

    @curve_groups.setter
    def curve_groups(self, value: dict[str, list[str]]):
        self._curve_groups = value

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._overlay.setGeometry(self.rect())
        self._overlay.raise_()


    def _get_snapped_depth(self, canvas: WellLogCanvas, clicked_depth: float) -> float:
        if self._snap_type == "none" or not self._active_curve:
            return clicked_depth

        # Extract depths and values of the active curve for the targeted well
        curve_data = self._extract_curve(canvas, preferred=(self._active_curve.upper(),))
        if curve_data is None:
            return clicked_depth

        depths, values = curve_data  # numpy arrays
        
        # Filter points within search window [clicked_depth - window, clicked_depth + window]
        mask = (depths >= clicked_depth - self._snap_window_m) & (depths <= clicked_depth + self._snap_window_m)
        if not np.any(mask):
            return clicked_depth
            
        window_depths = depths[mask]
        window_values = values[mask]

        if len(window_values) == 0:
            return clicked_depth

        # Find index of extremum
        if self._snap_type == "max":
            idx = np.argmax(window_values)
        elif self._snap_type == "min":
            idx = np.argmin(window_values)
        else:
            return clicked_depth

        return float(window_depths[idx])

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

        # Snap the depth using current settings
        depth = self._get_snapped_depth(canvas, depth)

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
        canvas, well_idx = self._canvas_at(pos)
        if canvas is not None:
            local_pos = canvas.mapFrom(self._widget, pos)
            raw_depth = CrossWellWidget._y_to_depth(canvas, local_pos.y())
            if raw_depth is not None:
                self._hover_well_idx = well_idx
                self._hover_snapped_depth = self._get_snapped_depth(canvas, raw_depth)
            else:
                self._hover_well_idx = None
                self._hover_snapped_depth = None
        else:
            self._hover_well_idx = None
            self._hover_snapped_depth = None
            
        self._overlay.set_hover_snapped(self._hover_well_idx, self._hover_snapped_depth, self._active_curve)

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

    def _pick_at(self, pos, tolerance_px: float = 10.0) -> HorizonPick | None:
        """Return the pick nearest to ``pos`` within ``tolerance_px`` screen pixels.

        The tolerance is expressed in screen pixels and converted to depth
        units through the canvas's current depth scale, so hit-testing stays
        constant on screen regardless of zoom level (a fixed depth-unit
        tolerance made every click hit at <10 m spans and made picks
        un-clickable at ~2 km spans). When several picks fall inside the
        tolerance the closest one wins.
        """
        best: tuple[float, HorizonPick] | None = None
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

            header_h = max((t.header_height for t in canvas.tracks), default=56)
            content_h = canvas.height() - header_h
            span = canvas.tracks[0].depth_span
            if content_h <= 0 or span <= 0:
                continue
            depth_tol = tolerance_px * span / content_h

            for pick in self._picks_model.picks_for_well(well):
                pick_depth = pick.depth_for_well(well)
                if pick_depth is None:
                    continue
                delta = abs(pick_depth - depth)
                if delta <= depth_tol and (best is None or delta < best[0]):
                    best = (delta, pick)
        return best[1] if best is not None else None

    def _extract_curve(self, canvas: WellLogCanvas, preferred: tuple[str, ...] = ("GR", "SP", "RT")) -> tuple[np.ndarray, np.ndarray] | None:
        """Return (depths, values) from the first CurveTrack matching `preferred` curve names, else first available curve."""
        first_curve = None
        for track in canvas.tracks:
            if isinstance(track, CurveTrack):
                for curve in track._curves:
                    if first_curve is None:
                        first_curve = curve
                    if curve.name.upper() in preferred:
                        depths = np.asarray(track._sorted_depths.get(curve.name, curve.depth), dtype=float)
                        values = np.asarray(track._sorted_values.get(curve.name, curve.values), dtype=float)
                        return depths, values
        if first_curve is not None:
            for track in canvas.tracks:
                if isinstance(track, CurveTrack):
                    depths = np.asarray(track._sorted_depths.get(first_curve.name, first_curve.depth), dtype=float)
                    values = np.asarray(track._sorted_values.get(first_curve.name, first_curve.values), dtype=float)
                    return depths, values
        return None

    def propagate_pick_via_dtw(
        self,
        ref_well: str,
        ref_depth: float,
        formation: str,
        band_radius: int | None = None,
        progress_callback=None,
    ) -> list[str]:
        """Propagate a pick from `ref_well` at `ref_depth` to every other well via DTW.

        Returns the list of newly created DTW ghost pick IDs.

        ``progress_callback`` receives ``(well_index, well_total)`` after each
        target well finishes, so callers can drive a progress bar.
        """
        names = self._widget._well_names
        canvases = self._widget._canvases
        if ref_well not in names:
            return []
        ref_idx = names.index(ref_well)
        ref_data = self._extract_curve(canvases[ref_idx])
        if ref_data is None:
            return []
        ref_depths, ref_values = ref_data

        targets = [(i, c, n) for i, (c, n) in enumerate(zip(canvases, names)) if i != ref_idx]
        total = len(targets)
        created: list[str] = []
        for step, (i, canvas, name) in enumerate(targets, start=1):
            tgt_data = self._extract_curve(canvas)
            if tgt_data is None:
                if progress_callback is not None:
                    progress_callback(step, total)
                continue
            tgt_depths, tgt_values = tgt_data
            result = self._dtw_engine.correlate(
                ref_values, ref_depths,
                tgt_values, tgt_depths,
                band_radius=band_radius,
                ref_depth=ref_depth,
            )
            # An infeasible alignment (curve length difference beyond the
            # Sakoe-Chiba band, or non-finite samples) must not fabricate a
            # ghost pick (#539).
            if not result.feasible:
                if progress_callback is not None:
                    progress_callback(step, total)
                continue
            pick_id = self._picks_model.add_pick(
                formation, name, result.suggested_depth, source="dtw",
            )
            created.append(pick_id)
            if progress_callback is not None:
                progress_callback(step, total)
        return created

