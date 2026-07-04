"""High-resolution core photo magnifier dialog with zoom & pan controls."""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QScrollArea, QPushButton, QHBoxLayout
from PySide6.QtGui import QPixmap, QImage

class ImagePreviewDialog(QDialog):
    """Modal dialog for inspecting high-resolution core photo segments with zoom controls."""

    def __init__(self, pixmap: QPixmap, title: str = "Core Photo Preview", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"📸 {title}")
        self.resize(750, 600)

        self._pixmap = pixmap
        self._scale_factor = 1.0

        layout = QVBoxLayout(self)

        # Scrollable image container
        self.scroll_area = QScrollArea(self)
        self.image_label = QLabel(self)
        self.image_label.setPixmap(self._pixmap)
        self.image_label.setScaledContents(True)
        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.setWidgetResizable(True)
        layout.addWidget(self.scroll_area, 1)

        # Toolbar controls
        ctrl_layout = QHBoxLayout()
        zoom_in_btn = QPushButton("放大 (+)", self)
        zoom_out_btn = QPushButton("缩小 (-)", self)
        reset_btn = QPushButton("重置大小", self)

        zoom_in_btn.clicked.connect(self._zoom_in)
        zoom_out_btn.clicked.connect(self._zoom_out)
        reset_btn.clicked.connect(self._reset_zoom)

        ctrl_layout.addWidget(zoom_in_btn)
        ctrl_layout.addWidget(zoom_out_btn)
        ctrl_layout.addWidget(reset_btn)
        ctrl_layout.addStretch()

        close_btn = QPushButton("关闭", self)
        close_btn.clicked.connect(self.accept)
        ctrl_layout.addWidget(close_btn)

        layout.addLayout(ctrl_layout)

    def _zoom_in(self):
        self._scale_factor *= 1.25
        self._update_image_size()

    def _zoom_out(self):
        self._scale_factor *= 0.8
        self._update_image_size()

    def _reset_zoom(self):
        self._scale_factor = 1.0
        self._update_image_size()

    def _update_image_size(self):
        if not self._pixmap.isNull():
            new_w = int(self._pixmap.width() * self._scale_factor)
            new_h = int(self._pixmap.height() * self._scale_factor)
            self.image_label.resize(new_w, new_h)
