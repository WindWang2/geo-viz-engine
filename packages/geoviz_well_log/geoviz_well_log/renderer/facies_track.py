from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter

from ..models import IntervalItem, FaciesData
from ..pattern_map import FACIES_COLORS
from .interval_track import IntervalTrack
from .track_base import BaseTrack


class FaciesTrack(BaseTrack):
    """Facies column with color fills. Supports single and nested display."""

    def __init__(self, facies_data: FaciesData, label: str = "Facies",
                 width: int = 80, nested: bool = False,
                 header_height: int = 32, parent=None):
        super().__init__(label=label, width=width, header_height=header_height,
                         parent=parent)
        self._facies_data = facies_data
        self._nested = nested

    def _paint_column(self, painter: QPainter, rect: QRectF, intervals: list[IntervalItem]):
        colors = {iv.name: FACIES_COLORS.get(iv.name, "#e0e0e0") for iv in intervals}
        inner = IntervalTrack(intervals=intervals, width=int(rect.width()), colors=colors)
        inner.set_depth_range(self.depth_top, self.depth_bottom)
        inner.paint_content(painter, rect)

    def paint_content(self, painter: QPainter, rect: QRectF):
        # Horizontal grid lines (ECharts splitLine parity)
        self.paint_grid(painter, rect)

        if self._nested:
            col_width = rect.width() / 3
            phase_rect = QRectF(rect.left(), rect.top(), col_width, rect.height())
            sub_rect = QRectF(rect.left() + col_width, rect.top(), col_width, rect.height())
            micro_rect = QRectF(rect.left() + 2 * col_width, rect.top(), col_width, rect.height())

            if self._facies_data.phase:
                self._paint_column(painter, phase_rect, self._facies_data.phase)
            if self._facies_data.sub_phase:
                self._paint_column(painter, sub_rect, self._facies_data.sub_phase)
            if self._facies_data.micro_phase:
                self._paint_column(painter, micro_rect, self._facies_data.micro_phase)
        else:
            if self._facies_data.micro_phase:
                self._paint_column(painter, rect, self._facies_data.micro_phase)
            elif self._facies_data.sub_phase:
                self._paint_column(painter, rect, self._facies_data.sub_phase)
            elif self._facies_data.phase:
                self._paint_column(painter, rect, self._facies_data.phase)
