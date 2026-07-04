# packages/geoviz_paleo_map/geoviz_paleo_map/cartography/scene.py
"""Paper graphics scene managing paper sizes, printable margins, and grid snapping."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPen, QBrush
from PySide6.QtWidgets import QGraphicsScene

_PAPER_SIZES_MM = {
    "A4": (297.0, 210.0),
    "A3": (420.0, 297.0),
    "A2": (594.0, 420.0),
}

def get_paper_size_mm(page_size: str = "A4", orientation: str = "landscape") -> tuple[float, float]:
    """Return (width_mm, height_mm) for given paper size and orientation."""
    w, h = _PAPER_SIZES_MM.get(page_size.upper(), (297.0, 210.0))
    if orientation.lower() == "portrait":
        return h, w
    return w, h

class PaperGraphicsScene(QGraphicsScene):
    """QGraphicsScene representing a paper sheet in physical mm units."""

    def __init__(
        self,
        page_size: str = "A4",
        orientation: str = "landscape",
        margin_mm: float = 10.0,
        parent=None,
    ):
        super().__init__(parent)
        self._page_size = page_size
        self._orientation = orientation
        self._margin_mm = margin_mm

        self._show_grid = True
        self._grid_size_mm = 10.0

        self._update_scene_bounds()

    def _update_scene_bounds(self):
        w, h = get_paper_size_mm(self._page_size, self._orientation)
        self.setSceneRect(0, 0, w, h)

    def paper_rect(self) -> QRectF:
        w, h = get_paper_size_mm(self._page_size, self._orientation)
        return QRectF(0, 0, w, h)

    def printable_rect(self) -> QRectF:
        w, h = get_paper_size_mm(self._page_size, self._orientation)
        m = self._margin_mm
        return QRectF(m, m, max(1.0, w - 2 * m), max(1.0, h - 2 * m))

    def set_paper_size(self, page_size: str, orientation: str):
        self._page_size = page_size
        self._orientation = orientation
        self._update_scene_bounds()
        self.update()

    def drawBackground(self, painter, rect):
        # Draw paper background
        painter.fillRect(rect, QColor("#e2e8f0"))  # Desktop area gray
        paper = self.paper_rect()
        painter.fillRect(paper, QColor("#ffffff")) # White paper sheet
        
        # Paper border
        painter.setPen(QPen(QColor("#cbd5e1"), 1.0))
        painter.drawRect(paper)

        # Margin dashed line
        m_rect = self.printable_rect()
        margin_pen = QPen(QColor(31, 102, 212, 100), 1.0, Qt.PenStyle.DashLine)
        painter.setPen(margin_pen)
        painter.drawRect(m_rect)
