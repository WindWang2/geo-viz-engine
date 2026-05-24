from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QProgressBar, QLabel,
)


class FloatingProgressOverlay(QWidget):
    """Inline progress bar embedded in the page layout."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.hide()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        self._label = QLabel()
        self._label.setStyleSheet("font-size: 12px; color: #2d3748;")
        layout.addWidget(self._label)

        self._bar = QProgressBar()
        self._bar.setFixedHeight(8)
        self._bar.setTextVisible(False)
        self._bar.setMaximum(0)
        self._bar.setStyleSheet("""
            QProgressBar {
                background: #e2e8f0; border: none; border-radius: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3182ce, stop:1 #63b3ed);
                border-radius: 4px;
            }
        """)
        layout.addWidget(self._bar, 1)

        self.setStyleSheet("""
            FloatingProgressOverlay {
                background: #f7fafc;
                border-bottom: 1px solid #e2e8f0;
            }
        """)

    def show_progress(self, msg: str = "", maximum: int = 0):
        self._bar.setRange(0, maximum)
        self._bar.setValue(0)
        if msg:
            self._label.setText(msg)
        self.show()

    def update_progress(self, value: int, msg: str = ""):
        if value > 0 and self._bar.maximum() == 0:
            self._bar.setRange(0, 100)
        self._bar.setValue(value)
        if msg:
            self._label.setText(msg)

    def hide_progress(self):
        self.hide()
