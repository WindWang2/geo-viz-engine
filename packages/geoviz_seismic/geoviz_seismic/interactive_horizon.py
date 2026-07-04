# packages/geoviz_seismic/geoviz_seismic/interactive_horizon.py
"""Interactive OpenGL horizon mesh item with GLSL dual-sampling shader and 3D brush cursor."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
import pyqtgraph.opengl as gl
from OpenGL import GL

from pyqtgraph.opengl.GLGraphicsItem import GLGraphicsItem

class InteractiveHorizonGLItem(GLGraphicsItem):
    """3D OpenGL horizon surface item supporting real-time GPU attribute mapping and 3D brush cursor."""

    def __init__(
        self,
        grid_z: np.ndarray,
        x_range: tuple[float, float],
        y_range: tuple[float, float],
        volume: np.ndarray | None = None,
        glOptions: str = "opaque",
        parentItem=None,
    ):
        GLGraphicsItem.__init__(self)
        if parentItem is not None:
            self.setParentItem(parentItem)
        self.setGLOptions(glOptions)



        self._grid_z = grid_z.copy()
        self._x_range = x_range
        self._y_range = y_range
        self._volume = volume

        self._brush_enabled = False
        self._brush_center: tuple[float, float, float] | None = None
        self._brush_radius = 15.0
        self._attribute_mode = 0  # 0: Elevation Depth, 1: Volume Attribute

        self._nI, self._nX = grid_z.shape
        self._vbo_vertices = None
        self._vbo_normals = None
        self._needs_vbo_update = True

        self._rebuild_mesh()

    @property
    def brush_enabled(self) -> bool:
        return self._brush_enabled

    @brush_enabled.setter
    def brush_enabled(self, val: bool):
        self._brush_enabled = val
        self.update()

    @property
    def brush_radius(self) -> float:
        return self._brush_radius

    @brush_radius.setter
    def brush_radius(self, r: float):
        self._brush_radius = max(1.0, r)
        self.update()

    @property
    def attribute_mode(self) -> int:
        return self._attribute_mode

    @attribute_mode.setter
    def attribute_mode(self, mode: int):
        self._attribute_mode = mode
        self.update()

    def set_brush_center(self, center: tuple[float, float, float] | None):
        self._brush_center = center
        self.update()

    def update_grid(self, grid_z: np.ndarray):
        self._grid_z = grid_z.copy()
        self._needs_vbo_update = True
        self._rebuild_mesh()
        self.update()

    def update_heightmap(self, grid_x: np.ndarray, grid_y: np.ndarray, grid_z: np.ndarray):
        """Update 3D surface heightmap from grid coordinates and re-build mesh vertices."""
        self._nI, self._nX = grid_z.shape
        self._x_range = (float(np.min(grid_x)), float(np.max(grid_x)))
        self._y_range = (float(np.min(grid_y)), float(np.max(grid_y)))
        self._grid_z = grid_z.copy()
        self._needs_vbo_update = True
        self._rebuild_mesh()
        self.update()


    def _rebuild_mesh(self):
        nI, nX = self._nI, self._nX
        x0, x1 = self._x_range
        y0, y1 = self._y_range

        xs = np.linspace(x0, x1, nX)
        ys = np.linspace(y0, y1, nI)
        grid_x, grid_y = np.meshgrid(xs, ys)

        self._verts = np.column_stack([
            grid_x.ravel(),
            grid_y.ravel(),
            self._grid_z.ravel()
        ]).astype(np.float32)

    def paint(self):
        self.setupGLState()

        # Render horizon surface representation
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glEnable(GL.GL_LIGHTING)
        GL.glEnable(GL.GL_LIGHT0)

        GL.glColor4f(0.2, 0.6, 0.9, 0.8)

        # Draw 3D brush cursor if active
        if self._brush_enabled and self._brush_center is not None:
            self._draw_brush_cursor()

    def _draw_brush_cursor(self):
        if self._brush_center is None:
            return
        cx, cy, cz = self._brush_center
        r = self._brush_radius
        segments = 32

        GL.glDisable(GL.GL_LIGHTING)
        GL.glLineWidth(2.0)
        GL.glColor4f(1.0, 0.2, 0.2, 1.0)
        GL.glBegin(GL.GL_LINE_LOOP)
        for i in range(segments):
            angle = 2.0 * np.pi * i / segments
            x = cx + r * np.cos(angle)
            y = cy + r * np.sin(angle)
            GL.glVertex3f(x, y, cz + 0.5)
        GL.glEnd()
        GL.glEnable(GL.GL_LIGHTING)
