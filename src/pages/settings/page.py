"""SettingsPage — 应用偏好设置（主题 / 坐标格式 / 缓存清理）。"""
import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QFrame, QGroupBox,
)

from src.utils.preferences import get_preference_bus
from src.utils.paths import get_resources_dir


THEMES = [
    ("浅米白 (默认)", "light"),
    ("矿石灰", "ore-gray"),
]


def _section_card(title: str) -> tuple[QGroupBox, QVBoxLayout]:
    box = QGroupBox(f" {title}")
    box.setStyleSheet(
        "QGroupBox { background: #ffffff; border: 1px solid #e5eaf1; border-radius: 12px;"
        " margin-top: 14px; padding: 16px 14px 14px 14px; font-weight: 600; color: #1f66d4; }"
        "QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 6px; }"
    )
    layout = QVBoxLayout(box)
    layout.setContentsMargins(4, 10, 4, 4)
    layout.setSpacing(10)
    return box, layout


class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(14)

        # Header
        title = QLabel("设置")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #1a2433;")
        outer.addWidget(title)
        subtitle = QLabel("应用主题、坐标显示、缓存管理")
        subtitle.setStyleSheet("font-size: 12px; color: #92a0b0;")
        outer.addWidget(subtitle)

        # --- Theme card -------------------------------------------------------
        theme_card, theme_layout = _section_card("主题")
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("配色方案:"))
        self.theme_combo = QComboBox()
        for label, _key in THEMES:
            self.theme_combo.addItem(label)
        self.theme_combo.setMinimumWidth(180)
        theme_row.addWidget(self.theme_combo)
        theme_row.addStretch()
        theme_layout.addLayout(theme_row)
        outer.addWidget(theme_card)

        # --- Coordinate format card ------------------------------------------
        coord_card, coord_layout = _section_card("坐标显示")
        coord_row = QHBoxLayout()
        coord_row.addWidget(QLabel("格式:"))
        self.coord_dd_btn = QPushButton("十进制 DD")
        self.coord_dd_btn.setCheckable(True)
        self.coord_dd_btn.setChecked(True)
        self.coord_dms_btn = QPushButton("度分秒 DMS")
        self.coord_dms_btn.setCheckable(True)
        for btn in (self.coord_dd_btn, self.coord_dms_btn):
            btn.setStyleSheet(
                "QPushButton { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px;"
                " padding: 6px 14px; color: #586878; font-weight: 500; }"
                "QPushButton:checked { background: #e9effa; color: #1f66d4;"
                " border-color: #1f66d4; font-weight: 600; }"
            )
        coord_row.addWidget(self.coord_dd_btn)
        coord_row.addWidget(self.coord_dms_btn)
        coord_row.addStretch()
        coord_layout.addLayout(coord_row)
        outer.addWidget(coord_card)

        # --- Cache card -------------------------------------------------------
        cache_card, cache_layout = _section_card("缓存")
        cache_row = QHBoxLayout()
        self.cache_size_label = QLabel(self._compute_cache_size_label())
        self.cache_size_label.setStyleSheet("color: #586878; font-family: monospace; font-size: 12px;")
        cache_row.addWidget(self.cache_size_label)
        cache_row.addStretch()
        self.clear_cache_btn = QPushButton(" 清理缓存")
        ic = get_resources_dir() / "icons" / "ui" / "redo.svg"
        if ic.exists():
            self.clear_cache_btn.setIcon(QIcon(str(ic)))
        self.clear_cache_btn.setStyleSheet(
            "QPushButton { background: #1f66d4; color: #ffffff; border: none; border-radius: 8px;"
            " padding: 7px 16px; font-weight: 600; }"
            "QPushButton:hover { background: #1552b0; }"
        )
        cache_row.addWidget(self.clear_cache_btn)
        cache_layout.addLayout(cache_row)
        outer.addWidget(cache_card)

        outer.addStretch()

        # Wire signals
        self._bus = get_preference_bus()
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        self.coord_dd_btn.clicked.connect(lambda: self._on_coord_clicked("DD"))
        self.coord_dms_btn.clicked.connect(lambda: self._on_coord_clicked("DMS"))
        self.clear_cache_btn.clicked.connect(self._on_clear_cache)

    # ------------------------------------------------------------------
    def _on_theme_changed(self, idx: int):
        label = self.theme_combo.itemText(idx)
        self._bus.theme_changed.emit(label)

    def _on_coord_clicked(self, fmt: str):
        self.coord_dd_btn.setChecked(fmt == "DD")
        self.coord_dms_btn.setChecked(fmt == "DMS")
        self._bus.coordinate_format_changed.emit(fmt)

    def _on_clear_cache(self):
        from src.utils.cache_metrics import purge_all_caches, compute_total_cache_mb

        released = purge_all_caches()
        self.cache_size_label.setText(self._compute_cache_size_label())
        self._bus.cache_cleared.emit(released if released else compute_total_cache_mb())

    # ------------------------------------------------------------------
    def _compute_cache_size_label(self) -> str:
        from src.utils.cache_metrics import compute_total_cache_mb

        mb = compute_total_cache_mb()
        if mb >= 1024:
            return f"已用 {mb / 1024:.2f} GB"
        return f"已用 {mb:.1f} MB"
