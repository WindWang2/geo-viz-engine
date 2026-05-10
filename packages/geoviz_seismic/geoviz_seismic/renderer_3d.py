from __future__ import annotations

import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout


class Renderer3D(QWidget):
    slice_changed = Signal(str, int)  # (slice_type, position)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plotter = QtInteractor(self)
        layout.addWidget(self._plotter.interactor)
        self._loaded = False
        self._volume_data: np.ndarray | None = None
        self._meta = None

    def load_volume(self, data: np.ndarray, origin=(0, 0, 0),
                    spacing=(1, 1, 1)):
        self._volume_data = data
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
        self._plotter.reset_camera()
        self._loaded = True

    def add_horizon(self, horizon_data: np.ndarray, origin=(0, 0, 0),
                    spacing=(1, 1)):
        if horizon_data is None:
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
        if self._loaded:
            self._plotter.update_scalars(
                self._volume_data.flatten(order="F"),
                name="amplitude",
            )

    def clear(self):
        self._plotter.clear()
        self._loaded = False
        self._volume_data = None
