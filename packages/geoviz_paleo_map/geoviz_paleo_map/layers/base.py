"""PaleoLayer abstract base."""
from abc import ABC, abstractmethod

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainter

from geoviz_paleo_map.viewport import PaleoMapViewport


class PaleoLayer(ABC):
    """One rendering pass over the viewport."""

    # Chrome layers (title/north arrow/scale bar/legend) anchor to viewport
    # edges via viewport.width/height. They must paint directly against the
    # real widget viewport — never go through LayerPixmapCache, which uses an
    # oversized 2x buffer that shifts their anchor points off-screen.
    is_chrome: bool = False
    visible: bool = True

    @abstractmethod
    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None: ...

    def reserved_rect(self, viewport: PaleoMapViewport) -> QRectF | None:
        """Screen rect this layer occupies, for label collision avoidance.

        Chrome layers (legend/north arrow/scale bar) override this so region
        labels know to steer clear. Returns None for layers that reserve nothing.
        """
        return None

    def hit_test_polygon(self, screen_pt: QPointF,
                         viewport: PaleoMapViewport) -> str | None:
        """Override for layers that respond to tooltip hover."""
        return None
