"""LockedObjectsPanel — premium glassmorphic overlay for managing locked hierarchy levels."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QAbstractItemView
)


class LockedItemWidget(QWidget):
    """Custom list item widget displaying locked feature name and level with a hover-red delete button."""

    def __init__(self, feature_id: str, name: str, level_name: str, on_unlock, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        lbl = QLabel(f"{name} ({level_name})")
        lbl.setStyleSheet("color: #334155; font-size: 10px;")
        layout.addWidget(lbl, 1)

        btn = QPushButton("✕")
        btn.setFixedSize(14, 14)
        btn.setToolTip("解除锁定")
        btn.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 7px;
                background: #f1f5f9;
                color: #64748b;
                font-weight: bold;
                font-size: 9px;
            }
            QPushButton:hover {
                background: #fee2e2;
                color: #ef4444;
            }
        """)
        btn.clicked.connect(lambda: on_unlock(feature_id))
        layout.addWidget(btn)


class LockedObjectsPanel(QWidget):
    """Floating list panel showing all currently locked objects in a glassmorphic card."""
    unlock_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(240)
        self.setFixedHeight(180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # 1. Header Title
        self.title_lbl = QLabel("已锁定层级对象")
        self.title_lbl.setStyleSheet("font-weight: bold; color: #1e293b; font-size: 11px;")
        layout.addWidget(self.title_lbl)

        # 2. Scrollable List Widget
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
            }
            QListWidget::item {
                background: transparent;
                padding: 2px 0px;
                border-bottom: 1px solid #f1f5f9;
            }
        """)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.list_widget, 1)

        # 3. Empty State Label
        self.empty_lbl = QLabel("暂无锁定对象\n(在图上多边形右键可锁定)")
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_lbl.setStyleSheet("color: #64748b; font-size: 10px; line-height: 14px;")
        layout.addWidget(self.empty_lbl, 1)

    def update_items(self, locked_items: list[tuple[str, str, str]]) -> None:
        """Update the list. locked_items is a list of (feature_id, display_name, level_label)."""
        self.list_widget.clear()
        if not locked_items:
            self.list_widget.hide()
            self.empty_lbl.show()
        else:
            self.empty_lbl.hide()
            self.list_widget.show()
            for fid, name, lvl in locked_items:
                item = QListWidgetItem(self.list_widget)
                widget = LockedItemWidget(fid, name, lvl, self._on_unlock_click, self)
                item.setSizeHint(widget.sizeHint())
                self.list_widget.addItem(item)
                self.list_widget.setItemWidget(item, widget)

    def _on_unlock_click(self, feature_id: str) -> None:
        self.unlock_requested.emit(feature_id)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Glassmorphic Card Background
        p.setPen(QPen(QColor("#e2e8f0"), 1.0))
        p.setBrush(QBrush(QColor(255, 255, 255, 230)))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)
