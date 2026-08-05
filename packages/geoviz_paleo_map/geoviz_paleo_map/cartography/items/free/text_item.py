"""FreeTextItem — paper text annotation with mm font size and word wrap."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QPen

from geoviz_paleo_map.cartography.items.free.base import FreeGraphicsItem, mm_font

_ALIGN = {
    "left": Qt.AlignmentFlag.AlignLeft,
    "center": Qt.AlignmentFlag.AlignHCenter,
    "right": Qt.AlignmentFlag.AlignRight,
}


class FreeTextItem(FreeGraphicsItem):
    """Text at ``pos``; optional wrap width (record geometry ``w``).

    The item rect is always ``(0,0,w,h)``; without a wrap width ``w`` tracks
    the natural text width. Resizing sets the wrap width and reflows; the
    height always follows content + ``font_mm``.
    """

    kind = "text"

    def __init__(self, pos: QPointF, text: str = "", wrap_w: float | None = None, parent=None) -> None:
        super().__init__(QRectF(0, 0, 40.0, 8.0), parent)
        self.setPos(pos)
        self.text = text
        self.align = "left"
        self._wrap_w = wrap_w
        self._reflow()

    # -- layout ---------------------------------------------------------

    def _reflow(self) -> None:
        fm = QFontMetricsF(mm_font(self.font_mm))
        flags = int(Qt.TextFlag.TextWordWrap)
        if self._wrap_w:
            br = fm.boundingRect(
                QRectF(0, 0, self._wrap_w, 10000.0), flags, self.text or " "
            )
            w, h = self._wrap_w, max(br.height(), self.font_mm)
        else:
            br = fm.boundingRect(self.text or " ")
            w, h = max(br.width(), 5.0), max(br.height(), self.font_mm)
        self.setRect(0, 0, w, h)

    def resize_to(self, new_local: QRectF) -> None:
        """Resize = set wrap width; height reflows to content."""
        if new_local.width() <= 0:
            return
        self._wrap_w = new_local.width()
        self.setPos(self.pos() + new_local.topLeft())
        self._reflow()

    def apply_style(self, style: dict) -> None:
        super().apply_style(style)
        self._reflow()

    # -- paint ----------------------------------------------------------

    def paint_content(self, painter) -> None:
        painter.setFont(mm_font(self.font_mm))
        painter.setPen(QPen(QColor(self.stroke), 0))
        flags = _ALIGN[self.align] | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap
        painter.drawText(self.rect(), int(flags), self.text)

    # -- serialization ----------------------------------------------------

    def geometry_record(self) -> dict:
        geom = {"x": self.pos().x(), "y": self.pos().y()}
        if self._wrap_w:
            geom["w"] = self._wrap_w
        return geom

    def props_record(self) -> dict:
        return {"text": self.text, "align": self.align}

    @classmethod
    def from_normalized(cls, rec: dict) -> "FreeTextItem":
        g = rec["geometry"]
        item = cls(
            QPointF(g["x"], g["y"]),
            text=rec["props"]["text"],
            wrap_w=g.get("w"),
        )
        item.align = rec["props"]["align"]
        item._init_from_normalized(rec)  # apply_style -> _reflow with final font_mm
        return item
