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
from .gpu_ops import (
    is_gpu_available, to_gpu, to_cpu, slice_volume_gpu, apply_colormap_gpu,
    sample_arbitrary_slice_gpu, sample_polyline_slice
)

logger = logging.getLogger(__name__)

class Renderer3D(QWidget):
    """3-D seismic volume renderer using PyQtGraph (Wayland + Native Qt compatible).

    Leverages QOpenGLWidget for reliable composition and optional CuPy backend
    for accelerated slicing operations.
    """

    slice_changed = Signal(str, int)  # (slice_type, position)
    arbitrary_slice_changed = Signal(object)  # polyline slice data (np.ndarray)
    jump_to_position = Signal(float, float, float)  # (il_idx, xl_idx, t_idx)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._press_pos = None
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
        self._arb_polyline: list[tuple[float, float]] | None = None  # index-space waypoints

        # Overlay / Attribute volume state (Phase 12a)
        self._overlay_volume_data_cpu: np.ndarray | None = None
        self._overlay_cmap_name = "jet"
        self._overlay_opacity = 0.5
        self._overlay_volume_visual = None

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

        # Install event filter for click-to-jump detection
        self._view.installEventFilter(self)

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
        self._img_arb = None
        self._horizon_visual = None
        self._horizons: dict[str, object] = {}  # name -> GLMeshItem
        self._picks_visual = None
        self._annotation_items: list = []  # GLTextItem references
        self._bbox_visual = None
        self._cursor_sphere = None  # GLScatterPlotItem for linked cursor

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
            "margin:-5px 0;border-radius:7px;}"
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

    def set_render_mode(self, mode: str):
        """Set the 3D display mode: 'planes' or 'volume'"""
        self._mode = mode
        if self._volume_visual is not None:
            if mode == "volume":
                self._volume_visual.show()
            else:
                self._volume_visual.hide()
        if self._overlay_volume_visual is not None:
            if mode == "volume":
                self._overlay_volume_visual.show()
            else:
                self._overlay_volume_visual.hide()
        self._view.update()

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

        self._mode = getattr(self, "_mode", "planes")
        self._volume_visual = None
        self._opacity_mode = getattr(self, "_opacity_mode", "sharp")

        # 1. 3D Volume Item (Hidden by default, shown when mode="volume")
        try:
            cmap_data = ColormapManager.get_colormap(self._cmap_name).copy()
            alpha_curve = self._build_alpha_curve(self._opacity_mode, len(cmap_data))
            cmap_data[:, 3] = alpha_curve.astype(np.uint8)
            vol_data = self._volume_data_gpu if self._volume_data_gpu is not None else data
            
            # Using downsampled data for volume rendering to avoid GPU VRAM crash on huge datasets
            # Slices remain 1x1x1 resolution, volume is purely visual
            from .gpu_ops import apply_colormap_gpu
            vol_rgba = apply_colormap_gpu(vol_data[::2, ::2, ::2], cmap_data)
            
            # sliceDensity=3 makes the raycaster cast more rays, making it look dense and solid
            self._volume_visual = gl.GLVolumeItem(vol_rgba, sliceDensity=3, smooth=True)
            self._volume_visual.scale(si*2, sx*2, st*2)
            self._view.addItem(self._volume_visual)
            if self._mode != "volume":
                self._volume_visual.hide()
        except Exception as e:
            logger.warning(f"GLVolumeItem preparation failed: {e}")

        # 2. Bounding Box & labeled Axis setup
        self._create_bbox(ni, nx, nt, spacing)
        self._create_axis_labels(ni, nx, nt, spacing)
        
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
                    spacing=(1, 1), name: str = "horizon", color=(1.0, 0.9, 0.2, 0.6)):
        """Renders horizon as a 3D mesh surface."""
        if horizon_data is None:
            return

        # Remove previous single-horizon if it exists
        if self._horizon_visual is not None:
            self._view.removeItem(self._horizon_visual)
            self._horizon_visual = None

        # Remove existing horizon with same name
        if name in self._horizons:
            self._view.removeItem(self._horizons[name])

        nI, nX = horizon_data.shape
        x = np.arange(nX, dtype=np.float32) * spacing[1] + origin[0]
        y = np.arange(nI, dtype=np.float32) * spacing[0] + origin[1]
        xx, yy = np.meshgrid(x, y)

        verts = np.dstack([xx, yy, horizon_data.astype(np.float32)])

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

        mesh = gl.GLMeshItem(
            vertexes=verts_flat,
            faces=faces,
            color=color,
            shader='shaded',
            smooth=True,
            glOptions='additive'
        )
        self._horizons[name] = mesh
        self._view.addItem(mesh)

    def remove_horizon(self, name: str):
        if name in self._horizons:
            self._view.removeItem(self._horizons.pop(name))

    def horizons(self) -> list[str]:
        return list(self._horizons.keys())

    def set_colormap(self, cmap_name: str):
        """Change the display colormap and trigger redraw."""
        if not self._loaded:
            return
        self._cmap_name = cmap_name
        self._update_slice_planes()
        if self._mode == "volume":
            self._rebuild_volume_visual()

    @staticmethod
    def _build_alpha_curve(mode: str, n: int = 256) -> np.ndarray:
        """Build an alpha transfer function curve (0-255)."""
        t = np.linspace(0, 1, n)
        if mode == "linear":
            alpha = t * 255
        elif mode == "sigmoid":
            alpha = 1 / (1 + np.exp(-10 * (t - 0.5))) * 255
        elif mode == "threshold":
            alpha = np.where(t > 0.15, 200, 0).astype(np.float64)
        else:  # "sharp" (default) — original behavior
            alpha = np.clip(np.abs(np.linspace(-1, 1, n)) * 400, 0, 255)
        return np.clip(alpha, 0, 255).astype(np.uint8)

    def set_opacity_mode(self, mode: str):
        """Set the opacity transfer function and rebuild volume visual."""
        self._opacity_mode = mode
        if self._loaded and self._volume_visual is not None:
            self._rebuild_volume_visual()

    def _rebuild_volume_visual(self):
        """Rebuild the GLVolumeItem with current opacity settings."""
        if self._volume_visual is not None:
            self._view.removeItem(self._volume_visual)
            self._volume_visual = None

        try:
            cmap_data = ColormapManager.get_colormap(self._cmap_name).copy()
            alpha_curve = self._build_alpha_curve(self._opacity_mode, len(cmap_data))
            cmap_data[:, 3] = alpha_curve.astype(np.uint8)
            vol_data = self._volume_data_gpu if self._volume_data_gpu is not None else self._volume_data_cpu
            from .gpu_ops import apply_colormap_gpu
            vol_rgba = apply_colormap_gpu(vol_data[::2, ::2, ::2], cmap_data)

            si, sx, st = self._volume_spacing
            self._volume_visual = gl.GLVolumeItem(vol_rgba, sliceDensity=3, smooth=True)
            self._volume_visual.scale(si * 2, sx * 2, st * 2)
            self._view.addItem(self._volume_visual)
            if self._mode != "volume":
                self._volume_visual.hide()
        except Exception as e:
            logger.warning(f"Rebuild volume visual failed: {e}")

    def load_overlay_volume(self, data: np.ndarray, colormap: str = "jet", opacity: float = 0.5):
        """Load an overlay attribute/property volume and display it superimposed with alpha blending."""
        self._overlay_volume_data_cpu = data
        self._overlay_cmap_name = colormap
        self._overlay_opacity = opacity
        
        self.rebuild_overlay_volume_visual()

    def rebuild_overlay_volume_visual(self):
        """Rebuild the overlay volume visual item using colormap and opacity."""
        if self._overlay_volume_visual is not None:
            try:
                self._view.removeItem(self._overlay_volume_visual)
            except Exception:
                pass
            self._overlay_volume_visual = None

        if self._overlay_volume_data_cpu is None:
            return

        try:
            # Get colormap LUT data
            cmap_data = ColormapManager.get_colormap(self._overlay_cmap_name).copy()
            
            # Apply global opacity factor as standard alpha overlay
            alpha_curve = self._build_alpha_curve("sharp", len(cmap_data))
            # Multiply alpha curve by our opacity factor (0.0 to 1.0)
            alpha_curve = alpha_curve * self._overlay_opacity
            cmap_data[:, 3] = alpha_curve.astype(np.uint8)
            
            # Downsample attribute volume for visual parity with primary volume (sliceDensity=3)
            vol_data = self._overlay_volume_data_cpu
            from .gpu_ops import apply_colormap_gpu
            vol_rgba = apply_colormap_gpu(vol_data[::2, ::2, ::2], cmap_data)

            # Create visual item
            si, sx, st = self._volume_spacing
            self._overlay_volume_visual = gl.GLVolumeItem(vol_rgba, sliceDensity=3, smooth=True)
            self._overlay_volume_visual.scale(si * 2, sx * 2, st * 2)
            self._view.addItem(self._overlay_volume_visual)
            
            # Sync visibility with main volume mode
            if self._mode != "volume":
                self._overlay_volume_visual.hide()
                
            self._view.update()
        except Exception as e:
            logger.warning(f"Rebuild overlay volume visual failed: {e}")

    def set_overlay_colormap(self, cmap_name: str):
        """Change the colormap of the overlay volume."""
        self._overlay_cmap_name = cmap_name
        self.rebuild_overlay_volume_visual()

    def set_overlay_opacity(self, opacity: float):
        """Change the opacity (alpha multiplier) of the overlay volume."""
        self._overlay_opacity = opacity
        self.rebuild_overlay_volume_visual()

    def set_overlay_visible(self, visible: bool):
        """Toggle visibility of the overlay volume visual."""
        if self._overlay_volume_visual is not None:
            if visible and self._mode == "volume":
                self._overlay_volume_visual.show()
            else:
                self._overlay_volume_visual.hide()
            self._view.update()

    def clear_overlay_volume(self):
        """Clear and remove the overlay volume visual."""
        if self._overlay_volume_visual is not None:
            try:
                self._view.removeItem(self._overlay_volume_visual)
            except Exception:
                pass
            self._overlay_volume_visual = None
        self._overlay_volume_data_cpu = None
        self._view.update()

    def clear(self):
        """Reset state and clean visual graph."""
        self._clear_visuals()
        self._loaded = False
        self._volume_data_cpu = None
        self._volume_data_gpu = None
        self._overlay_volume_data_cpu = None
        self._overlay_volume_visual = None

    def _clear_visuals(self):
        for v in (self._volume_visual, self._overlay_volume_visual, self._img_il, self._img_xl,
                  self._img_t, self._img_arb, self._horizon_visual,
                  self._picks_visual, self._bbox_visual, self._cursor_sphere):
            if v is not None:
                try:
                    self._view.removeItem(v)
                except Exception:
                    pass
        for v in self._horizons.values():
            try:
                self._view.removeItem(v)
            except Exception:
                pass
        self._horizons.clear()
        # Clear axis labels
        for v in getattr(self, '_axis_labels', []):
            try:
                self._view.removeItem(v)
            except Exception:
                pass
        self._axis_labels = []
        # Clear line items from borders
        for attr in ('_line_il', '_line_xl', '_line_t', '_line_arb'):
            v = getattr(self, attr, None)
            if v is not None:
                try:
                    self._view.removeItem(v)
                except Exception:
                    pass
                setattr(self, attr, None)
        self._volume_visual = None
        self._img_il = None
        self._img_xl = None
        self._img_t = None
        self._img_arb = None
        self._horizon_visual = None
        self._bbox_visual = None
        self._cursor_sphere = None
        
        # Clear polyline curtain items & data
        for item in getattr(self, '_arb_curtain_items', []):
            try:
                self._view.removeItem(item)
            except Exception:
                pass
        self._arb_curtain_items = []
        self._arb_polyline = None

        # Clear annotation items
        for item in self._annotation_items:
            try:
                self._view.removeItem(item)
            except Exception:
                pass
        self._annotation_items = []

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

    def _create_axis_labels(self, ni, nx, nt, sp):
        """Create visible 3D coordinate axes with colored lines, arrows, and tick labels."""
        si, sx, st = sp
        max_dim = max(ni * si, nx * sx, nt * st)
        pad = max_dim * 0.08  # Extension beyond bounding box
        
        self._axis_labels = []
        
        # ---- Solid colored axis LINES (RGB convention) ----
        # Inline axis (X) — Red
        il_line = gl.GLLinePlotItem(
            pos=np.array([[0, 0, 0], [ni * si + pad, 0, 0]], dtype=np.float32),
            color=(1.0, 0.3, 0.3, 1.0), width=3.0, antialias=True
        )
        self._view.addItem(il_line)
        self._axis_labels.append(il_line)
        
        # Crossline axis (Y) — Green
        xl_line = gl.GLLinePlotItem(
            pos=np.array([[0, 0, 0], [0, nx * sx + pad, 0]], dtype=np.float32),
            color=(0.3, 0.85, 0.3, 1.0), width=3.0, antialias=True
        )
        self._view.addItem(xl_line)
        self._axis_labels.append(xl_line)
        
        # Time axis (Z) — Blue
        t_line = gl.GLLinePlotItem(
            pos=np.array([[0, 0, 0], [0, 0, nt * st + pad]], dtype=np.float32),
            color=(0.3, 0.5, 1.0, 1.0), width=3.0, antialias=True
        )
        self._view.addItem(t_line)
        self._axis_labels.append(t_line)
        
        # ---- Axis endpoint text labels ----
        try:
            il_label = gl.GLTextItem(
                pos=np.array([ni * si + pad * 1.2, 0, 0]),
                text=f'Inline (0-{ni-1})',
                color=(255, 100, 100, 255)
            )
            xl_label = gl.GLTextItem(
                pos=np.array([0, nx * sx + pad * 1.2, 0]),
                text=f'Xline (0-{nx-1})',
                color=(100, 220, 100, 255)
            )
            t_label = gl.GLTextItem(
                pos=np.array([0, 0, nt * st + pad * 1.2]),
                text=f'Time (0-{nt-1})',
                color=(100, 150, 255, 255)
            )
            for lbl in (il_label, xl_label, t_label):
                self._view.addItem(lbl)
                self._axis_labels.append(lbl)
        except Exception:
            pass
        
        # ---- Tick marks along each axis (5 ticks) ----
        tick_offset = max_dim * 0.03
        n_ticks = 5
        for i in range(n_ticks + 1):
            frac = i / n_ticks
            try:
                pos_il = np.array([frac * ni * si, -tick_offset, 0])
                tick_il = gl.GLTextItem(
                    pos=pos_il,
                    text=str(int(frac * ni)),
                    color=(220, 180, 180, 220)
                )
                self._view.addItem(tick_il)
                self._axis_labels.append(tick_il)
                
                pos_xl = np.array([-tick_offset, frac * nx * sx, 0])
                tick_xl = gl.GLTextItem(
                    pos=pos_xl,
                    text=str(int(frac * nx)),
                    color=(180, 220, 180, 220)
                )
                self._view.addItem(tick_xl)
                self._axis_labels.append(tick_xl)
                
                pos_t = np.array([-tick_offset, -tick_offset, frac * nt * st])
                tick_t = gl.GLTextItem(
                    pos=pos_t,
                    text=str(int(frac * nt)),
                    color=(180, 190, 220, 220)
                )
                self._view.addItem(tick_t)
                self._axis_labels.append(tick_t)
            except Exception:
                pass

    def _get_sliced_data(self, axis: int, index: int) -> np.ndarray:
        """Retrieves slice, prioritizing GPU cached volume memory if accessible."""
        vol = self._volume_data_gpu if self._volume_data_gpu is not None else self._volume_data_cpu
        if vol is None:
            return np.zeros((1,1))
        # Optimization: Request to KEEP the array reference on the GPU device
        return slice_volume_gpu(vol, axis, index, keep_on_gpu=True)

    def _create_slice_planes(self):
        if self._volume_data_cpu is None:
            return
            
        ni, nx, nt = self._volume_data_cpu.shape
        si, sx, st = self._volume_spacing
        
        # Pre-fetch color lookup table for hardware upload reuse
        lut = ColormapManager.get_colormap(self._cmap_name)

        # 1. Inline — Perpendicular to IL axis (x)
        il_raw = self._get_sliced_data(0, self._il_pos) # returns GPU or CPU array
        img_il_rgb = apply_colormap_gpu(il_raw, lut)
        self._img_il = gl.GLImageItem(img_il_rgb)
        self._img_il.scale(sx, st, 1)
        self._img_il.rotate(90, 1, 0, 0)  # Puts Time (Height) on Z axis
        self._img_il.rotate(90, 0, 0, 1)  # Puts Crossline (Width) on Y axis
        self._img_il.translate(self._il_pos * si, 0, 0)
        self._view.addItem(self._img_il)
        
        # Red Border for Inline
        il_pts = np.array([[0, 0, 0], [0, nx*sx, 0], [0, nx*sx, nt*st], [0, 0, nt*st], [0, 0, 0]])
        self._line_il = gl.GLLinePlotItem(pos=il_pts, color=(1, 0, 0, 1), width=2, antialias=True)
        self._line_il.translate(self._il_pos * si, 0, 0)
        self._view.addItem(self._line_il)

        # 2. Crossline — Perpendicular to XL axis (y)
        xl_raw = self._get_sliced_data(1, self._xl_pos)
        img_xl_rgb = apply_colormap_gpu(xl_raw, lut)
        self._img_xl = gl.GLImageItem(img_xl_rgb)
        self._img_xl.scale(si, st, 1)
        self._img_xl.rotate(90, 1, 0, 0)
        self._img_xl.translate(0, self._xl_pos * sx, 0)
        self._view.addItem(self._img_xl)
        
        # Green Border for Crossline
        xl_pts = np.array([[0, 0, 0], [ni*si, 0, 0], [ni*si, 0, nt*st], [0, 0, nt*st], [0, 0, 0]])
        self._line_xl = gl.GLLinePlotItem(pos=xl_pts, color=(0, 1, 0, 1), width=2, antialias=True)
        self._line_xl.translate(0, self._xl_pos * sx, 0)
        self._view.addItem(self._line_xl)

        # 3. Time — Perpendicular to T axis (z)
        t_raw = self._get_sliced_data(2, self._t_pos)
        img_t_rgb = apply_colormap_gpu(t_raw, lut)
        self._img_t = gl.GLImageItem(img_t_rgb)
        self._img_t.scale(si, sx, 1)
        self._img_t.translate(0, 0, self._t_pos * st)
        self._view.addItem(self._img_t)
        
        # Blue Border for Time
        t_pts = np.array([[0, 0, 0], [ni*si, 0, 0], [ni*si, nx*sx, 0], [0, nx*sx, 0], [0, 0, 0]])
        self._line_t = gl.GLLinePlotItem(pos=t_pts, color=(0, 0, 1, 1), width=2, antialias=True)
        self._line_t.translate(0, 0, self._t_pos * st)
        self._view.addItem(self._line_t)
        
        # 4. Polyline-driven arbitrary curtain (if set)
        self._render_polyline_curtain(ni, nx, nt, si, sx, st, lut)

    def _update_slice_planes(self):
        # Clear existing plane visuals from item graph
        items_to_clean = (
            getattr(self, "_img_il", None), getattr(self, "_img_xl", None), getattr(self, "_img_t", None), getattr(self, "_img_arb", None),
            getattr(self, "_line_il", None), getattr(self, "_line_xl", None), getattr(self, "_line_t", None), getattr(self, "_line_arb", None)
        )
        for v in items_to_clean:
            if v is not None:
                try:
                    self._view.removeItem(v)
                except Exception:
                    pass
        
        self._img_il = self._img_xl = self._img_t = self._img_arb = None
        self._line_il = self._line_xl = self._line_t = self._line_arb = None
        
        # Clean up polyline curtain items
        for item in getattr(self, '_arb_curtain_items', []):
            try:
                self._view.removeItem(item)
            except Exception:
                pass
        self._arb_curtain_items = []
        
        # Recreate instantly (leveraging GPU accelerated slicing cached results)
        self._create_slice_planes()
        self._view.update()

    def set_arbitrary_polyline(self, points: list[tuple[float, float]]):
        """Set the arbitrary slice polyline path (index-space coordinates).
        
        Args:
            points: List of (inline_idx, xline_idx) waypoints.
        """
        self._arb_polyline = points if len(points) >= 2 else None
        if self._loaded:
            self._update_slice_planes()
    
    def _render_polyline_curtain(self, ni, nx, nt, si, sx, st, lut):
        """Render the polyline-based arbitrary vertical curtain in 3D."""
        if self._arb_polyline is None or len(self._arb_polyline) < 2:
            return
        
        try:
            vol = self._volume_data_gpu if self._volume_data_gpu is not None else self._volume_data_cpu
            arb_data, cum_dist = sample_polyline_slice(vol, self._arb_polyline)
            
            if arb_data.shape[1] < 2:
                return
            
            # Render each segment of the curtain as a separate image plane
            # For simplicity, render the whole curtain as segments between consecutive waypoints
            points = self._arb_polyline
            
            # Draw the polyline path on the floor (time=t_pos*st) as a magenta line
            path_pts = []
            for il_idx, xl_idx in points:
                path_pts.append([il_idx * si, xl_idx * sx, self._t_pos * st])
            path_arr = np.array(path_pts, dtype=np.float32)
            
            self._line_arb = gl.GLLinePlotItem(
                pos=path_arr,
                color=(1.0, 0.0, 0.85, 1.0),
                width=4.0,
                antialias=True
            )
            self._view.addItem(self._line_arb)
            
            # Draw vertical curtain walls between each consecutive pair of waypoints
            img_arb_rgb = apply_colormap_gpu(arb_data, lut)
            
            # We render the whole curtain as individual segment planes
            # Track horizontal position in the sampled data
            self._arb_curtain_items = []
            
            seg_start = 0
            for seg_idx in range(len(points) - 1):
                i0, x0 = points[seg_idx]
                i1, x1 = points[seg_idx + 1]
                seg_len = float(np.hypot(i1 - i0, x1 - x0))
                if seg_len < 0.01:
                    continue
                
                n_pts = max(2, int(seg_len))
                seg_end = min(seg_start + n_pts, arb_data.shape[1])
                
                if seg_end <= seg_start:
                    continue
                
                seg_data = img_arb_rgb[:, seg_start:seg_end]
                n_cols = seg_end - seg_start
                
                # Transpose for GLImageItem: (n_cols, nt, 4)
                seg_img = np.ascontiguousarray(seg_data.transpose(1, 0, 2))
                
                wx0, wy0 = float(i0 * si), float(x0 * sx)
                wx1, wy1 = float(i1 * si), float(x1 * sx)
                d_spatial = float(np.hypot(wx1 - wx0, wy1 - wy0))
                alpha_deg = float(np.degrees(np.arctan2(wy1 - wy0, wx1 - wx0)))
                
                item = gl.GLImageItem(seg_img)
                item.scale(d_spatial / max(n_cols, 1), st, 1.0)
                item.rotate(90, 1, 0, 0)
                item.rotate(alpha_deg, 0, 0, 1)
                item.translate(wx0, wy0, 0)
                self._view.addItem(item)
                self._arb_curtain_items.append(item)
                
                # Vertical borders for this segment
                border = np.array([
                    [wx0, wy0, 0], [wx1, wy1, 0],
                    [wx1, wy1, nt * st], [wx0, wy0, nt * st],
                    [wx0, wy0, 0]
                ], dtype=np.float32)
                border_item = gl.GLLinePlotItem(
                    pos=border, color=(1.0, 0.0, 0.85, 0.6), width=2.0, antialias=True
                )
                self._view.addItem(border_item)
                self._arb_curtain_items.append(border_item)
                
                seg_start = seg_end
            
            # Emit the full curtain data for 2D panel
            self.arbitrary_slice_changed.emit(arb_data)
        except Exception as e:
            logger.error(f"Failed to render polyline curtain: {e}")

    def eventFilter(self, obj, event):
        """Detect left-clicks on 3D view for jump-to-position navigation."""
        from PySide6.QtCore import QEvent
        if obj is not self._view:
            return False
        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                self._press_pos = event.position()
        elif event.type() == QEvent.Type.MouseButtonRelease:
            if event.button() == Qt.MouseButton.LeftButton and self._press_pos is not None:
                release_pos = event.position()
                dx = release_pos.x() - self._press_pos.x()
                dy = release_pos.y() - self._press_pos.y()
                self._press_pos = None
                if dx * dx + dy * dy < 25:  # 5px threshold
                    self._handle_3d_click(release_pos.x(), release_pos.y())
        return False

    def _handle_3d_click(self, px: float, py: float):
        """Ray-cast from screen point into volume bounding box and emit jump."""
        if not self._loaded:
            return
        result = self._ray_box_intersect(px, py)
        if result is not None:
            il_idx, xl_idx, t_idx = result
            self.jump_to_position.emit(il_idx, xl_idx, t_idx)

    def _ray_box_intersect(self, px: float, py: float):
        """Compute 3D volume coordinates by ray-box intersection (slab method).

        Uses the view and projection matrices to unproject screen coordinates
        into a world-space ray, then intersects against the volume AABB.
        Returns (il_idx, xl_idx, t_idx) or None.
        """
        try:
            view = self._view
            w = view.width()
            h = view.height()
            if w <= 0 or h <= 0:
                return None

            # Get view and projection matrices from pyqtgraph
            vm = view.viewMatrix()
            pm = view.projectionMatrix()

            # NDC coordinates (flip y for OpenGL)
            ndc_x = (2.0 * px / w) - 1.0
            ndc_y = 1.0 - (2.0 * py / h)

            # Compute inverse view-projection matrix
            vpm = pm * vm
            inv = vpm.inverted()
            if inv[1] != 0:
                inv_mat = inv[0]
            else:
                return None

            # Near and far points in world space
            from PySide6.QtGui import QVector4D
            near = inv_mat.map(QVector4D(ndc_x, ndc_y, -1.0, 1.0))
            far = inv_mat.map(QVector4D(ndc_x, ndc_y, 1.0, 1.0))
            if abs(near.w()) < 1e-8 or abs(far.w()) < 1e-8:
                return None
            near_w = QVector3D(near.x() / near.w(), near.y() / near.w(), near.z() / near.w())
            far_w = QVector3D(far.x() / far.w(), far.y() / far.w(), far.z() / far.w())

            # Ray direction
            direction = far_w - near_w
            length = direction.length()
            if length < 1e-8:
                return None
            direction = direction / length

            origin = near_w

            # AABB bounds in world space
            ni, nx, nt = self._volume_data_cpu.shape
            si, sx, st = self._volume_spacing
            box_min = QVector3D(0, 0, 0)
            box_max = QVector3D(ni * si, nx * sx, nt * st)

            # Slab method for ray-AABB intersection
            t_min = -1e30
            t_max = 1e30
            for i, (o, d, bmin, bmax) in enumerate([
                (origin.x(), direction.x(), box_min.x(), box_max.x()),
                (origin.y(), direction.y(), box_min.y(), box_max.y()),
                (origin.z(), direction.z(), box_min.z(), box_max.z()),
            ]):
                if abs(d) < 1e-10:
                    if o < bmin or o > bmax:
                        return None
                else:
                    t1 = (bmin - o) / d
                    t2 = (bmax - o) / d
                    if t1 > t2:
                        t1, t2 = t2, t1
                    t_min = max(t_min, t1)
                    t_max = min(t_max, t2)
                    if t_min > t_max:
                        return None

            if t_min < 0:
                t_min = t_max
            if t_min < 0:
                return None

            # Intersection point
            hit = origin + direction * t_min

            # Convert world coordinates to volume indices
            il_idx = hit.x() / si
            xl_idx = hit.y() / sx
            t_idx = hit.z() / st

            il_idx = max(0.0, min(il_idx, ni - 1))
            xl_idx = max(0.0, min(xl_idx, nx - 1))
            t_idx = max(0.0, min(t_idx, nt - 1))

            return il_idx, xl_idx, t_idx
        except Exception:
            return None

    def _on_slider(self, slice_type: str, value: int):
        if slice_type == "inline":
            self._il_slider._val_label.setText(str(value))
            self._il_pos = value
        elif slice_type == "crossline":
            self._xl_slider._val_label.setText(str(value))
            self._xl_pos = value
        elif slice_type == "time":
            self._t_slider._val_label.setText(str(value))
            self._t_pos = value

        self._update_slice_planes()

        if value >= 0:
            self.slice_changed.emit(slice_type, value)

    def set_position_external(self, slice_type: str, position: int):
        """Set a slice position from an external source (toolbar slider, etc.).

        Updates the internal state, syncs the 3D slider with blockSignals,
        and triggers slice plane update + signal emission.
        """
        if not self._loaded:
            return
        slider_map = {
            "inline": (self._il_slider, "_il_pos"),
            "crossline": (self._xl_slider, "_xl_pos"),
            "time": (self._t_slider, "_t_pos"),
        }
        entry = slider_map.get(slice_type)
        if entry is None:
            return
        slider, attr = entry
        slider.blockSignals(True)
        slider.setValue(position)
        slider._val_label.setText(str(position))
        slider.blockSignals(False)
        setattr(self, attr, position)
        self._update_slice_planes()
        self.slice_changed.emit(slice_type, position)

    def set_horizon_picks(self, points: list[tuple[float, float, float]]):
        """Render manually picked horizon points as a 3D scatter plot.

        Args:
            points: List of (inline_num, xline_num, time_ms) tuples.
        """
        if self._picks_visual is not None:
            self._view.removeItem(self._picks_visual)
            self._picks_visual = None

        if not points or not self._loaded:
            return

        ni, nx, nt = self._volume_data_cpu.shape
        si, sx, st = self._volume_spacing

        pos = np.array([
            [il * si, xl * sx, t * st]
            for il, xl, t in points
        ], dtype=np.float32)

        if len(pos) == 0:
            return

        color = np.full((len(pos), 4), [1.0, 0.65, 0.0, 1.0], dtype=np.float32)
        self._picks_visual = gl.GLScatterPlotItem(
            pos=pos, color=color, size=8, pxMode=True
        )
        self._view.addItem(self._picks_visual)

    def set_cursor_position(self, il_val: float, xl_val: float, t_val: float):
        """Update the linked cursor sphere position in 3D space.

        Args:
            il_val, xl_val, t_val: Coordinate values in seismic units.
        """
        if not self._loaded:
            return
        si, sx, st = self._volume_spacing
        pos = np.array([[il_val * si, xl_val * sx, t_val * st]], dtype=np.float32)
        if self._cursor_sphere is None:
            self._cursor_sphere = gl.GLScatterPlotItem(
                pos=pos, color=np.array([[1.0, 1.0, 0.0, 1.0]], dtype=np.float32),
                size=12, pxMode=True,
            )
            self._view.addItem(self._cursor_sphere)
        else:
            self._cursor_sphere.setData(pos=pos)

    def set_annotations(self, annotations: list[tuple[float, float, float, str]]):
        """Render text annotations in 3D space.

        Args:
            annotations: List of (il_val, xl_val, time_val, text) tuples.
        """
        for item in self._annotation_items:
            try:
                self._view.removeItem(item)
            except Exception:
                pass
        self._annotation_items = []

        if not annotations or not self._loaded:
            return

        si, sx, st = self._volume_spacing

        for il_val, xl_val, t_val, text in annotations:
            try:
                pos = np.array([il_val * si, xl_val * sx, t_val * st])
                item = gl.GLTextItem(
                    pos=pos,
                    text=text,
                    color=(255, 255, 0, 255),
                )
                self._view.addItem(item)
                self._annotation_items.append(item)
            except Exception:
                pass

    # Helper for existing API compatibility
    def grab(self):
        """Compatibility wrapper mirroring QWidget method to return current frame render."""
        return self._view.grabFramebuffer()
