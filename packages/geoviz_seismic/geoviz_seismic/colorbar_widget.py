from PySide6.QtGui import QPainter, QLinearGradient, QColor
from PySide6.QtWidgets import QWidget


class ColorbarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(60)
        self._cmap_name = "seismic"
        self._min_val = -1.0
        self._max_val = 1.0

    def set_colormap(self, name: str):
        self._cmap_name = name
        self.update()

    def set_range(self, min_val: float, max_val: float):
        self._min_val = min_val
        self._max_val = max_val
        self.update()

    def paintEvent(self, event):
        from .colormap import ColormapManager

        painter = QPainter(self)
        rect = self.rect()

        # Draw gradient
        grad = QLinearGradient(0, rect.bottom() - 20, 0, 20)
        lut = ColormapManager.get_colormap(self._cmap_name)
        for i in range(len(lut)):
            pos = i / (len(lut) - 1)
            r, g, b, a = lut[i]
            grad.setColorAt(pos, QColor(r, g, b, 255))

        bar_rect = rect.adjusted(10, 20, -30, -20)
        painter.fillRect(bar_rect, grad)

        # Draw text labels
        painter.setPen(QColor(100, 100, 100))
        painter.drawText(
            bar_rect.right() + 5, bar_rect.top() + 10, f"{self._max_val:.1f}"
        )
        painter.drawText(
            bar_rect.right() + 5, bar_rect.bottom(), f"{self._min_val:.1f}"
        )
        painter.drawText(
            bar_rect.right() + 5,
            bar_rect.center().y() + 5,
            f"{(self._max_val + self._min_val) / 2:.1f}",
        )
