"""FreeImageItem — paper image / logo with absolute source path.

The geoviz side only holds the source path and loads pixels; copying the
file into the workspace asset directory is the host's job on save (spec
§4.3). Missing files degrade to a placeholder rectangle + filename.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPen, QPixmap

from geoviz_paleo_map.cartography.items.free.base import FreeGraphicsItem, mm_font


class FreeImageItem(FreeGraphicsItem):
    kind = "image"

    def __init__(self, rect_scene: QRectF, path: str = "", parent=None) -> None:
        super().__init__(QRectF(0, 0, rect_scene.width(), rect_scene.height()), parent)
        self.setPos(rect_scene.topLeft())
        self.path = path
        self._pixmap: QPixmap | None = None
        self._load_pixmap()

    def _load_pixmap(self) -> None:
        if self.path and os.path.isfile(self.path):
            self._pixmap = QPixmap(self.path)
        else:
            self._pixmap = None

    def set_pixmap(self, pm: QPixmap | None) -> None:
        self._pixmap = pm
        self.update()

    def set_path(self, path: str) -> None:
        self.path = path
        self._load_pixmap()
        self.update()

    def paint_content(self, painter) -> None:
        r = self.rect()
        if self._pixmap is not None and not self._pixmap.isNull():
            painter.drawPixmap(r, self._pixmap)
        else:
            painter.setPen(QPen(QColor("#94a3b8"), 0.5, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(r)
            painter.setPen(QColor("#94a3b8"))
            name = os.path.basename(self.path) if self.path else "(无图片)"
            painter.setFont(mm_font(self.font_mm))
            painter.drawText(r, int(Qt.AlignmentFlag.AlignCenter), name)

    def geometry_record(self) -> dict:
        return self.frame_geometry_record()

    def props_record(self) -> dict:
        return {"path": self.path}

    @classmethod
    def from_normalized(cls, rec: dict) -> "FreeImageItem":
        g = rec["geometry"]
        item = cls(QRectF(g["x"], g["y"], g["w"], g["h"]), path=rec["props"]["path"])
        item._init_from_normalized(rec)
        return item
