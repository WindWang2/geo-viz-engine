"""PaleoLayer abstract base."""
from abc import ABC, abstractmethod

from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainter

from geoviz_paleo_map.viewport import PaleoMapViewport


class PaleoLayer(ABC):
    """One rendering pass over the viewport."""

    @abstractmethod
    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None: ...

    def hit_test_polygon(self, screen_pt: QPointF,
                         viewport: PaleoMapViewport) -> str | None:
        """Override for layers that respond to tooltip hover."""
        return None
