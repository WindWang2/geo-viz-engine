from __future__ import annotations

import logging
import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget,
)

import pyqtgraph.opengl as gl
from PySide6.QtGui import QVector3D

# Internal imports
from .colormap import ColormapManager
from .gpu_ops import is_gpu_available, to_gpu, slice_volume_gpu

logger = logging.getLogger(__name__)

class Renderer3D(QWidget):
    """3-D seismic volume renderer using PyQtGraph (Wayland + Native Qt compatible).

    Leverages QOpenGLWidget for reliable composition and optional CuPy backend
    for accelerated slicing operations.
    """

    slice_changed = Signal(str, int)  # (slice_type, position)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._loaded = False
        self._volume_data_cpu: np.ndarray | None = None
        self._volume_data_gpu = None  # CuPy array reference if available
        
        self._volume_spacing = (1, 1, 1)
        self._volume_origin = (0, 0, 0)
        self._meta = None
        self._cmap_name = "seismic"
        self._il_pos = 0
        self._xl_pos = 0
        self._t_pos = 0
        self._use_volume = False

        self._init_pyqtgraph(layout)
        self._plotter = True  # Keeps state parity with external API expectations

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _init_pyqtgraph(self, layout: QVBoxLayout):
        # Create central 3D widget
        self._view = gl.GLViewWidget()
        self._view.setBackgroundColor("#1e1e2e")
        
        # Set intuitive default camera positioning
        self._view.setCameraPosition(distance=500, elevation=30, azimuth=45)
        layout.addWidget(self._view, 1)

        # Add base grid for environment context
        self._base_grid = gl.GLGridItem()
        self._base_grid.setSize(500, 500)
        self._base_grid.setSpacing(50, 50)
        self._view.addItem(self._base_grid)

        # Controller layout for sliders
        ctrl = QWidget()
        ctrl.setStyleSheet("background: #f8fafc;")
        cl = QHBoxLayout(ctrl)
        cl.setContentsMargins(8, 4, 8, 4)

        self._il_slider = self._make_slider(cl, "Inline", "#e53e3e")
        self._xl_slider = self._make_slider(cl, "Xline", "#38a169")
        self._t_slider = self._make_slider(cl, "Time", "#3182ce")
        layout.addWidget(ctrl, 0)

        # Visual item placeholders
        self._volume_visual = None
        self._img_il = None
        self._img_xl = None
        self._img_t = None
        self._horizon_visual = None
        self._bbox_visual = None

    @staticmethod
    def _make_slider(layout: QHBoxLayout, label: str, color: str):
        lbl = QLabel(f"{label}:")
        lbl.setStyleSheet(
            f"color: {color}; font-weight: bold; font-size: 12px;"
        )
        layout.addWidget(lbl)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 0)
        slider.setValue(0)
        slider.setStyleSheet(
            "QSlider::groove:horizontal{height:4px;background:#e2e8f0;border-radius:2px;}"
            f"QSlider::handle:horizontal{{background:{color};width:14px;height:14px;"
            "margin:-5px 0;border-radius:7px;}}"
        )
        layout.addWidget(slider, 1)
        val_lbl = QLabel("0")
        val_lbl.setFixedWidth(36)
        val_lbl.setStyleSheet("color: #4a5568; font-size: 11px;")
        layout.addWidget(val_lbl)
        slider._val_label = val_lbl
        return slider

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_volume(self, data: np.ndarray, origin=(0, 0, 0),
                    spacing=(1, 1, 1)):
        """Load volume into renderer, automatically syncing to GPU if available."""
        self._volume_data_cpu = data
        self._volume_spacing = spacing
        self._volume_origin = origin
        
        # Transparently attempt mirroring to GPU for slicing acceleration
        if is_gpu_available():
            try:
                self._volume_data_gpu = to_gpu(data)
                logger.info("Seismic volume successfully cached on GPU via CuPy.")
            except Exception as e:
                logger.warning(f"Failed to push volume to GPU: {e}. Falling back to CPU slicing.")
                self._volume_data_gpu = None
        else:
            self._volume_data_gpu = None

        self._clear_visuals()

        ni, nx, nt = data.shape
        self._il_pos = ni // 2
        self._xl_pos = nx // 2
        self._t_pos = nt // 2
        
        # Setup spatial scaling
        si, sx, st = spacing
        
        # Center the camera dynamically based on volume size
        cx = (ni * si) / 2
        cy = (nx * sx) / 2
        cz = (nt * st) / 2
        self._view.opts['center'] = QVector3D(cx, cy, cz)
        self._view.setCameraPosition(distance=max(ni*si, nx*sx, nt*st) * 1.5)
        
        # Update grid to floor
        self._base_grid.translate(cx, cy, 0)

        # 1. Try 3D Texture Volume rendering first
        try:
            # PyQtGraph GLVolumeItem expect specific transpose for slicing order usually
            # We normalize data range for visualization
            vol_min = float(data.min())
            vol_max = float(data.max())
            norm_data = (data - vol_min) / (vol_max - vol_min)
            
            # Prepare volume item color table (alpha ramped)
            cmap_data = ColormapManager.get_colormap(self._cmap_name)
            # Add custom alpha logic (transparent near zero values for volume peek-thru)
            # shape=(256, 4)
            
            self._volume_visual = gl.GLVolumeItem(norm_data, sliceDensity=1)
            self._volume_visual.scale(si, sx, st)
            # Direct volume item can be intensive, off by default unless requested or explicitly coded.
            # In this project logic, we will follow the visual structure of manual planes + opt volume.
            # For performance stability on ES environments, we prefer sharp slice planes.
            self._use_volume = False # Set false for native slice perf
        except Exception as e:
            logger.warning(f"GLVolumeItem preparation skipped: {e}")
            self._use_volume = False

        # 2. Bounding Box setup
        self._create_bbox(ni, nx, nt, spacing)
        
        # 3. Interactive slice planes
        self._create_slice_planes()

        # 4. Update Control Sliders
        self._setup_sliders(ni, nx, nt)

        self._loaded = True
        self._view.update()

    def _setup_sliders(self, ni, nx, nt):
        self._il_slider.setRange(0, ni - 1)
        self._il_slider.setValue(self._il_pos)
        self._il_slider._val_label.setText(str(self._il_pos))
        
        self._xl_slider.setRange(0, nx - 1)
        self._xl_slider.setValue(self._xl_pos)
        self._xl_slider._val_label.setText(str(self._xl_pos))
        
        self._t_slider.setRange(0, nt - 1)
        self._t_slider.setValue(self._t_pos)
        self._t_slider._val_label.setText(str(self._t_pos))

        # Block multiple reconnections
        for s in [self._il_slider, self._xl_slider, self._t_slider]:
            try:
                s.valueChanged.disconnect()
            except (TypeError, RuntimeError):
                pass
                
        self._il_slider.valueChanged.connect(lambda v: self._on_slider("inline", v))
        self._xl_slider.valueChanged.connect(lambda v: self._on_slider("crossline", v))
        self._t_slider.valueChanged.connect(lambda v: self._on_slider("time", v))

    def add_horizon(self, horizon_data: np.ndarray, origin=(0, 0, 0),
                    spacing=(1, 1)):
        """Renders horizon as a 3D mesh surface."""
        if horizon_data is None:
            return
        if self._horizon_visual is not None:
            self._view.removeItem(self._horizon_visual)
            
        nI, nX = horizon_data.shape
        x = np.arange(nX, dtype=np.float32) * spacing[1] + origin[0]
        y = np.arange(nI, dtype=np.float32) * spacing[0] + origin[1]
        xx, yy = np.meshgrid(x, y)
        
        # Create mesh vertex grid
        verts = np.dstack([xx, yy, horizon_data.astype(np.float32)])
        
        # Generate faces
        faces = []
        for i in range(nI - 1):
            for j in range(nX - 1):
                p0 = i * nX + j
                p1 = p0 + 1
                p2 = (i + 1) * nX + j
                p3 = p2 + 1
                faces.append([p0, p1, p2])
                faces.append([p1, p3, p2])
        
        faces = np.array(faces)
        verts_flat = verts.reshape(-1, 3)
        
        # Soft golden/yellow coloring
        m_color = (1.0, 0.9, 0.2, 0.6)
        
        self._horizon_visual = gl.GLMeshItem(
            vertexes=verts_flat,
            faces=faces,
            color=m_color,
            shader='shaded',
            smooth=True,
            glOptions='additive'
        )
        self._view.addItem(self._horizon_visual)

    def set_colormap(self, cmap_name: str):
        """Change the display colormap and trigger redraw."""
        if not self._loaded:
            return
        self._cmap_name = cmap_name
        self._update_slice_planes()

    def clear(self):
        """Reset state and clean visual graph."""
        self._clear_visuals()
        self._loaded = False
        self._volume_data_cpu = None
        self._volume_data_gpu = None

    def _clear_visuals(self):
        for v in (self._volume_visual, self._img_il, self._img_xl,
                  self._img_t, self._horizon_visual, self._bbox_visual):
            if v is not None:
                try:
                    self._view.removeItem(v)
                except Exception:
                    pass
        self._volume_visual = None
        self._img_il = None
        self._img_xl = None
        self._img_t = None
        self._horizon_visual = None
        self._bbox_visual = None

    # ------------------------------------------------------------------
    # Internal Graph Building
    # ------------------------------------------------------------------

    def _create_bbox(self, ni, nx, nt, sp):
        si, sx, st = sp
        
        # Define corners of the volume cuboid
        corners = np.array([
            [0, 0, 0],
            [ni * si, 0, 0],
            [ni * si, nx * sx, 0],
            [0, nx * sx, 0],
            [0, 0, nt * st],
            [ni * si, 0, nt * st],
            [ni * si, nx * sx, nt * st],
            [0, nx * sx, nt * st]
        ], dtype=np.float32)
        
        # Sequence of vertex indices forming connected lines for edges
        edges = [
            0, 1, 1, 2, 2, 3, 3, 0,  # bottom loop
            4, 5, 5, 6, 6, 7, 7, 4,  # top loop
            0, 4, 1, 5, 2, 6, 3, 7   # vertical pillars
        ]
        
        path = corners[edges]
        
        self._bbox_visual = gl.GLLinePlotItem(
            pos=path,
            color=(0.5, 0.5, 0.5, 0.8),
            width=1.5,
            mode='lines'
        )
        self._view.addItem(self._bbox_visual)

    def _get_sliced_data(self, axis: int, index: int) -> np.ndarray:
        """Retrieves slice, prioritizing GPU cached volume memory if accessible."""
        vol = self._volume_data_gpu if self._volume_data_gpu is not None else self._volume_data_cpu
        if vol is None:
            return np.zeros((1,1))
        return slice_volume_gpu(vol, axis, index)

    def _create_slice_planes(self):
        if self._volume_data_cpu is None:
            return
            
        ni, nx, nt = self._volume_data_cpu.shape
        si, sx, st = self._volume_spacing

        # 1. Inline — Perpendicular to IL axis (x)
        il_raw = self._get_sliced_data(0, self._il_pos) # returns (nx, nt)
        img_il_rgb = ColormapManager.apply_to_data(il_raw, self._cmap_name)
        self._img_il = gl.GLImageItem(img_il_rgb)
        # The base ImageItem lies in XY plane. We scale to correct (sx, st) and rotate around Y axis by 90deg to place it perpendicular to X.
        self._img_il.scale(sx, st, 1)
        # Note: standard rotation is clockwise/counter dependent. 
        # To make it YZ facing: default is XY. Rotate around Y axis by 90 brings it to XZ. No, rotate around Y to get parallel to YZ?
        # Easier: Direct rotation matrix or sequential rotates.
        # We want the image local X mapped to world Y, local Y mapped to world Z.
        self._img_il.rotate(90, 0, 1, 0) # Rotates XY plane around Y-axis by 90 deg -> now lies in YZ plane at x=0.
        self._img_il.translate(self._il_pos * si, 0, 0)
        self._view.addItem(self._img_il)

        # 2. Crossline — Perpendicular to XL axis (y)
        xl_raw = self._get_sliced_data(1, self._xl_pos) # returns (ni, nt)
        img_xl_rgb = ColormapManager.apply_to_data(xl_raw, self._cmap_name)
        self._img_xl = gl.GLImageItem(img_xl_rgb)
        self._img_xl.scale(si, st, 1)
        # To place in XZ plane: Rotate around X-axis by 90 deg.
        self._img_xl.rotate(90, 1, 0, 0)
        self._img_xl.translate(0, self._xl_pos * sx, 0)
        self._view.addItem(self._img_xl)

        # 3. Time — Perpendicular to T axis (z)
        t_raw = self._get_sliced_data(2, self._t_pos) # returns (ni, nx)
        img_t_rgb = ColormapManager.apply_to_data(t_raw, self._cmap_name)
        self._img_t = gl.GLImageItem(img_t_rgb)
        self._img_t.scale(si, sx, 1)
        # Lies in XY plane by default. Just translate up in Z.
        self._img_t.translate(0, 0, self._t_pos * st)
        self._view.addItem(self._img_t)

    def _update_slice_planes(self):
        # Clear existing plane visuals from item graph
        for v in (self._img_il, self._img_xl, self._img_t):
            if v is not None:
                try:
                    self._view.removeItem(v)
                except Exception:
                    pass
        
        self._img_il = None
        self._img_xl = None
        self._img_t = None
        
        # Recreate instantly (leveraging GPU accelerated slicing cached results)
        self._create_slice_planes()
        self._view.update()

    def _on_slider(self, slice_type: str, value: int):
        if slice_type == "inline":
            self._il_slider._val_label.setText(str(value))
            self._il_pos = value
        elif slice_type == "crossline":
            self._xl_slider._val_label.setText(str(value))
            self._xl_pos = value
        else:
            self._t_slider._val_label.setText(str(value))
            self._t_pos = value
            
        self._update_slice_planes()
        
        if value >= 0:
            self.slice_changed.emit(slice_type, value)

    # Helper for existing API compatibility
    def grab(self):
        """Compatibility wrapper mirroring QWidget method to return current frame render."""
        return self._view.grabFramebuffer()
