from __future__ import annotations

import logging
import numpy as np
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QSplitter,
    QPushButton, QComboBox, QLabel, QFileDialog, QToolBar,
)

from .renderer_3d import Renderer3D
from .profile_widget import ProfileWidget
from .loader import SeismicLoader
from .horizon import HorizonParser
from .cache import SeismicCache
from .models import SeismicVolumeMeta, SliceInfo


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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = self._build_toolbar()
        layout.addWidget(toolbar)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self._renderer_3d = Renderer3D()
        self._profile_widget = ProfileWidget()
        splitter.addWidget(self._renderer_3d)
        splitter.addWidget(self._profile_widget)
        splitter.setSizes([400, 300])
        layout.addWidget(splitter)

        # Throttle slice updates: only refresh 2D profile after
        # 200ms of no new slice_changed signals (drag release)
        self._pending_slice: tuple[str, int] | None = None
        self._slice_timer = QTimer(self)
        self._slice_timer.setSingleShot(True)
        self._slice_timer.setInterval(200)
        self._slice_timer.timeout.connect(self._apply_pending_slice)

        self._renderer_3d.slice_changed.connect(self._on_slice_changed)

        # Auto-load: SEGY file if path given, else synthetic demo
        if path is not None:
            self.load_segy(path)
        else:
            self.load_demo(self._generate_synthetic())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_ready(self) -> bool:
        """Return ``True`` once the widget is fully initialised."""
        return True

    def is_loaded(self) -> bool:
        """Return ``True`` when a volume has been loaded."""
        return self._meta is not None

    def display_mode(self) -> str:
        """Current profile display mode (``"vd"`` or ``"wiggle"``)."""
        return self._profile_widget._mode

    def load_demo(self, data: np.ndarray):
        """Load a synthetic or pre-computed 3-D volume for quick demo."""
        self._ds_factor = (1, 1, 1)
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
        self._renderer_3d.load_volume(data)
        mid = data.shape[0] // 2
        slice_2d = data[mid].T  # (n_xlines, n_samples) → (n_samples, n_xlines)
        info = self._build_slice_info("inline", mid, slice_2d.shape)
        self._profile_widget.update_profile(slice_2d, slice_info=info)
        self._slice_label.setText(f"Inline {mid}")
        self._log.info("Demo loaded: shape=%s", data.shape)

    def load_segy(self, path: str):
        """Load a SEGY file, down-sample for 3-D display, and show mid-inline."""
        if self._loader is not None:
            self._loader.close()
        self._loader = SeismicLoader(path)
        self._meta = self._loader.inspect()
        self._log.info("SEGY inspected: %s (%dx%dx%d)", path,
                       self._meta.n_inlines, self._meta.n_crosslines,
                       self._meta.n_samples)
        self._ds_factor = (4, 4, 2)
        vol = self._loader.get_volume_downsampled(factor=self._ds_factor)
        self._log.info("Volume downsampled: shape=%s", vol.shape)
        self._renderer_3d.load_volume(vol)
        mid_il = (self._meta.iline_start
                  + self._meta.n_inlines // 2 * self._meta.iline_step)
        raw = self._loader.read_inline(mid_il)
        slice_2d = raw.T  # (n_xlines, n_samples) → (n_samples, n_xlines)
        info = self._build_slice_info("inline", mid_il, slice_2d.shape)
        self._profile_widget.update_profile(slice_2d, slice_info=info)
        self._slice_label.setText(f"Inline {mid_il}")

    def set_display_mode(self, mode: str):
        """Switch the profile display mode (``"vd"`` or ``"wiggle"``)."""
        self._profile_widget.set_display_mode(mode)

    # ------------------------------------------------------------------
    # Synthetic data generation
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_synthetic(
        n_inlines: int = 60, n_crosslines: int = 80,
        n_samples: int = 100,
    ) -> np.ndarray:
        """Generate synthetic seismic with geologically realistic structure:
        horizontal reflectors with gentle dip, a fault offset, and noise."""
        t = np.linspace(0, 4 * np.pi, n_samples, dtype=np.float32)
        il = np.arange(n_inlines, dtype=np.float32)
        xl = np.arange(n_crosslines, dtype=np.float32)
        # Reflector field: sine waves with gentle dip along inline
        field = np.zeros((n_inlines, n_crosslines, n_samples), dtype=np.float32)
        for i in range(n_inlines):
            dip = 0.02 * i  # gentle dip
            reflector = np.sin(t + dip) + 0.5 * np.sin(2.3 * t + dip)
            field[i, :] = reflector[np.newaxis, :]
        # Add a normal fault at inline 30, offsetting by 5 samples
        fault_il = n_inlines // 2
        offset = 5
        field[fault_il:, :, offset:] = field[fault_il:, :, :-offset].copy()
        field[fault_il:, :, :offset] = 0
        # Add Gaussian noise
        rng = np.random.default_rng(42)
        noise = rng.normal(0, 0.15, field.shape).astype(np.float32)
        return field + noise

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
            self._profile_widget.set_colormap
        )

        self._slice_label = QLabel("未加载")
        self._slice_label.setStyleSheet("color: #888; padding: 0 8px;")

        bar.addWidget(load_btn)
        bar.addWidget(demo_btn)
        bar.addWidget(horizon_btn)
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
        if slice_type == "inline":
            h_vals = [m.xline_start + i * m.xline_step
                      for i in range(data_shape[1] if len(data_shape) > 1
                                     else data_shape[0])]
            v_vals = [m.t0_ms + i * m.dt_ms for i in range(data_shape[0])]
            return SliceInfo(
                slice_type=slice_type, position=position,
                axis_h_label="Crossline", axis_v_label="Time (ms)",
                axis_h_values=[float(v) for v in h_vals],
                axis_v_values=[float(v) for v in v_vals],
            )
        elif slice_type == "crossline":
            h_vals = [m.iline_start + i * m.iline_step
                      for i in range(data_shape[1] if len(data_shape) > 1
                                     else data_shape[0])]
            v_vals = [m.t0_ms + i * m.dt_ms for i in range(data_shape[0])]
            return SliceInfo(
                slice_type=slice_type, position=position,
                axis_h_label="Inline", axis_v_label="Time (ms)",
                axis_h_values=[float(v) for v in h_vals],
                axis_v_values=[float(v) for v in v_vals],
            )
        else:  # time
            h_vals = [m.iline_start + i * m.iline_step
                      for i in range(data_shape[1] if len(data_shape) > 1
                                     else data_shape[0])]
            v_vals = [m.xline_start + i * m.xline_step
                      for i in range(data_shape[0])]
            return SliceInfo(
                slice_type=slice_type, position=position,
                axis_h_label="Inline", axis_v_label="Crossline",
                axis_h_values=[float(v) for v in h_vals],
                axis_v_values=[float(v) for v in v_vals],
            )

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

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
            vol = self._renderer_3d._volume_data
            if vol is None:
                return
            if slice_type == "inline":
                raw = vol[position, :, :]
            elif slice_type == "crossline":
                raw = vol[:, position, :]
            else:
                raw = vol[:, :, position]
            slice_2d = raw.T
            info = self._build_slice_info(slice_type, position, slice_2d.shape)
            self._profile_widget.update_profile(slice_2d, slice_info=info)
            self._slice_label.setText(f"{slice_type.capitalize()} {position}")
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

        slice_2d = raw.T  # (n_traces, n_samples) → (n_samples, n_traces)
        info = self._build_slice_info(slice_type, actual_pos, slice_2d.shape)
        self._profile_widget.update_profile(slice_2d, slice_info=info)
        self._slice_label.setText(
            f"{slice_type.capitalize()} {actual_pos}"
        )

    def _load_segy(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 SEGY 文件", "", "SEGY Files (*.sgy *.segy)"
        )
        if path:
            self.load_segy(path)

    def _load_demo_data(self):
        self.load_demo(self._generate_synthetic())

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
        if index == 0:
            self._profile_widget.set_display_mode("vd")
        else:
            self._profile_widget.set_display_mode("wiggle")

    def _on_slice_type_changed(self, index: int):
        pass  # Slice type is controlled by 3D plane widgets
