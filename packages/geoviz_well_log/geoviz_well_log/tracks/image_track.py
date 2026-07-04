"""Single-Well Image Track for Core Photos and FMI Borehole Imaging."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
import os
import numpy as np

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QBrush, QPixmap, QImage

from geoviz_well_log.renderer.track_base import BaseTrack


@dataclass
class CorePhotoSegment:
    depth_top: float
    depth_bottom: float
    image_path: str = ""
    title: str = "Core Photo"
    pixmap: Optional[QPixmap] = None

    def load_pixmap(self):
        if self.pixmap is None and self.image_path and os.path.exists(self.image_path):
            self.pixmap = QPixmap(self.image_path)

@dataclass
class BoreholeImageSegment:
    depth_top: float
    depth_bottom: float
    data_matrix: Optional[np.ndarray] = None  # 2D array [N_depth, N_azimuth]
    colormap_name: str = "thermal"

class ImageTrack(BaseTrack):
    """Track for displaying depth-mapped core photo segments and FMI borehole images."""

    def __init__(self, name: str = "Core Photos", width: int = 160, parent=None):
        super().__init__(label=name, width=width, parent=parent)
        self.core_photos: List[CorePhotoSegment] = []
        self.fmi_segments: List[BoreholeImageSegment] = []
        self._min_depth = 2000.0
        self._max_depth = 2100.0

    def set_depth_range(self, min_depth: float, max_depth: float):
        self._min_depth = min_depth
        self._max_depth = max_depth
        self.update()

    def add_core_photo(self, photo: CorePhotoSegment):
        photo.load_pixmap()
        self.core_photos.append(photo)

    def add_fmi_segment(self, fmi: BoreholeImageSegment):
        self.fmi_segments.append(fmi)

    def paint_content(self, painter: QPainter, rect: QRectF):
        """Render photo segments in depth viewport rect."""
        min_depth, max_depth = self._min_depth, self._max_depth
        depth_span = max(1e-6, max_depth - min_depth)

        def depth_to_y(d: float) -> float:
            return rect.top() + (d - min_depth) / depth_span * rect.height()

        painter.save()
        painter.setClipRect(rect)

        # Background
        painter.fillRect(rect, QColor(245, 247, 250))

        # Paint Core Photo Segments
        for photo in self.core_photos:
            if photo.depth_bottom < min_depth or photo.depth_top > max_depth:
                continue

            y_top = depth_to_y(photo.depth_top)
            y_bottom = depth_to_y(photo.depth_bottom)
            h = max(2.0, y_bottom - y_top)

            photo_rect = QRectF(rect.left() + 2, y_top, rect.width() - 4, h)

            if photo.pixmap and not photo.pixmap.isNull():
                painter.drawPixmap(photo_rect.toRect(), photo.pixmap)
            else:
                # Placeholder rendering
                painter.fillRect(photo_rect, QColor(220, 230, 245))
                painter.setPen(QPen(QColor(31, 102, 212), 1, Qt.DashLine))
                painter.drawRect(photo_rect)

                painter.setPen(QColor(88, 104, 120))
                painter.setFont(QFont("SansSerif", 8))
                label = f"📷 {photo.title}\n({photo.depth_top:.1f}m - {photo.depth_bottom:.1f}m)"
                painter.drawText(photo_rect, Qt.AlignmentFlag.AlignCenter, label)

            # Border
            painter.setPen(QPen(QColor(31, 102, 212), 1.5))
            painter.drawRect(photo_rect)

        painter.restore()

