"""pyqtgraph.opengl items with interactive three-way (X/Y/Z) clipping planes.

Promoted from ``paleo_workbench/viz/geomodel/engine.py`` — GL rendering primitives
belong to the visualization engine. The pure geometry generators that used to share
that module now live in :mod:`geoviz_plots.geomodel.primitives`.

Clipping uses the fixed-function ``GL_CLIP_PLANE0..2`` slots, which is what
pyqtgraph's default (compatibility-profile) items already rely on::

    item = ClippedGLMeshItem(vertexes=v, faces=f, faceColors=c, smooth=True)
    item.set_clipping("z", enabled=True, val=-50.0, direction=1.0)

Importing this module requires Qt + PyOpenGL, so keep it off worker threads.
"""

from __future__ import annotations

import pyqtgraph.opengl as gl
from OpenGL import GL
from PySide6.QtGui import QOpenGLContext

__all__ = ["ClippedGLMeshItem", "ClippedGLVolumeItem", "ThreeWayClipMixin"]

_AXIS_SLOTS: dict[str, int] = {"x": 0, "y": 1, "z": 2}


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
        workbench behaviour.
        """
        if axis in self._clip:
            self._clip[axis] = (bool(enabled), float(val), float(direction))
        self.update()

    def clipping(self, axis: str) -> tuple[bool, float, float]:
        """Current ``(enabled, val, direction)`` for ``axis``."""
        return self._clip[axis]

    def paint(self):
        if QOpenGLContext.currentContext() is None:
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
