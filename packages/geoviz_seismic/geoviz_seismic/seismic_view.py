from __future__ import annotations

import logging
import numpy as np
from PySide6.QtCore import Qt, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QSplitter,
    QPushButton, QComboBox, QLabel, QFileDialog, QToolBar,
)
from PySide6.QtGui import QPainter, QLinearGradient, QColor

from .renderer_3d import Renderer3D
from .profile_widget import ProfileWidget
from .loader import SeismicLoader
from .horizon import HorizonParser
from .cache import SeismicCache
from .models import SeismicVolumeMeta, SliceInfo


def _generate_synthetic(
    n_inlines: int = 200, n_crosslines: int = 200,
    n_samples: int = 200,
) -> np.ndarray:
    """Generate synthetic seismic with geologically realistic structure:
    horizontal reflectors with gentle dip, a fault offset, and noise."""
    t = np.linspace(0, 4 * np.pi, n_samples, dtype=np.float32)
    il = np.arange(n_inlines, dtype=np.float32)
    xl = np.arange(n_crosslines, dtype=np.float32)
    
    dip_il = 0.02 * il[:, np.newaxis, np.newaxis]
    dip_xl = 0.015 * xl[np.newaxis, :, np.newaxis]
    t_3d = t[np.newaxis, np.newaxis, :]
    
    reflector = np.sin(t_3d + dip_il + dip_xl) + 0.5 * np.sin(2.3 * t_3d + dip_il + dip_xl)
    field = reflector.copy()
    
    fault_il = n_inlines // 2
    offset = 5
    field[fault_il:, :, offset:] = field[fault_il:, :, :-offset].copy()
    field[fault_il:, :, :offset] = 0
    rng = np.random.default_rng(42)
    noise = rng.normal(0, 0.15, field.shape).astype(np.float32)
    return field + noise


class _SyntheticWorker(QThread):
    """Background thread for synthetic data generation."""
    done = Signal(object)  # np.ndarray

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        data = _generate_synthetic()
        self.done.emit(data)


