"""PaintScheduler — debounces rapid update() calls into ~60fps repaints."""
from __future__ import annotations

from PySide6.QtCore import QTimer


class PaintScheduler:
    """Coalesce rapid QWidget.update() calls into one repaint per frame."""

    def __init__(self, widget):
        self._widget = widget
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._do_update)
        self._pending = False

    def schedule(self) -> None:
        if not self._pending:
            self._pending = True
            self._timer.start()

    def _do_update(self) -> None:
        self._pending = False
        try:
            self._widget.update()
        except RuntimeError:
            pass