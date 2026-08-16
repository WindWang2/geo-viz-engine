import numpy as np
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QWidget


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
    """Attribute crossplot dialog — frequency vs envelope.

    The two Hilbert-transform attributes (envelope + instantaneous
    frequency) cost ~50-150 ms per full-resolution slice and used to run
    synchronously in __init__, freezing the GUI thread for every dialog
    open (#508). They now compute in a worker thread; the dialog shows a
    placeholder and swaps in the canvas when the result arrives.
    """

    def __init__(self, raw_data, sample_interval_s: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle("属性交叉图 — 频率 vs 包络")
        self.resize(500, 500)

        self._layout = QVBoxLayout(self)
        self._placeholder = QLabel("正在计算属性（包络 / 瞬时频率）…")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self._placeholder)

        from PySide6.QtCore import QThread

        self._thread = QThread()
        self._worker = _CrossplotComputeWorker(raw_data, sample_interval_s)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_computed)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_computed(self, x, y) -> None:
        self._layout.removeWidget(self._placeholder)
        self._placeholder.deleteLater()
        self._layout.addWidget(CrossplotCanvas(x, y))

    def _on_failed(self, message: str) -> None:
        self._placeholder.setText(f"属性计算失败: {message}")

    def closeEvent(self, event) -> None:
        # finished->deleteLater may already have destroyed the wrapper.
        thread = getattr(self, "_thread", None)
        if thread is not None:
            try:
                if thread.isRunning():
                    thread.quit()
                    thread.wait(2000)
            except RuntimeError:
                pass
        super().closeEvent(event)


class _CrossplotComputeWorker(QObject):
    """Envelope + instantaneous frequency off the GUI thread (#508)."""

    finished = Signal(object, object)  # x, y (subsampled)
    failed = Signal(str)

    def __init__(self, raw_data, sample_interval_s: float):
        super().__init__()
        self._raw = raw_data
        self._dt = sample_interval_s

    @Slot()
    def run(self) -> None:
        try:
            from .. import attributes as _attr

            env = _attr.compute_envelope(self._raw, axis=0)
            freq = _attr.compute_instantaneous_frequency(
                self._raw, axis=0, sample_interval=self._dt
            )
            # Subsample for performance
            step = max(1, env.size // 5000)
            self.finished.emit(
                freq.flatten()[::step], env.flatten()[::step]
            )
        except Exception as exc:  # surface to the dialog placeholder
            self.failed.emit(str(exc))
