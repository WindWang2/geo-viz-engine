"""Multi-Well Section Canvas for Cross-Well Stratigraphic Correlation."""
from __future__ import annotations

from typing import List, Optional
from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QToolTip, QWidget

from geoviz_well_log.models import WellLogData
from geoviz_well_log.qpainter_builder import build_qpainter_tracks
from geoviz_well_log.renderer.track_base import BaseTrack
from .datum_transformer import DatumTransformer
from .inter_well_link import FaciesQuad, HorizonLink, paint_facies_quad, paint_horizon_link


class WellSectionCanvas(QWidget):
    """2D QPainter canvas displaying a sequence of wells with inter-well correlation."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(True)
        self.setMouseTracking(True)

        self._wells: List[WellLogData] = []
        self._well_tracks: List[List[BaseTrack]] = []
        self._inter_well_spacing: int = 180
        self._show_facies_fills: bool = True
        self._transformer = DatumTransformer()

        self._cache_dirty: bool = True
        self._static_cache: Optional[QPixmap] = None

    @property
    def transformer(self) -> DatumTransformer:
        return self._transformer

    def set_wells(self, wells: List[WellLogData]) -> None:
        self._wells = list(wells)
        self._well_tracks = [build_qpainter_tracks(w) for w in self._wells]

        # Calculate global depth bounds
        all_min = []
        all_max = []
        for w in self._wells:
            if hasattr(w, "top_depth") and w.top_depth is not None:
                all_min.append(w.top_depth)
            elif hasattr(w, "depth_min") and w.depth_min is not None:
                all_min.append(w.depth_min)

            if hasattr(w, "bottom_depth") and w.bottom_depth is not None:
                all_max.append(w.bottom_depth)
            elif hasattr(w, "depth_max") and w.depth_max is not None:
                all_max.append(w.depth_max)

        self._transformer.global_min_depth = min(all_min, default=0.0)
        self._transformer.global_max_depth = max(all_max, default=1000.0)

        # Update datum depths for available stratigraphy
        datum_map = {}
        for w in self._wells:
            w_id = getattr(w, "well_name", getattr(w, "well_id", str(w)))
            if hasattr(w, "stratigraphy") and w.stratigraphy:
                for strat in w.stratigraphy:
                    datum_map[strat.name] = strat.top
            elif hasattr(w, "formation_tops") and w.formation_tops:
                for top_item in w.formation_tops:
                    datum_map[getattr(top_item, "name", "")] = getattr(top_item, "top", 0.0)

        self._transformer.datum_depths = datum_map

        self._cache_dirty = True
        self.update()

    def set_datum_mode(self, mode: str, datum_name: str = "") -> None:
        self._transformer.mode = mode
        self._transformer.datum_name = datum_name
        self._cache_dirty = True
        self.update()

    def set_inter_well_spacing(self, spacing: int) -> None:
        self._inter_well_spacing = max(50, spacing)
        self._cache_dirty = True
        self.update()

    def set_show_facies_fills(self, show: bool) -> None:
        self._show_facies_fills = show
        self._cache_dirty = True
        self.update()

    def _calculate_well_x_offsets(self) -> List[tuple[float, float]]:
        """Return list of (x_start, total_width) for each well."""
        offsets = []
        cur_x = 20.0
        for tracks in self._well_tracks:
            visible_w = sum(t.width for t in tracks if getattr(t, "_visible", True))
            offsets.append((cur_x, visible_w))
            cur_x += visible_w + self._inter_well_spacing
        return offsets

    def paint_all(self, painter: QPainter) -> None:
        if not self._well_tracks:
            painter.setPen(QColor(120, 130, 145))
            painter.setFont(QFont("SansSerif", 12))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "未加载多井对比数据")
            return

        h = self.height()
        header_h = 56.0
        self._transformer.header_height = header_h
        content_h = max(100.0, h - header_h)

        depth_span = max(1.0, self._transformer.global_max_depth - self._transformer.global_min_depth)
        self._transformer.scale_y = content_h / depth_span

        offsets = self._calculate_well_x_offsets()
        if offsets:
            total_w = int(offsets[-1][0] + offsets[-1][1] + 20.0)
            self.setMinimumWidth(total_w)

        # 1. Render Facies Quad Fills & Horizon Links across adjacent wells first (background layer)
        if len(self._wells) >= 2:
            for k in range(len(self._wells) - 1):
                w_left_id = getattr(self._wells[k], "well_name", str(k))
                w_right_id = getattr(self._wells[k + 1], "well_name", str(k + 1))
                x1_right = offsets[k][0] + offsets[k][1]
                x2_left = offsets[k + 1][0]

                # Collect and render shared stratigraphy horizon links
                tracks_left = self._well_tracks[k]
                tracks_right = self._well_tracks[k + 1]

                # Find stratigraphic tracks
                strat_left = next((t for t in tracks_left if hasattr(t, "intervals")), None)
                strat_right = next((t for t in tracks_right if hasattr(t, "intervals")), None)

                if strat_left and strat_right and hasattr(strat_left, "intervals") and hasattr(strat_right, "intervals"):
                    right_dict = {item.name: item for item in strat_right.intervals}
                    for item_l in strat_left.intervals:
                        if item_l.name in right_dict:
                            item_r = right_dict[item_l.name]
                            y_l = self._transformer.get_depth_y(w_left_id, item_l.top)
                            y_r = self._transformer.get_depth_y(w_right_id, item_r.top)
                            link = HorizonLink(
                                name=item_l.name,
                                x_left=x1_right,
                                y_left=y_l,
                                x_right=x2_left,
                                y_right=y_r,
                            )
                            paint_horizon_link(painter, link)

                            # If facies fill enabled
                            if self._show_facies_fills:
                                y1_l = y_l
                                y2_l = self._transformer.get_depth_y(w_left_id, item_l.bottom)
                                y1_r = y_r
                                y2_r = self._transformer.get_depth_y(w_right_id, item_r.bottom)
                                quad = FaciesQuad(
                                    facies_name=item_l.name,
                                    x_left=x1_right,
                                    y1_left=y1_l,
                                    y2_left=y2_l,
                                    x_right=x2_left,
                                    y1_right=y1_r,
                                    y2_right=y2_r,
                                )
                                paint_facies_quad(painter, quad)

        # 2. Render each well's tracks
        for idx, (well, tracks) in enumerate(zip(self._wells, self._well_tracks)):
            x_off, well_w = offsets[idx]
            well_name = getattr(well, "well_name", f"Well-{idx+1}")

            # Draw Well Title Header
            header_rect = QRectF(x_off, 0, well_w, 24)
            painter.fillRect(header_rect, QColor(31, 58, 107))
            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.setFont(QFont("SansSerif", 9, QFont.Weight.Bold))
            painter.drawText(header_rect, Qt.AlignmentFlag.AlignCenter, f"井名: {well_name}")

            # Render individual tracks
            cur_tx = x_off
            for track in tracks:
                if not getattr(track, "_visible", True):
                    continue
                full_rect = QRectF(cur_tx, 24, track.width, h - 24)
                track.export_render(painter, full_rect, canvas_header_height=32)
                cur_tx += track.width

        # 3. If in datum_shift mode, render horizontal Datum Reference Line
        if self._transformer.mode == "datum_shift" and self._transformer.datum_name:
            y_dat = self._transformer.y_datum
            painter.setPen(QPen(QColor(220, 50, 50), 2, Qt.PenStyle.DashDotLine))
            painter.drawLine(0, int(y_dat), int(self.width()), int(y_dat))

            painter.setFont(QFont("SansSerif", 9, QFont.Weight.Bold))
            painter.setPen(QPen(QColor(180, 30, 30)))
            painter.drawText(
                QRectF(10, y_dat - 20, 300, 18),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"⚓ 拉平基准层: {self._transformer.datum_name}",
            )

    def paintEvent(self, event) -> None:
        dpr = self.devicePixelRatioF()
        w = int(self.width() * dpr)
        h = int(self.height() * dpr)

        if self._cache_dirty or self._static_cache is None or self._static_cache.size() != QSize(w, h):
            self._static_cache = QPixmap(w, h)
            self._static_cache.setDevicePixelRatio(dpr)
            self._static_cache.fill(QColor("#ffffff"))
            cache_painter = QPainter(self._static_cache)
            self.paint_all(cache_painter)
            cache_painter.end()
            self._cache_dirty = False

        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        painter.drawPixmap(0, 0, self._static_cache)
        painter.end()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        if not self._wells or pos.y() < 56:
            QToolTip.hideText()
            return

        offsets = self._calculate_well_x_offsets()
        x = pos.x()
        selected_well_idx = -1
        for idx, (x_off, well_w) in enumerate(offsets):
            if x_off <= x <= x_off + well_w:
                selected_well_idx = idx
                break

        if selected_well_idx != -1:
            well = self._wells[selected_well_idx]
            well_name = getattr(well, "well_name", f"Well-{selected_well_idx+1}")
            depth = self._transformer.inverse_y_to_depth(well_name, pos.y())
            QToolTip.showText(
                self.mapToGlobal(pos.toPoint()),
                f"📍 井名: {well_name}\n深度: {depth:.2f} m",
                self,
            )
        else:
            QToolTip.hideText()
        super().mouseMoveEvent(event)
