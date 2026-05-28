"""LockedObjectsPanel — premium glassmorphic overlay for managing locked hierarchy levels."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QAbstractItemView, QComboBox
)


class LockedItemWidget(QWidget):
    """Custom list item widget displaying locked feature name and a level selector with a hover-red delete button."""

    def __init__(self, feature_id: str, name: str, current_lock_level: str, on_level_changed, on_unlock, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        # Name label
        lbl = QLabel(name)
        lbl.setStyleSheet("color: #1e293b; font-size: 10px; font-weight: bold;")
        lbl.setToolTip(name)
        layout.addWidget(lbl, 1)

        # Level selector combobox
        self.combo = QComboBox()
        self.combo.addItems(["相", "亚相", "微相"])
        self.combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background: #f8fafc;
                color: #334155;
                font-size: 9px;
                padding: 1px 4px;
                min-width: 55px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                font-size: 9px;
                color: #334155;
            }
        """)

        # Map DB level strings to index
        level_map = ["facies", "sub_facies", "micro_facies"]
        if current_lock_level in level_map:
            self.combo.setCurrentIndex(level_map.index(current_lock_level))
        else:
            self.combo.setCurrentIndex(0)

        self.combo.currentIndexChanged.connect(
            lambda index: on_level_changed(feature_id, level_map[index])
        )
        layout.addWidget(self.combo)

        # Unlock / Delete button
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
    level_changed = Signal(str, str)

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
        """Update the list. locked_items is a list of (feature_id, display_name, current_lock_level)."""
        self.list_widget.clear()
        if not locked_items:
            self.list_widget.hide()
            self.empty_lbl.show()
        else:
            self.empty_lbl.hide()
            self.list_widget.show()
            for fid, name, lvl in locked_items:
                item = QListWidgetItem(self.list_widget)
                widget = LockedItemWidget(fid, name, lvl, self._on_level_changed, self._on_unlock_click, self)
                item.setSizeHint(widget.sizeHint())
                self.list_widget.addItem(item)
                self.list_widget.setItemWidget(item, widget)

    def _on_unlock_click(self, feature_id: str) -> None:
        self.unlock_requested.emit(feature_id)

    def _on_level_changed(self, feature_id: str, new_level: str) -> None:
        self.level_changed.emit(feature_id, new_level)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Glassmorphic Card Background
        p.setPen(QPen(QColor("#e2e8f0"), 1.0))
        p.setBrush(QBrush(QColor(255, 255, 255, 230)))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)
