# src/pages/cross_well/page.py
"""Thin wrapper around the QPainter cross-well widget."""
from __future__ import annotations

from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDialog, QListWidget, QListWidgetItem, QAbstractItemView,
)

from geoviz_well_log import CrossWellWidget, build_qpainter_tracks
from geoviz_well_log.renderer.canvas import WellLogCanvas
from src.data.well_registry import get_well_data


class _WellSelectDialog(QDialog):
    """Multi-select dialog for choosing wells to compare."""

    def __init__(self, well_names: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择对比井")
        self.setMinimumSize(300, 400)

        layout = QVBoxLayout(self)

        label = QLabel("勾选要对比的井号：")
        label.setStyleSheet("font-weight: bold; padding: 8px;")
        layout.addWidget(label)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        for name in sorted(well_names):
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._list.addItem(item)
        layout.addWidget(self._list)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        ok_btn = QPushButton("确定")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

    def get_selected(self) -> list[str]:
        """Return list of checked well names."""
        selected = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.text())
        return selected


class _WellLoadWorker(QObject):
    """Background worker that loads multiple wells and builds canvases."""

    progress = Signal(int, str)  # index, well_name
    finished = Signal(list)  # list[WellLogCanvas]
    error = Signal(str)

    def __init__(self, well_names: list[str], parent=None):
        super().__init__(parent)
        self._well_names = well_names
        self.result: list[WellLogCanvas] = []

    def run(self):
        self.result = []
        for i, name in enumerate(self._well_names):
            try:
                entry = get_well_data(name)
                if entry is None:
                    print(f"[CrossWell] Skipping {name}: not found in registry")
                    continue
                loader_fn, xls_path, config = entry
                data = loader_fn(xls_path, well_name=name)
                tracks = build_qpainter_tracks(data)
                canvas = WellLogCanvas()
                canvas.set_tracks(tracks)
                canvas.resize(200, 600)
                self.result.append(canvas)
                self.progress.emit(i, name)
            except Exception as e:
                print(f"[CrossWell] Failed to load {name}: {e}")
                continue
        self.finished.emit(self.result)


class CrossWellPage(CrossWellWidget):
    """Cross-well comparison page for the main application."""
    pass
