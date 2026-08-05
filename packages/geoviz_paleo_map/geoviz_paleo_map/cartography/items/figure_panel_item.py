# packages/geoviz_paleo_map/geoviz_paleo_map/cartography/items/figure_panel_item.py
"""FigurePanelGraphicsItem — embeds a source plot on the paper as a live
proxy or snapshot.

Phase-2, T7 / #251. The composite figure (油藏综合图) lays out several
source plots on one paper sheet. This item is the paper-side slot:

- ``render_mode="live"`` — the host (Workstation CompositeView) attaches a
  ``QGraphicsProxyWidget`` for non-GL source plots (single_well /
  correlation / plane_map). The proxy repaints itself via Qt's parent-child
  mechanism; the item only provides the frame + ``refresh()`` hook.
- ``render_mode="snapshot"`` — the host stores a ``QPixmap`` via
  ``source_widget.grab()`` (GL / engine plots: section, fence_3d). The item
  paints the pixmap in ``paint()``.

The item itself carries no engine/workstation dependency — it only knows
``source_plot_id`` / ``source_plot_type`` / ``render_mode`` and an optional
pixmap. The host wires the actual proxy/pixmap.
"""

from __future__ import annotations

from typing import Literal

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QPixmap
from PySide6.QtWidgets import QGraphicsItem

from geoviz_paleo_map.cartography.items.base_item import LayoutGraphicsItem

# The six Workstation plot types (T9). Kept as a literal here so the item
# shape matches PlotType without importing the Workstation package.
PlotTypeName = Literal[
    "single_well",
    "correlation",
    "section",
    "plane_map",
    "fence_3d",
    "composite",
]

RenderMode = Literal["live", "snapshot"]


class FigurePanelGraphicsItem(LayoutGraphicsItem):
    """Paper slot for a source plot (live proxy or snapshot pixmap)."""

    def __init__(
        self,
        rect_mm: QRectF,
        source_plot_id: str,
        source_plot_type: PlotTypeName = "single_well",
        render_mode: RenderMode = "live",
        parent=None,
    ) -> None:
        super().__init__(rect_mm, parent)
        self.source_plot_id = source_plot_id
        self.source_plot_type = source_plot_type
        self.render_mode = render_mode
        self._snapshot_pixmap: QPixmap | None = None
        self.setBrush(QBrush(QColor("#f8fafc")))
        self.setZValue(10)

    # -- host wiring ----------------------------------------------------

    def set_snapshot_pixmap(self, pixmap: QPixmap | None) -> None:
        """Store the snapshot pixmap (snapshot mode); live mode ignores it."""
        self._snapshot_pixmap = pixmap
        self.update()

    def snapshot_pixmap(self) -> QPixmap | None:
        return self._snapshot_pixmap

    def refresh(self) -> None:
        """Host hook: re-grab the source widget in snapshot mode, repaint in
        live mode (proxy repaints itself; update() is a no-op safety)."""
        self.update()

    # -- paint ----------------------------------------------------------

    def paint(self, painter: QPainter, option, widget=None) -> None:
        # Draw the frame + selection handles first (base behaviour).
        super().paint(painter, option, widget)

        r = self.rect()
        if self.render_mode == "snapshot" and self._snapshot_pixmap is not None:
            # Inset the pixmap slightly inside the frame so the blue border
            # remains visible around the embedded figure.
            target = QRectF(
                r.x() + 1.5, r.y() + 1.5, r.width() - 3.0, r.height() - 3.0
            )
            painter.drawPixmap(
                target, self._snapshot_pixmap, QRectF(self._snapshot_pixmap.rect())
            )
        elif self.render_mode == "snapshot":
            # Snapshot mode but no pixmap yet: placeholder.
            painter.setPen(QPen(QColor("#94a3b8"), 1.0, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(r.adjusted(1.5, 1.5, -1.5, -1.5))
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(
                r,
                Qt.AlignmentFlag.AlignCenter,
                f"面板 · {self.source_plot_id[:12]}",
            )
        else:
            # Live mode: host attaches a QGraphicsProxyWidget; draw a thin
            # label so the slot is identifiable before the proxy is added.
            painter.setPen(QColor("#64748b"))
            painter.drawText(
                r,
                Qt.AlignmentFlag.AlignCenter,
                f"图件面板 · {self.source_plot_type}",
            )

    def itemChange(self, change, value):
        # Keep the frame crisp when moved/resized; base handles handles.
        return super().itemChange(change, value)


def panel_rect_mm(x: float, y: float, w: float, h: float) -> QRectF:
    """Convenience builder for a panel rect in mm paper coordinates."""
    return QRectF(x, y, w, h)
