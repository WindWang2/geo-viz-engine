from __future__ import annotations

from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

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

        self._mode = "vd"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_profile(
        self,
        data,
        trace_step: int = 2,
        slice_info=None,
    ) -> None:
        """Forward data to the active renderer.

        Parameters
        ----------
        data:
            2-D ``float32`` array of shape ``(n_samples, n_traces)``.
        trace_step:
            Trace subsampling for wiggle mode (ignored in VD mode).
        slice_info:
            Optional :class:`SliceInfo` metadata forwarded to VD mode.
        """
        if self._mode == "vd":
            self._vd.render(
                data,
                colormap=self._vd.current_colormap(),
                slice_info=slice_info,
            )
        else:
            self._wiggle.render(data, trace_step=trace_step)

    def set_display_mode(self, mode: str) -> None:
        """Switch between ``"vd"`` and ``"wiggle"`` display modes."""
        if mode == "vd":
            self._stack.setCurrentIndex(0)
            self._mode = "vd"
        elif mode == "wiggle":
            self._stack.setCurrentIndex(1)
            self._mode = "wiggle"
        else:
            raise ValueError(f"Unknown display mode: {mode!r}")

    def set_colormap(self, name: str) -> None:
        """Change the VD colormap."""
        self._vd.set_colormap(name)

    def set_wiggle_density(self, trace_step: int) -> None:
        """Change the wiggle trace subsampling step."""
        self._wiggle.set_trace_step(trace_step)
