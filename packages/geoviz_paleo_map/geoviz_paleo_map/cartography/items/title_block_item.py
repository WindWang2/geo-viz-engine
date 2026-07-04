# packages/geoviz_paleo_map/geoviz_paleo_map/cartography/items/title_block_item.py
"""Chinese Exploration standard title block graphics item."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPen, QPainter
from .base_item import LayoutGraphicsItem

class TitleBlockGraphicsItem(LayoutGraphicsItem):
    """Exploration standard 3-column title block matching Chinese petroleum specs."""

    def __init__(
        self,
        rect: QRectF = QRectF(0, 0, 120, 30),
        map_title: str = "中国主要含油气盆地构造图",
        map_number: str = "GEO-MAP-2026-001",
        organization: str = "地质勘探研究院",
        scale_str: str = "1 : 2,500,000",
        author: str = "张伟",
        checker: str = "李明",
        approver: str = "王强",
        date_str: str = "2026年07月",
        parent=None,
    ):
        super().__init__(rect, parent)
        self.map_title = map_title
        self.map_number = map_number
        self.organization = organization
        self.scale_str = scale_str
        self.author = author
        self.checker = checker
        self.approver = approver
        self.date_str = date_str

    def paint(self, painter: QPainter, option, widget=None):
        painter.save()
        r = self.rect()
        
        # Outer border
        painter.setPen(QPen(QColor("#1a2433"), 1.2))
        painter.fillRect(r, QColor("#ffffff"))
        painter.drawRect(r)

        # 3 Columns: Col 1 (30%), Col 2 (45%), Col 3 (25%)
        w1 = r.width() * 0.30
        w2 = r.width() * 0.45
        w3 = r.width() * 0.25

        x1 = r.left() + w1
        x2 = x1 + w2

        painter.drawLine(x1, r.top(), x1, r.bottom())
        painter.drawLine(x2, r.top(), x2, r.bottom())

        # Col 1: Organization
        font = QFont("SimSun", 9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(r.left() + 2, r.top() + 4, w1 - 4, r.height() - 8),
                         Qt.AlignmentFlag.AlignCenter, self.organization)

        # Col 2: Title & Map Number & Scale
        font.setPixelSize(10)
        painter.setFont(font)
        r_title = QRectF(x1 + 2, r.top() + 2, w2 - 4, r.height() * 0.5)
        r_sub = QRectF(x1 + 2, r.top() + r.height() * 0.5, w2 - 4, r.height() * 0.5 - 2)
        
        painter.drawText(r_title, Qt.AlignmentFlag.AlignCenter, self.map_title)
        
        font.setPixelSize(8)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(r_sub, Qt.AlignmentFlag.AlignCenter, f"{self.map_number}  |  比例尺 {self.scale_str}")

        # Col 3: Signatures (编制/审核/批准/日期)
        r_sig = QRectF(x2 + 4, r.top() + 2, w3 - 6, r.height() - 4)
        sig_text = f"编制: {self.author}\n审核: {self.checker}\n日期: {self.date_str}"
        painter.drawText(r_sig, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, sig_text)

        painter.restore()
        super().paint(painter, option, widget)
