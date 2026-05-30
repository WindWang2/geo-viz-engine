import numpy as np
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget


class CrossplotCanvas(QWidget):
    def __init__(self, x_data, y_data, parent=None):
        super().__init__(parent)
        self._x = x_data
        self._y = y_data
        self.setMinimumSize(400, 400)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(40, 20, -20, -30)

        # Axes
        p.setPen(QPen(QColor(100, 100, 100), 1))
        p.drawLine(r.left(), r.bottom(), r.right(), r.bottom())
        p.drawLine(r.left(), r.top(), r.left(), r.bottom())

        # Labels
        p.drawText(r.center().x() - 30, r.bottom() + 22, "瞬时频率 (Hz)")
        p.save()
        p.translate(12, r.center().y() + 30)
        p.rotate(-90)
        p.drawText(0, 0, "包络")
        p.restore()

        xlo = float(np.nanpercentile(self._x, 1))
        xhi = float(np.nanpercentile(self._x, 99))
        ylo = float(np.nanpercentile(self._y, 1))
        yhi = float(np.nanpercentile(self._y, 99))
        if xhi <= xlo:
            xhi = xlo + 1
        if yhi <= ylo:
            yhi = ylo + 1

        pen = QPen(QColor(30, 100, 200, 60), 2)
        p.setPen(pen)
        for xi, yi in zip(self._x, self._y):
            px = r.left() + (xi - xlo) / (xhi - xlo) * r.width()
            py = r.bottom() - (yi - ylo) / (yhi - ylo) * r.height()
            if r.left() <= px <= r.right() and r.top() <= py <= r.bottom():
                p.drawPoint(int(px), int(py))
        p.end()


class CrossplotDialog(QDialog):
    """Attribute crossplot dialog — frequency vs envelope."""

    def __init__(self, raw_data, sample_interval_s: float, parent=None):
        super().__init__(parent)
        from .. import attributes as _attr

        self.setWindowTitle("属性交叉图 — 频率 vs 包络")
        self.resize(500, 500)

        env = _attr.compute_envelope(raw_data, axis=0)
        freq = _attr.compute_instantaneous_frequency(
            raw_data, axis=0, sample_interval=sample_interval_s
        )

        # Subsample for performance
        step = max(1, env.size // 5000)
        x = freq.flatten()[::step]
        y = env.flatten()[::step]

        layout = QVBoxLayout(self)
        layout.addWidget(CrossplotCanvas(x, y))
