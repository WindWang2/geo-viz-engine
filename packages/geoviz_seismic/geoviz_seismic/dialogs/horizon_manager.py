from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QHBoxLayout,
)


class HorizonManagerDialog(QDialog):
    """Dialog for listing and removing loaded horizons."""

    def __init__(self, horizon_names, remove_callback, parent=None):
        super().__init__(parent)
        self.setWindowTitle("层位管理")
        self.setMinimumSize(300, 300)
        self._remove_callback = remove_callback

        layout = QVBoxLayout(self)

        self._list_widget = QListWidget()
        for name in horizon_names:
            self._list_widget.addItem(name)
        layout.addWidget(self._list_widget)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        remove_btn = QPushButton("移除选中")
        remove_btn.setStyleSheet(
            "QPushButton { background: #fed7d7; color: #9b2c2c; "
            "border: 1px solid #feb2b2; border-radius: 4px; "
            "padding: 0 12px; font-size: 13px; }"
        )
        remove_btn.clicked.connect(self._remove_selected)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)

        btn_layout.addWidget(remove_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _remove_selected(self):
        item = self._list_widget.currentItem()
        if item:
            name = item.text()
            self._remove_callback(name)
            self._list_widget.takeItem(self._list_widget.row(item))
