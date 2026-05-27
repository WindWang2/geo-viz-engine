"""MapLayer abstract base."""
from abc import ABC, abstractmethod

from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainter

from geoviz_map.viewport import MapViewport


class MapLayer(ABC):
    """One rendering pass over the viewport.

    Layers are painted in registration order; hit-test runs reverse order
    (topmost first), so interactive layers should be appended last.
    """

    @abstractmethod
    def paint(self, painter: QPainter, viewport: MapViewport) -> None: ...

    def hit_test(self, screen_pt: QPointF,
                 viewport: MapViewport) -> str | None:
        """Override for interactive layers. Default: no hit."""
        return None