class _SegyLoadWorker(QThread):
    """Background thread for SEGY file loading."""
    done = Signal(object)  # tuple: (meta, vol, raw, path)
    error = Signal(str)

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self._path = path

    def run(self):
        try:
            loader = SeismicLoader(self._path)
            meta = loader.inspect()
            vol = loader.get_volume_downsampled(factor=(4, 4, 2))
            mid_il = meta.iline_start + (meta.n_inlines // 2) * meta.iline_step
            mid_xl = meta.xline_start + (meta.n_crosslines // 2) * meta.xline_step
            mid_t = meta.n_samples // 2  # index
            
            raw_il = loader.read_inline(mid_il)
            raw_xl = loader.read_crossline(mid_xl)
            raw_t = loader.read_timeslice(mid_t)
            
            # Close file handle on worker thread; main thread re-opens lazily
            loader.close()
            self.done.emit((meta, vol, raw_il, raw_xl, raw_t, self._path))
        except Exception as exc:
            self.error.emit(str(exc))


class ColorbarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(60)
        self._cmap_name = "seismic"
        self._min_val = -1.0
        self._max_val = 1.0

    def set_colormap(self, name: str):
        self._cmap_name = name
        self.update()

    def set_range(self, min_val: float, max_val: float):
        self._min_val = min_val
        self._max_val = max_val
        self.update()

    def paintEvent(self, event):
        from .colormap import ColormapManager
        painter = QPainter(self)
        rect = self.rect()
        
        # Draw gradient
        grad = QLinearGradient(0, rect.bottom() - 20, 0, 20)
        lut = ColormapManager.get_colormap(self._cmap_name)
        for i in range(len(lut)):
            pos = i / (len(lut) - 1)
            r, g, b, a = lut[i]
            grad.setColorAt(pos, QColor(r, g, b, 255))
        
        bar_rect = rect.adjusted(10, 20, -30, -20)
        painter.fillRect(bar_rect, grad)
        
        # Draw text labels
        painter.setPen(QColor(100, 100, 100))
        painter.drawText(bar_rect.right() + 5, bar_rect.top() + 10, f"{self._max_val:.1f}")
        painter.drawText(bar_rect.right() + 5, bar_rect.bottom(), f"{self._min_val:.1f}")
        painter.drawText(bar_rect.right() + 5, bar_rect.center().y() + 5, f"{(self._max_val+self._min_val)/2:.1f}")

class SeismicView(QWidget):
    """High-level composite widget for seismic data visualization.

    Combines a 3-D volume renderer (:class:`Renderer3D`), a 2-D profile
    display (:class:`ProfileWidget`), and a toolbar into a single
    drop-in widget.  Supports SEGY file loading, synthetic demo data,
    display-mode switching (VD heatmap / Wiggle trace), colormap
    selection, and horizon overlays.
    """

    def __init__(self, parent=None, path: str | None = None):
        super().__init__(parent)
        self._loader: SeismicLoader | None = None
        self._cache = SeismicCache(max_slices=50)
        self._meta: SeismicVolumeMeta | None = None
        self._horizon_grids: dict[str, np.ndarray] = {}
        self._ds_factor: tuple[int, int, int] = (1, 1, 1)
        self._log = logging.getLogger(__name__)

        # Store raw slice data for export
        self._slice_data: dict[str, np.ndarray | None] = {
            "inline": None, "crossline": None, "time": None, "arbitrary": None
        }

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._renderer_3d = Renderer3D()
        self._colorbar = ColorbarWidget()

        # Create 3 separate profile panels for Inline, Crossline, Time
        self._profile_il = ProfileWidget()
        self._profile_xl = ProfileWidget()
        self._profile_t = ProfileWidget()
        self._profile_arb = ProfileWidget()
        
        self._profile_widget = self._profile_il

        toolbar = self._build_toolbar()
        layout.addWidget(toolbar)

        # --- Main content: 3D view (top) + 3 profiles (bottom) ---
        main_splitter = QSplitter(Qt.Orientation.Vertical)

        # Top: 3D renderer
        main_splitter.addWidget(self._renderer_3d)

        # Bottom: 2x2 grid layout of profiles
        profiles_container = QWidget()
        profiles_layout = QGridLayout(profiles_container)
        profiles_layout.setContentsMargins(0, 0, 0, 0)
        profiles_layout.setSpacing(4)

        profile_panels = [
            ("Inline 剖面", "#e53e3e", self._profile_il, "inline", 0, 0),
            ("Crossline 剖面", "#38a169", self._profile_xl, "crossline", 0, 1),
            ("Time 剖面", "#3182ce", self._profile_t, "time", 1, 0),
            ("任意剖面", "#805ad5", self._profile_arb, "arbitrary", 1, 1),
        ]

        for label, color, profile, key, row, col in profile_panels:
            panel = QWidget()
            panel.setStyleSheet("background: #ffffff; border-radius: 4px;")
            panel_layout = QVBoxLayout(panel)
            panel_layout.setContentsMargins(2, 0, 2, 0)
            panel_layout.setSpacing(2)

            # Header bar with label + export button
            header = QWidget()
            header.setStyleSheet(f"background: #f7fafc; border-bottom: 2px solid {color};")
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(6, 2, 6, 2)
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 12px;")
            header_layout.addWidget(lbl)
            header_layout.addStretch()

            export_btn = QPushButton("导出")
            export_btn.setFixedSize(50, 22)
            export_btn.setStyleSheet(
                "QPushButton { background: #edf2f7; border: 1px solid #cbd5e0; border-radius: 3px; font-size: 11px; }"
                "QPushButton:hover { background: #e2e8f0; }"
            )
            export_btn.clicked.connect(lambda checked, k=key: self._export_slice(k))
            header_layout.addWidget(export_btn)

            panel_layout.addWidget(header)
            panel_layout.addWidget(profile, 1)
            profiles_layout.addWidget(panel, row, col)

        main_splitter.addWidget(profiles_container)
        main_splitter.setSizes([350, 350])
        
        # Make splitter handle visible and draggable
        main_splitter.setHandleWidth(8)
        main_splitter.setStyleSheet(
            "QSplitter::handle:vertical { "
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            "    stop:0 #e2e8f0, stop:0.5 #a0aec0, stop:1 #e2e8f0); "
            "  border: 1px solid #cbd5e0; "
            "  border-radius: 3px; "
            "  margin: 0 40px; "
            "}"
        )
        main_splitter.setCollapsible(0, False)
        main_splitter.setCollapsible(1, False)
        self._renderer_3d.setMinimumHeight(200)
        profiles_container.setMinimumHeight(150)

        # Horizontal layout for splitter + colorbar
        h_layout = QHBoxLayout()
        h_layout.addWidget(main_splitter, stretch=1)
        h_layout.addWidget(self._colorbar)
        layout.addLayout(h_layout)

        # Throttle slice updates: only refresh 2D profile after
        # a short delay of no new slice_changed signals (drag release)
        self._pending_slice: tuple[str, int] | None = None
        self._slice_timer = QTimer(self)
        self._slice_timer.setSingleShot(True)
        # With GPU slicing, we can reduce this from 200ms to near-instant (10ms)
        self._slice_timer.setInterval(10)
        self._slice_timer.timeout.connect(self._apply_pending_slice)

        self._renderer_3d.slice_changed.connect(self._on_slice_changed)
        self._renderer_3d.arbitrary_slice_changed.connect(self._on_arbitrary_changed)

        # Enable polyline drawing on Time panel and wire signal
        self._profile_t._vd.enable_polyline_drawing(True)
        self._profile_t._vd.polyline_changed.connect(self._on_polyline_drawn)

        # Auto-load: SEGY file if path given, else synthetic demo (async)
        if path is not None:
            self.load_segy_async(path)
        else:
            self._profile_il.set_overlay_text("生成合成数据...")
            self._synth_worker = _SyntheticWorker(self)
            self._synth_worker.done.connect(self._on_synthetic_ready)
            self._synth_worker.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_ready(self) -> bool:
        """Return ``True`` once volume data has been loaded."""
        return self._meta is not None

    def display_mode(self) -> str:
        """Current profile display mode (``"vd"`` or ``"wiggle"``)."""
        return self._profile_widget.mode()

    @staticmethod
    def _compute_balanced_spacing(shape: tuple[int, ...], target: float = 200.0) -> tuple[float, float, float]:
        """Compute spacing that normalizes each axis to approximately *target* visual units."""
        ni, nx, nt = shape
        return (
            target / max(ni, 1),
            target / max(nx, 1),
            target / max(nt, 1),
        )

    def load_demo(self, data: np.ndarray):
        """Load a synthetic or pre-computed 3-D volume for quick demo."""
        self._ds_factor = (1, 1, 1)
        
        # Clear existing polyline state
        self._profile_t.clear_polyline()
        self._slice_data.pop("arbitrary", None)
        
        self._meta = SeismicVolumeMeta(
            filename="demo",
            n_inlines=data.shape[0],
            n_crosslines=data.shape[1],
            n_samples=data.shape[2],
            sample_interval=4.0,
            iline_start=0,
            iline_step=1,
            xline_start=0,
            xline_step=1,
            dt_ms=4.0,
        )
        spacing = self._compute_balanced_spacing(data.shape)
        self._renderer_3d.load_volume(data, spacing=spacing)
        self._colorbar.set_range(float(np.nanmin(data)), float(np.nanmax(data)))

        # Populate all 3 profile panels
        mid_il = data.shape[0] // 2
        mid_xl = data.shape[1] // 2
        mid_t = data.shape[2] // 2

        self._update_profile_panel("inline", mid_il, data[mid_il, :, :].T)
        self._update_profile_panel("crossline", mid_xl, data[:, mid_xl, :].T)
        self._update_profile_panel("time", mid_t, data[:, :, mid_t].T)

        self._slice_label.setText(f"IL:{mid_il} XL:{mid_xl} T:{mid_t}")
        self._log.info("Demo loaded: shape=%s", data.shape)

    def load_segy(self, path: str):
        """Load a SEGY file synchronously (for backward compat)."""
        if self._loader is not None:
            self._loader.close()
        self._loader = SeismicLoader(path)
        self._meta = self._loader.inspect()
        self._log.info("SEGY inspected: %s (%dx%dx%d)", path,
                       self._meta.n_inlines, self._meta.n_crosslines,
                       self._meta.n_samples)
        self._ds_factor = (1, 1, 1)
        vol = self._loader.get_volume_downsampled(factor=self._ds_factor)
        self._log.info("Volume downsampled: shape=%s", vol.shape)
        self._renderer_3d.load_volume(vol)
        mid_il = self._meta.iline_start + (self._meta.n_inlines // 2) * self._meta.iline_step
        mid_xl = self._meta.xline_start + (self._meta.n_crosslines // 2) * self._meta.xline_step
        mid_t = self._meta.n_samples // 2
        
        raw_il = self._loader.read_inline(mid_il)
        raw_xl = self._loader.read_crossline(mid_xl)
        raw_t = self._loader.read_timeslice(mid_t)
        
        self._update_profile_panel("inline", mid_il, raw_il.T)
        self._update_profile_panel("crossline", mid_xl, raw_xl.T)
        self._update_profile_panel("time", mid_t, raw_t.T)
        
        self._slice_label.setText(f"Loaded: IL:{mid_il} XL:{mid_xl} T:{mid_t}")

    def load_segy_async(self, path: str):
        """Load a SEGY file in a background thread."""
        if self._loader is not None:
            self._loader.close()
        if hasattr(self, '_segy_worker') and self._segy_worker is not None and self._segy_worker.isRunning():
            self._segy_worker.done.disconnect(self._on_segy_ready)
            self._segy_worker.error.disconnect(self._on_segy_error)
        self._profile_il.set_overlay_text("加载 SEGY...")
        self._segy_worker = _SegyLoadWorker(path, self)
        self._segy_worker.done.connect(self._on_segy_ready)
        self._segy_worker.error.connect(self._on_segy_error)
        self._segy_worker.start()

    def set_display_mode(self, mode: str):
        """Switch the profile display mode (``"vd"`` or ``"wiggle"``)."""
        for pw in (self._profile_il, self._profile_xl, self._profile_t, self._profile_arb):
            pw.set_display_mode(mode)

    # ------------------------------------------------------------------
    # Async callbacks
    # ------------------------------------------------------------------

    @Slot(object)
    def _on_synthetic_ready(self, data: np.ndarray):
        self.load_demo(data)
        self._profile_il.set_overlay_text(None)

    @Slot(object)
    def _on_segy_ready(self, result: tuple):
        meta, vol, raw_il, raw_xl, raw_t, path = result
        self._loader = SeismicLoader(path)
        self._meta = meta
        self._ds_factor = (1, 1, 1)
        
        # Clear existing polyline state
        self._profile_t.clear_polyline()
        self._slice_data.pop("arbitrary", None)
        
        self._log.info("SEGY loaded async: (%dx%dx%d), vol shape=%s",
                       meta.n_inlines, meta.n_crosslines, meta.n_samples,
                       vol.shape)
        spacing = self._compute_balanced_spacing(vol.shape)
        self._renderer_3d.load_volume(vol, spacing=spacing)
        self._colorbar.set_range(float(np.nanmin(vol)), float(np.nanmax(vol)))
        
        mid_il = meta.iline_start + (meta.n_inlines // 2) * meta.iline_step
        mid_xl = meta.xline_start + (meta.n_crosslines // 2) * meta.xline_step
        mid_t = meta.n_samples // 2  # Sample index for time
        
        self._update_profile_panel("inline", mid_il, raw_il.T)
        self._update_profile_panel("crossline", mid_xl, raw_xl.T)
        self._update_profile_panel("time", mid_t, raw_t.T)
        
        self._slice_label.setText(f"Loaded: IL:{mid_il} XL:{mid_xl} T:{mid_t}")
        self._profile_il.set_overlay_text(None)

    @Slot(str)
    def _on_segy_error(self, msg: str):
        self._log.error("SEGY load failed: %s", msg)
        self._profile_il.set_overlay_text(f"加载失败: {msg}")

    # ------------------------------------------------------------------
    # Synthetic data generation
    # ------------------------------------------------------------------

    @Slot(int)
    def _on_3d_mode_changed(self, index: int):
        mode = "planes" if index == 0 else "volume"
        self._renderer_3d.set_render_mode(mode)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_toolbar(self) -> QWidget:
        bar = QToolBar()

        load_btn = QPushButton("加载 SEGY")
        load_btn.clicked.connect(self._load_segy)
        demo_btn = QPushButton("Demo")
        demo_btn.clicked.connect(self._load_demo_data)
        horizon_btn = QPushButton("层位")
        horizon_btn.clicked.connect(self._load_horizon)

        self._slice_type_combo = QComboBox()
        self._slice_type_combo.addItems(["Inline", "Crossline", "Time"])
        self._slice_type_combo.currentIndexChanged.connect(
            self._on_slice_type_changed
        )

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["VD 热图", "Wiggle 波形"])
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        self._cmap_combo = QComboBox()
        self._cmap_combo.addItems(["seismic", "gray", "jet"])
        self._cmap_combo.currentTextChanged.connect(
            lambda name: [pw.set_colormap(name) for pw in (self._profile_il, self._profile_xl, self._profile_t, self._profile_arb)]
        )
        self._cmap_combo.currentTextChanged.connect(
            self._colorbar.set_colormap
        )

        self._3d_mode_combo = QComboBox()
        self._3d_mode_combo.addItems(["正交切片", "三维体"])
        self._3d_mode_combo.currentIndexChanged.connect(self._on_3d_mode_changed)

        self._slice_label = QLabel("未加载")
        self._slice_label.setStyleSheet("color: #888; padding: 0 8px;")

        bar.addWidget(load_btn)
        bar.addWidget(demo_btn)
        bar.addWidget(horizon_btn)
        bar.addWidget(QLabel(" 3D模式:"))
        bar.addWidget(self._3d_mode_combo)
        bar.addWidget(QLabel(" 剖面:"))
        bar.addWidget(self._slice_type_combo)
        bar.addWidget(QLabel(" 显示:"))
        bar.addWidget(self._mode_combo)
        bar.addWidget(QLabel(" 色标:"))
        bar.addWidget(self._cmap_combo)
        bar.addWidget(self._slice_label)
        return bar

    def _build_slice_info(self, slice_type: str, position: int,
                          data_shape: tuple) -> SliceInfo:
        if self._meta is None:
            return SliceInfo(
                slice_type=slice_type, position=position,
                axis_h_label="X", axis_v_label="Y",
                axis_h_values=[0.0], axis_v_values=[0.0],
            )
        m = self._meta
        n_h = data_shape[1] if len(data_shape) > 1 else data_shape[0]
        n_v = data_shape[0]

        if slice_type == "inline":
            h_arr = np.arange(n_h) * m.xline_step + m.xline_start
            v_arr = np.arange(n_v) * m.dt_ms + m.t0_ms
            return SliceInfo(
                slice_type=slice_type, position=position,
                axis_h_label="Crossline", axis_v_label="Time (ms)",
                axis_h_values=h_arr.tolist(),
                axis_v_values=v_arr.tolist(),
            )
        elif slice_type == "crossline":
            h_arr = np.arange(n_h) * m.iline_step + m.iline_start
            v_arr = np.arange(n_v) * m.dt_ms + m.t0_ms
            return SliceInfo(
                slice_type=slice_type, position=position,
                axis_h_label="Inline", axis_v_label="Time (ms)",
                axis_h_values=h_arr.tolist(),
                axis_v_values=v_arr.tolist(),
            )
        else:  # time
            h_arr = np.arange(n_h) * m.iline_step + m.iline_start
            v_arr = np.arange(n_v) * m.xline_step + m.xline_start
            return SliceInfo(
                slice_type=slice_type, position=position,
                axis_h_label="Inline", axis_v_label="Crossline",
                axis_h_values=h_arr.tolist(),
                axis_v_values=v_arr.tolist(),
            )

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @Slot(object)
    def _on_arbitrary_changed(self, data: np.ndarray):
        """Receive polyline-driven arbitrary slice data from Renderer3D."""
        if data is None:
            return
        
        self._slice_data["arbitrary"] = data.copy()
        
        m = self._meta
        info = SliceInfo(
            slice_type="arbitrary",
            position=0,
            axis_h_label="Distance",
            axis_v_label="Time (ms)" if m else "Sample",
            axis_h_values=np.arange(data.shape[1]).tolist(),
            axis_v_values=(np.arange(data.shape[0]) * (m.dt_ms if m else 1.0)).tolist()
        )
        
        self._profile_arb.update_profile(data, slice_info=info)

    @Slot(list)
    def _on_polyline_drawn(self, frac_points: list):
        """Convert fractional Time-slice coordinates to index-space and forward to 3D."""
        vol = self._renderer_3d._volume_data_cpu
        if vol is None or len(frac_points) < 2:
            return
        
        ni, nx, nt = vol.shape
        
        # frac_points are (col_frac, row_frac) on the Time slice
        # Time slice data shape is (n_xlines, n_inlines) after .T
        # col_frac maps to inline, row_frac maps to crossline
        index_points = []
        for col_frac, row_frac in frac_points:
            il_idx = col_frac * (ni - 1)
            xl_idx = row_frac * (nx - 1)
            index_points.append((il_idx, xl_idx))
        
        self._renderer_3d.set_arbitrary_polyline(index_points)

    @Slot(str, int)
    def _on_slice_changed(self, slice_type: str, position: int):
        self._pending_slice = (slice_type, position)
        self._slice_timer.start()  # Resets timer on each drag move

    @Slot()
    def _apply_pending_slice(self):
        if self._pending_slice is None:
            return
        slice_type, position = self._pending_slice
        self._pending_slice = None
        if self._meta is None:
            return

        # Demo mode: slice from cached volume data directly
        if self._loader is None:
            vol = self._renderer_3d._volume_data_cpu
            if vol is None:
                return
            if slice_type == "inline":
                raw = vol[position, :, :]
            elif slice_type == "crossline":
                raw = vol[:, position, :]
            else:
                raw = vol[:, :, position]
            self._update_profile_panel(slice_type, position, raw.T)
            return

        # Plane widget gives downsampled voxel indices.
        # Convert to actual inline/crossline numbers for segyio.
        m = self._meta
        df = self._ds_factor
        if slice_type == "inline":
            actual_pos = m.iline_start + position * df[0] * m.iline_step
        elif slice_type == "crossline":
            actual_pos = m.xline_start + position * df[1] * m.xline_step
        else:
            actual_pos = position * df[2]

        cache_key = (slice_type, actual_pos)
        cached = self._cache.get(cache_key)
        if cached is not None:
            raw = cached
            self._log.debug("Cache hit: %s %d", slice_type, actual_pos)
        else:
            self._log.debug("Cache miss: %s %d, reading from disk",
                            slice_type, actual_pos)
            try:
                if slice_type == "inline":
                    raw = self._loader.read_inline(actual_pos)
                elif slice_type == "crossline":
                    raw = self._loader.read_crossline(actual_pos)
                else:
                    raw = self._loader.read_timeslice(actual_pos)
            except Exception as exc:
                self._log.error("Failed to read %s %d: %s",
                                slice_type, actual_pos, exc)
                self._slice_label.setText(f"Read error: {slice_type} {actual_pos}")
                return
            self._cache.put(cache_key, raw)

        self._update_profile_panel(slice_type, actual_pos, raw.T)

    def _update_profile_panel(self, slice_type: str, position: int, slice_2d: np.ndarray):
        """Route slice data to the correct profile panel and cache raw data for export."""
        info = self._build_slice_info(slice_type, position, slice_2d.shape)
        self._slice_data[slice_type] = slice_2d.copy()

        if slice_type == "inline":
            self._profile_il.update_profile(slice_2d, slice_info=info)
        elif slice_type == "crossline":
            self._profile_xl.update_profile(slice_2d, slice_info=info)
        else:
            self._profile_t.update_profile(slice_2d, slice_info=info)

        self._slice_label.setText(f"{slice_type.capitalize()} {position}")

    def _export_slice(self, slice_type: str):
        """Export the current slice data for the given type as CSV."""
        data = self._slice_data.get(slice_type)
        if data is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, f"导出 {slice_type.capitalize()} 剖面数据",
            f"{slice_type}_slice.csv",
            "CSV Files (*.csv);;NumPy Files (*.npy)"
        )
        if not path:
            return
        try:
            if path.endswith(".npy"):
                np.save(path, data)
            else:
                np.savetxt(path, data, delimiter=",", fmt="%.6f")
            self._log.info("Exported %s slice to %s", slice_type, path)
        except Exception as exc:
            self._log.error("Export failed: %s", exc)

    def _load_segy(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 SEGY 文件", "", "SEGY Files (*.sgy *.segy)"
        )
        if path:
            self.load_segy_async(path)

    def _load_demo_data(self):
        if (hasattr(self, '_synth_worker')
                and self._synth_worker is not None
                and self._synth_worker.isRunning()):
            self._synth_worker.done.disconnect(self._on_synthetic_ready)
        self._profile_widget.set_overlay_text("生成合成数据...")
        self._synth_worker = _SyntheticWorker(self)
        self._synth_worker.done.connect(self._on_synthetic_ready)
        self._synth_worker.start()

    def _load_horizon(self):
        if self._meta is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "选择层位文件 (格式: inline  crossline  time_ms, tab分隔)",
            "", "Horizon Files (*.txt *.dat *.hor)",
        )
        if not path:
            return
        axes = {
            "ilines": np.arange(
                self._meta.iline_start,
                self._meta.iline_start
                + self._meta.n_inlines * self._meta.iline_step,
                self._meta.iline_step,
            ),
            "xlines": np.arange(
                self._meta.xline_start,
                self._meta.xline_start
                + self._meta.n_crosslines * self._meta.xline_step,
                self._meta.xline_step,
            ),
            "nI": self._meta.n_inlines,
            "nX": self._meta.n_crosslines,
        }
        parser = HorizonParser(path, unit="ms")
        grid = parser.parse(axes)
        filled = parser.fill_nearest(grid)
        self._renderer_3d.add_horizon(filled)

    def _on_mode_changed(self, index: int):
        mode = "vd" if index == 0 else "wiggle"
        for pw in (self._profile_il, self._profile_xl, self._profile_t, self._profile_arb):
            pw.set_display_mode(mode)

    def _on_slice_type_changed(self, index: int):
        pass  # Slice type is controlled by 3D plane widgets
