from __future__ import annotations

import numpy as np
import pyvista as pv
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

try:
    from pyvistaqt import QtInteractor
    _HAS_PYVISTAQT = True
except ImportError:
    _HAS_PYVISTAQT = False


class Renderer3D(QWidget):
    slice_changed = Signal(str, int)  # (slice_type, position)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if _HAS_PYVISTAQT:
            self._plotter = QtInteractor(self)
            layout.addWidget(self._plotter.interactor)
        else:
            self._fallback = QLabel("3D 渲染不可用 (pyvistaqt 未安装)")
            self._fallback.setStyleSheet("color: #a0aec0; font-size: 16px;")
            layout.addWidget(self._fallback)
            self._plotter = None
        self._loaded = False
        self._volume_data: np.ndarray | None = None
        self._volume_spacing = (1, 1, 1)
        self._volume_origin = (0, 0, 0)
        self._meta = None

    def load_volume(self, data: np.ndarray, origin=(0, 0, 0),
                    spacing=(1, 1, 1)):
        self._volume_data = data
        self._volume_spacing = spacing
        self._volume_origin = origin
        if self._plotter is None:
            return
        self._plotter.clear()
        grid = pv.ImageData(
            dimensions=np.array(data.shape) + 1,
            spacing=spacing,
            origin=origin,
        )
        grid["amplitude"] = data.flatten(order="F")
        self._plotter.add_volume(
            grid, cmap="seismic", opacity="sigmoid",
            name="volume",
        )
        # Interactive slice widgets
        ni, nx, nt = data.shape
        self._plotter.add_plane_widget(
            self._make_slice_callback("inline"),
            normal="x", origin=(ni // 2 * spacing[0], 0, 0),
            bounds=(0, ni * spacing[0], 0, nx * spacing[1], 0, nt * spacing[2]),
            color="red", tubing=True,
        )
        self._plotter.add_plane_widget(
            self._make_slice_callback("crossline"),
            normal="y", origin=(0, nx // 2 * spacing[1], 0),
            bounds=(0, ni * spacing[0], 0, nx * spacing[1], 0, nt * spacing[2]),
            color="green", tubing=True,
        )
        self._plotter.add_plane_widget(
            self._make_slice_callback("time"),
            normal="z", origin=(0, 0, nt // 2 * spacing[2]),
            bounds=(0, ni * spacing[0], 0, nx * spacing[1], 0, nt * spacing[2]),
            color="blue", tubing=True,
        )
        self._plotter.reset_camera()
        self._loaded = True

    def _make_slice_callback(self, slice_type: str):
        def callback(normal, origin):
            if slice_type == "inline":
                pos = int(round(origin[0]))
            elif slice_type == "crossline":
                pos = int(round(origin[1]))
            else:
                pos = int(round(origin[2]))
            if pos >= 0:
                self.slice_changed.emit(slice_type, pos)
        return callback

    def add_horizon(self, horizon_data: np.ndarray, origin=(0, 0, 0),
                    spacing=(1, 1)):
        if horizon_data is None or self._plotter is None:
            return
        nI, nX = horizon_data.shape
        x = np.arange(nX, dtype=np.float64) * spacing[1] + origin[0]
        y = np.arange(nI, dtype=np.float64) * spacing[0] + origin[1]
        xx, yy = np.meshgrid(x, y)
        points = np.column_stack([
            xx.ravel(), yy.ravel(), horizon_data.ravel()
        ])
        mesh = pv.StructuredGrid()
        mesh.points = points
        mesh.dimensions = [nX, nI, 1]
        self._plotter.add_mesh(
            mesh, color="yellow", opacity=0.7,
            name="horizon", show_edges=False,
        )

    def set_colormap(self, cmap_name: str):
        if not self._loaded or self._volume_data is None or self._plotter is None:
            return
        grid = pv.ImageData(
            dimensions=np.array(self._volume_data.shape) + 1,
            spacing=self._volume_spacing,
            origin=self._volume_origin,
        )
        grid["amplitude"] = self._volume_data.flatten(order="F")
        self._plotter.add_volume(
            grid, cmap=cmap_name, opacity="sigmoid", name="volume",
        )
        self._plotter.reset_camera()

    def clear(self):
        if self._plotter is not None:
            self._plotter.clear()
        self._loaded = False
        self._volume_data = None
