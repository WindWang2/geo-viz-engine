"""pyqtgraph.opengl items with interactive three-way (X/Y/Z) clipping planes.

Promoted from ``paleo_workbench/viz/geomodel/engine.py`` — GL rendering primitives
belong to the visualization engine. The pure geometry generators that used to share
that module now live in :mod:`geoviz_plots.geomodel.primitives`.

Clipping uses the fixed-function ``GL_CLIP_PLANE0..2`` slots, which is what
pyqtgraph's default (compatibility-profile) items already rely on::

    item = ClippedGLMeshItem(vertexes=v, faces=f, faceColors=c, smooth=True)
    item.set_clipping("z", enabled=True, val=-50.0, direction=1.0)

**Limitation:** ``GL_CLIP_PLANE0..2`` are fixed-function state that only exists
in compatibility-profile (or legacy no-profile) GL contexts. Under a **core
profile** or GLES they are unavailable; :meth:`ThreeWayClipMixin.paint` detects
that, logs a warning once and skips clipping (geometry renders unclipped)
instead of raising a GL error.

Importing this module requires Qt + PyOpenGL, so keep it off worker threads.
"""

from __future__ import annotations

import logging

import pyqtgraph.opengl as gl
from OpenGL import GL
from PySide6.QtGui import QOpenGLContext, QSurfaceFormat

logger = logging.getLogger(__name__)

__all__ = ["ClippedGLMeshItem", "ClippedGLVolumeItem", "ThreeWayClipMixin"]

_AXIS_SLOTS: dict[str, int] = {"x": 0, "y": 1, "z": 2}

_FIXED_CLIP_WARNED = False


def _core_profile_context() -> bool:
    """Return ``True`` when the current context is an explicit core profile.

    Fixed-function ``GL_CLIP_PLANE*`` are removed in core profile. A missing
    current context or a ``NoProfile`` context (legacy default, treated as
    compatibility-capable) reports ``False``.
    """
    ctx = QOpenGLContext.currentContext()
    if ctx is None:
        return False
    return ctx.format().profile() == QSurfaceFormat.OpenGLContextProfile.CoreProfile


def _warn_fixed_clip_once() -> None:
    """Log the core-profile clipping limitation once per process."""
    global _FIXED_CLIP_WARNED
    if _FIXED_CLIP_WARNED:
        return
    _FIXED_CLIP_WARNED = True
    logger.warning(
        "OpenGL context is a core profile: fixed-function GL_CLIP_PLANE0..2 "
        "are unavailable, clipping is disabled."
    )


class ThreeWayClipMixin:
    """Adds X/Y/Z clipping-plane state and a ``paint()`` wrapper that applies it.

    Mix in *before* the pyqtgraph item so ``paint()`` resolves here first.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # axis -> (enabled, value, direction); direction 1.0 clips coord > value.
        self._clip: dict[str, tuple[bool, float, float]] = {
            axis: (False, 0.0, 1.0) for axis in _AXIS_SLOTS
        }

    def set_clipping(self, axis: str, enabled: bool, val: float, direction: float = 1.0) -> None:
        """Enable/disable the clip plane for ``axis`` (``'x'``, ``'y'`` or ``'z'``).

        ``direction=1.0`` discards geometry with ``coord > val``; ``-1.0`` discards
        ``coord < val``. Unknown axis names are ignored, matching the previous
        workbench behaviour. In a core-profile context the planes are unavailable;
        a warning is logged once and :meth:`paint` skips clipping.
        """
        if axis in self._clip:
            self._clip[axis] = (bool(enabled), float(val), float(direction))
        if enabled and _core_profile_context():
            _warn_fixed_clip_once()
        self.update()

    def clipping(self, axis: str) -> tuple[bool, float, float]:
        """Current ``(enabled, val, direction)`` for ``axis``."""
        return self._clip[axis]

    def paint(self):
        if QOpenGLContext.currentContext() is None:
            super().paint()
            return

        if _core_profile_context():
            # Fixed-function clip planes do not exist in core profile: skip
            # clipping rather than feeding GL invalid enums.
            _warn_fixed_clip_once()
            super().paint()
            return

        enabled_slots = []
        for axis, (enabled, val, direction) in self._clip.items():
            if not enabled:
                continue
            slot = GL.GL_CLIP_PLANE0 + _AXIS_SLOTS[axis]
            equation = [0.0, 0.0, 0.0, val * direction]
            equation[_AXIS_SLOTS[axis]] = -direction
            GL.glEnable(slot)
            GL.glClipPlane(slot, tuple(equation))
            enabled_slots.append(slot)

        try:
            super().paint()
        finally:
            for slot in enabled_slots:
                GL.glDisable(slot)


class ClippedGLMeshItem(ThreeWayClipMixin, gl.GLMeshItem):
    """``GLMeshItem`` supporting interactive three-way clipping planes."""


class ClippedGLVolumeItem(ThreeWayClipMixin, gl.GLVolumeItem):
    """``GLVolumeItem`` supporting interactive three-way clipping planes."""
