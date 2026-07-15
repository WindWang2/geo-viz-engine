from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PySide6.QtWidgets import QComboBox, QVBoxLayout, QWidget

from .models import SliceInfo
from .profile_widget import ProfileWidget


@dataclass(frozen=True)
class SeismicSlice:
    data: np.ndarray
    info: SliceInfo


@dataclass(frozen=True)
class SeismicPreviewPayload:
    slices: dict[str, SeismicSlice]
    initial_mode: str = "inline"


class SeismicPreviewWidget(QWidget):
    """A bounded 2-D seismic preview without any OpenGL dependencies."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._slices: dict[str, SeismicSlice] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.mode_combo = QComboBox(self)
        self.mode_combo.addItem("Inline", "inline")
        self.mode_combo.addItem("Crossline", "crossline")
        self.mode_combo.addItem("Time", "time")
        layout.addWidget(self.mode_combo)

        self.profile = ProfileWidget(self)
        layout.addWidget(self.profile)

        self.mode_combo.currentIndexChanged.connect(self._show_selected_slice)
        self.clear()

    def set_slices(self, payload: SeismicPreviewPayload) -> None:
        self._slices = dict(payload.slices)
        initial_index = self.mode_combo.findData(payload.initial_mode)
        if initial_index < 0:
            initial_index = 0
        self.mode_combo.setCurrentIndex(initial_index)
        self._show_selected_slice()

    def clear(self) -> None:
        self._slices = {}
        self.profile.set_overlay_text("暂无地震切片")

    def _show_selected_slice(self, *args) -> None:
        mode = self.mode_combo.currentData()
        seismic_slice = self._slices.get(mode)
        if seismic_slice is None:
            return
        self.profile.set_overlay_text(None)
        self.profile.update_profile(seismic_slice.data, slice_info=seismic_slice.info)


__all__ = ["SeismicPreviewPayload", "SeismicPreviewWidget", "SeismicSlice"]
