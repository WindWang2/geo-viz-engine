from __future__ import annotations

from typing import Literal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QStackedWidget, QVBoxLayout, QWidget

from .profile_vd import ProfileVD
from .profile_wiggle import ProfileWiggle


class ProfileWidget(QWidget):
    """Unified profile widget with VD / Wiggle display-mode switching.

    Wraps a :class:`QStackedWidget` that contains a :class:`ProfileVD`
    (variable-density heatmap) and a :class:`ProfileWiggle` (wiggle-trace)
    renderer.  The active renderer is selected via
    :meth:`set_display_mode`.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        self._vd = ProfileVD()
        self._wiggle = ProfileWiggle()
        self._stack.addWidget(self._vd)
        self._stack.addWidget(self._wiggle)

        # Overlay label for loading states
        self._overlay = QLabel(self)
        self._overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._overlay.setStyleSheet(
            "background: rgba(255,255,255,200); color: #4a5568; font-size: 16px;"
        )
        self._overlay.hide()

        self._mode = "vd"
        self._current_data = None
        self._current_slice_info = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_profile(
        self,
        data,
        trace_step: int = 2,
        slice_info=None,
    ) -> None:
        self._current_data = data
        self._current_slice_info = slice_info

        if self._mode == "vd":
            self._vd.render(
                data,
                colormap=self._vd.current_colormap(),
                slice_info=slice_info,
            )
        else:
            self._wiggle.render(data, trace_step=trace_step)

    def mode(self) -> str:
        """Return the current display mode (``"vd"`` or ``"wiggle"``)."""
        return self._mode

    def set_display_mode(self, mode: Literal["vd", "wiggle"]) -> None:
        """Switch between ``"vd"`` and ``"wiggle"`` display modes and refresh display."""
        if mode == self._mode:
            return
            
        if mode == "vd":
            self._stack.setCurrentIndex(0)
            self._mode = "vd"
        elif mode == "wiggle":
            self._stack.setCurrentIndex(1)
            self._mode = "wiggle"
        else:
            raise ValueError(
                f"Unknown display mode: {mode!r}. Expected 'vd' or 'wiggle'."
            )
            
        # Re-render immediately with currently cached data if available
        if self._current_data is not None:
            self.update_profile(self._current_data, slice_info=self._current_slice_info)

    def set_colormap(self, name: str) -> None:
        """Change the VD colormap."""
        self._vd.set_colormap(name)

    def set_wiggle_density(self, trace_step: int) -> None:
        """Change the wiggle trace subsampling step."""
        self._wiggle.set_trace_step(trace_step)

    def set_overlay_text(self, text: str | None) -> None:
        """Show a centered overlay message, or hide it if *text* is ``None``."""
        if text is None:
            self._overlay.hide()
        else:
            self._overlay.setText(text)
            self._overlay.setGeometry(self.rect())
            self._overlay.raise_()
            self._overlay.show()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._overlay.isVisible():
            self._overlay.setGeometry(self.rect())
