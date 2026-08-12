from __future__ import annotations

import logging
import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QCoreApplication
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QSplitter,
    QPushButton, QComboBox, QLabel, QFileDialog, QToolBar,
    QDoubleSpinBox, QSlider, QCheckBox,
)

from .renderer_3d import Renderer3D
from .profile_widget import ProfileWidget
from .loader import SeismicLoader
from .horizon import HorizonParser
from .cache import SeismicCache
from .colorbar_widget import ColorbarWidget
from .workers import (
    DEFAULT_MAX_PREVIEW_VOXELS,
    SegyLoadWorker,
    SeismicLoadError,
    SeismicLoadResult,
    SliceReadWorker,
    SyntheticWorker,
    downsample_factor_for_budget,
    retain_background_worker,
)
from .dialogs.crossplot import CrossplotDialog
from .dialogs.horizon_manager import HorizonManagerDialog
from .models import SeismicVolumeMeta, SliceInfo

class SeismicView(QWidget):
    """High-level composite widget for seismic data visualization.

    Combines a 3-D volume renderer (:class:`Renderer3D`), a 2-D profile
    display (:class:`ProfileWidget`), and a toolbar into a single
    drop-in widget.  Supports SEGY file loading, synthetic demo data,
    display-mode switching (VD heatmap / Wiggle trace), colormap
    selection, and horizon overlays.
    """

    segy_loaded = Signal(object)  # SeismicLoadResult

    def __init__(self, parent=None, path: str | None = None, auto_load: bool = True):
        super().__init__(parent)
        self._loader: SeismicLoader | None = None
        self._segy_path: str | None = None
        self._cache = SeismicCache(max_slices=50)
        # A slice reader is only useful once a real SEGY is opened.  Deferring
        # it avoids a permanent QThread per unopened/project-hidden view and
        # keeps ordinary project/session teardown bounded.
        self._slice_worker_stopped = True
        self._slice_worker: SliceReadWorker | None = None
        self._meta: SeismicVolumeMeta | None = None
        self._horizon_grids: dict[str, np.ndarray] = {}
        self._ds_factor: tuple[int, int, int] = (1, 1, 1)
        self._log = logging.getLogger(__name__)
        self._segy_generation = 0
        self._segy_worker: SegyLoadWorker | None = None
        self._segy_workers: set[SegyLoadWorker] = set()

        # Horizon picking state
        self._picked_points: list[tuple[float, float, float]] = []  # (il, xl, t)

        # Store raw slice data for export
        self._slice_data: dict[str, np.ndarray | None] = {
            "inline": None, "crossline": None, "time": None, "arbitrary": None
        }

        # Well-tie panel state (created lazily on toggle)
        self._well_tie_panel = None

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
            panel.setStyleSheet("background: #faf9f5; border: 1.6px solid #586878; border-radius: 8px;")
            panel_layout = QVBoxLayout(panel)
            panel_layout.setContentsMargins(2, 0, 2, 0)
            panel_layout.setSpacing(2)

            # Header bar with label + export button
            header = QWidget()
            header.setStyleSheet(f"background: #f0f4f8; border-bottom: 1.6px solid {color}; border-top-left-radius: 6px; border-top-right-radius: 6px;")
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(6, 2, 6, 2)
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 11px;")
            header_layout.addWidget(lbl)
            header_layout.addStretch()

            export_btn = QPushButton()
            export_btn.setIcon(self._get_ui_icon("export.svg"))
            export_btn.setFixedSize(26, 22)
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
        self._pending_slice: dict[str, int] = {}
        # Latest requested actual position per axis; guards against stale
        # in-flight worker results overwriting a newer panel position.
        self._latest_slice_request: dict[str, int] = {}
        self._slice_timer = QTimer(self)
        self._slice_timer.setSingleShot(True)
        self._slice_timer.setInterval(16)
        self._slice_timer.timeout.connect(self._apply_pending_slice)

        self._renderer_3d.slice_changed.connect(self._on_slice_changed)
        self._renderer_3d.arbitrary_slice_changed.connect(self._on_arbitrary_changed)
        self._renderer_3d.jump_to_position.connect(self._on_jump)

        # Enable polyline drawing on Time panel and wire signal
        self._profile_t._vd.enable_polyline_drawing(True)
        self._profile_t._vd.polyline_changed.connect(self._on_polyline_drawn)

        # Cross-hair cursor linking between IL/XL/T panels (via 3D-aware signal)
        for pw in (self._profile_il, self._profile_xl, self._profile_t):
            pw._vd.cursor_moved_3d.connect(self._on_cursor_3d)

        # Shift+wheel slice browsing
        self._profile_il._vd.slice_step_requested.connect(lambda d: self._on_slice_step("inline", d))
        self._profile_xl._vd.slice_step_requested.connect(lambda d: self._on_slice_step("crossline", d))
        self._profile_t._vd.slice_step_requested.connect(lambda d: self._on_slice_step("time", d))

        # Amplitude readout from all panels
        for pw in (self._profile_il, self._profile_xl, self._profile_t, self._profile_arb):
            pw._vd.amplitude_readout.connect(self._on_amplitude_readout)

        # Horizon picking signals
        for pw in (self._profile_il, self._profile_xl, self._profile_t):
            pw._vd.horizon_picked.connect(self._on_horizon_picked)

        # Annotation signals
        for pw in (self._profile_il, self._profile_xl, self._profile_t):
            pw._vd.annotation_added.connect(self._on_annotation_added)

        # Auto-load: SEGY file if path given, else synthetic demo (async)
        if path is not None:
            self.load_segy_async(path)
        elif auto_load:
            self._profile_il.set_overlay_text("生成合成数据...")
            self._synth_worker = SyntheticWorker()
            retain_background_worker(self._synth_worker)
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

    def cleanup(self):
        """Stop background workers and cleanup GPU resources before page switch."""
        self.cancel_pending_segy_load()

        if hasattr(self, '_synth_worker') and self._synth_worker is not None:
            if self._synth_worker.isRunning():
                self._synth_worker.requestInterruption()

        self._stop_slice_worker()

    def _stop_slice_worker(self) -> None:
        """Stop the slice-read worker exactly once (idempotent)."""
        if self._slice_worker is not None and not self._slice_worker_stopped:
            self._slice_worker_stopped = True
            self._slice_worker.stop()

    def _ensure_slice_worker(self) -> None:
        if self._slice_worker is None:
            # Keep the QThread unparented but retained until it stops: parenting
            # it to this widget aborts if QWidget disposal reaches it first.
            worker = SliceReadWorker()
            worker.slice_ready.connect(self._on_slice_ready)
            worker.prefetch_ready.connect(self._on_prefetch_ready)
            worker.read_error.connect(self._on_slice_read_error)
            retain_background_worker(worker)
            app = QCoreApplication.instance()
            if app is not None:
                app.aboutToQuit.connect(worker.stop)
            self._slice_worker = worker
        self._slice_worker_stopped = False
        self._slice_worker.ensure_running()

    def __del__(self):
        # Views are often dropped without cleanup() (tests, page switches);
        # the long-lived worker thread must not outlive the process or it
        # aborts at interpreter teardown ("QThread: Destroyed while still
        # running").
        try:
            self._stop_slice_worker()
        except Exception:
            pass

    def cancel_pending_segy_load(self) -> None:
        """Invalidate SEGY callbacks and cooperatively stop active file loads."""
        self._segy_generation += 1
        self._segy_path = None
        for worker in tuple(self._segy_workers):
            if worker.isRunning():
                worker.requestInterruption()
        if self._loader is not None:
            self._loader.close()
            self._loader = None
        # In-flight slice reads are invalidated by the bumped generation.

    def get_project_state(self) -> dict:
        """Return seismic file path and view settings for .gvz persistence."""
        mode_index = self._3d_mode_combo.currentIndex()
        render_mode = "planes" if mode_index == 0 else "volume"
        return {
            "file_path": self._segy_path,
            "slice_positions": {
                "inline": self._tb_il_slider.value(),
                "crossline": self._tb_xl_slider.value(),
                "time": self._tb_t_slider.value(),
            },
            "colormap": self._cmap_combo.currentText(),
            "render_mode": render_mode,
        }

    def apply_project_view_state(self, view_state) -> None:
        """Restore slice positions, colormap, and 3D render mode from project."""
        if view_state is None:
            return
        positions = getattr(view_state, "seismic_slice_positions", None) or {}
        for key, slider in (
            ("inline", self._tb_il_slider),
            ("crossline", self._tb_xl_slider),
            ("time", self._tb_t_slider),
        ):
            if key in positions and slider.maximum() >= positions[key] >= slider.minimum():
                slider.setValue(positions[key])
        cmap = getattr(view_state, "seismic_colormap", None)
        if cmap and self._cmap_combo.findText(cmap) >= 0:
            self._cmap_combo.setCurrentText(cmap)
        render_mode = getattr(view_state, "seismic_render_mode", None)
        if render_mode:
            idx = 0 if render_mode == "planes" else 1
            if idx < self._3d_mode_combo.count():
                self._3d_mode_combo.setCurrentIndex(idx)

    def load_demo(self, data: np.ndarray):
        """Load a synthetic or pre-computed 3-D volume for quick demo."""
        self.cancel_pending_segy_load()
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
        self._setup_toolbar_sliders()
        self._log.info("Demo loaded: shape=%s", data.shape)

    def load_segy(self, path: str):
        """Load a SEGY file in a background thread to keep the GUI responsive."""
        self.load_segy_async(path)

    def load_segy_async(self, path: str):
        """Load a SEGY file in a background thread."""
        self.cancel_pending_segy_load()
        generation = self._segy_generation
        self._segy_path = path
        self._profile_il.set_overlay_text("加载 SEGY...")
        worker = SegyLoadWorker(path, generation=generation)
        retain_background_worker(worker)
        self._segy_workers.add(worker)
        self._segy_worker = worker
        worker.done.connect(self._on_segy_ready)
        worker.error.connect(self._on_segy_error)
        worker.finished.connect(self._on_segy_worker_finished)
        worker.start()

    def load_overlay_volume(self, data: np.ndarray, colormap: str = "jet", opacity: float = 0.5):
        """Load an overlay attribute/property volume and display it superimposed."""
        self._renderer_3d.load_overlay_volume(data, colormap=colormap, opacity=opacity)
        # Sync control states
        self._overlay_opacity_slider.blockSignals(True)
        self._overlay_opacity_slider.setValue(int(opacity * 100))
        self._overlay_opacity_slider.blockSignals(False)

        self._overlay_cmap_combo.blockSignals(True)
        self._overlay_cmap_combo.setCurrentText(colormap)
        self._overlay_cmap_combo.blockSignals(False)

        self._overlay_btn.blockSignals(True)
        self._overlay_btn.setChecked(True)
        self._overlay_btn.blockSignals(False)

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
    def _on_segy_ready(self, result: SeismicLoadResult):
        if result.generation != self._segy_generation or result.path != self._segy_path:
            return
        meta = result.meta
        vol = result.volume
        raw_il = result.raw_inline
        raw_xl = result.raw_crossline
        raw_t = result.raw_timeslice
        self._loader = SeismicLoader(result.path)
        self._ensure_slice_worker()
        self._slice_worker.set_volume(result.path, self._segy_generation)
        self._meta = meta
        self._ds_factor = result.downsample_factor
        
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
        self._setup_toolbar_sliders()
        self.segy_loaded.emit(result)

    @Slot(object)
    def _on_segy_error(self, error: SeismicLoadError):
        if error.generation != self._segy_generation:
            return
        self._log.error("SEGY load failed: %s", error.message)
        self._profile_il.set_overlay_text(f"加载失败: {error.message}")

    @Slot()
    def _on_segy_worker_finished(self):
        worker = self.sender()
        if isinstance(worker, SegyLoadWorker):
            self._segy_workers.discard(worker)
            if self._segy_worker is worker:
                self._segy_worker = None
            worker.deleteLater()

    # ------------------------------------------------------------------
    # Synthetic data generation
    # ------------------------------------------------------------------

    @Slot(int)
    def _on_3d_mode_changed(self, index: int):
        mode = "planes" if index == 0 else "volume"
        self._renderer_3d.set_render_mode(mode)

    @Slot(bool)
    def _on_overlay_toggled(self, checked: bool):
        self._renderer_3d.set_overlay_visible(checked)

    @Slot(str)
    def _on_overlay_cmap_changed(self, cmap_name: str):
        self._renderer_3d.set_overlay_colormap(cmap_name)

    @Slot(int)
    def _on_overlay_opacity_changed(self, value: int):
        opacity = value / 100.0
        self._renderer_3d.set_overlay_opacity(opacity)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_ui_icon(self, name: str) -> QIcon:
        """Resolve icon from project resources."""
        try:
            from src.utils.paths import get_resources_dir
            path = get_resources_dir() / "icons" / "ui" / name
            if path.exists():
                return QIcon(str(path))
        except ImportError:
            pass
        return QIcon()

    def _build_toolbar(self) -> QWidget:
        # Three-row toolbar: 主操作 (row 1) | 视图 (row 2) | 属性与切片 (row 3)
        self._toolbar_row1 = QToolBar()
        self._toolbar_row2 = QToolBar()
        self._toolbar_row3 = QToolBar()
        bar = self._toolbar_row1  # row 1 is primary actions (load/pick/tie)

        load_btn = QPushButton(" 加载 SEGY")
        load_btn.setIcon(self._get_ui_icon("upload.svg"))
        load_btn.clicked.connect(self._load_segy)
        
        demo_btn = QPushButton(" Demo")
        demo_btn.setIcon(self._get_ui_icon("play.svg"))
        demo_btn.clicked.connect(self._load_demo_data)
        
        horizon_btn = QPushButton(" 层位")
        horizon_btn.setIcon(self._get_ui_icon("layers.svg"))
        horizon_btn.clicked.connect(self._load_horizon)

        horizon_list_btn = QPushButton(" 层位管理")
        horizon_list_btn.setIcon(self._get_ui_icon("table.svg"))
        horizon_list_btn.clicked.connect(self._show_horizon_list)

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
        # Keep the first-load experience aligned with the interactive 3D host:
        # show the volume instead of hiding it behind the orthogonal slice mode.
        self._3d_mode_combo.setCurrentIndex(1)

        self._opacity_combo = QComboBox()
        self._opacity_combo.addItems(["透明度: 锐利", "透明度: 线性", "透明度: S曲线", "透明度: 阈值"])
        self._opacity_combo.currentIndexChanged.connect(self._on_opacity_changed)

        self._hillshade_btn = QPushButton(" 光照")
        self._hillshade_btn.setCheckable(True)
        self._hillshade_btn.setIcon(self._get_ui_icon("layers.svg")) # reusing icon for now
        self._hillshade_btn.toggled.connect(self._on_hillshade_toggled)

        self._sculpt_horizon_combo = QComboBox()
        self._sculpt_horizon_combo.addItem("无")
        self._sculpt_horizon_combo.currentTextChanged.connect(self._on_sculpt_changed)
        
        self._sculpt_mode_combo = QComboBox()
        self._sculpt_mode_combo.addItems(["保留下部", "保留上部"])
        self._sculpt_mode_combo.currentTextChanged.connect(self._on_sculpt_changed)

        self._clip_spin = QDoubleSpinBox()
        self._clip_spin.setRange(50.0, 99.9)
        self._clip_spin.setValue(99.0)
        self._clip_spin.setSuffix("%")
        self._clip_spin.setSingleStep(1.0)
        self._clip_spin.setDecimals(1)
        self._clip_spin.setFixedWidth(80)
        self._clip_spin.valueChanged.connect(self._on_clip_changed)

        self._iso_checkbox = QCheckBox(" 等值面")
        self._iso_checkbox.setEnabled(False)
        self._iso_checkbox.toggled.connect(self._on_isosurface_toggled)
        self._iso_spin = QDoubleSpinBox()
        self._iso_spin.setDecimals(3)
        self._iso_spin.setFixedWidth(90)
        self._iso_spin.setEnabled(False)
        self._iso_spin.valueChanged.connect(self._on_isosurface_threshold_changed)
        self._iso_timer = QTimer(self)
        self._iso_timer.setSingleShot(True)
        self._iso_timer.setInterval(200)
        self._iso_timer.timeout.connect(self._rebuild_isosurface)

        # Toolbar slice sliders
        self._tb_il_slider = QSlider(Qt.Orientation.Horizontal)
        self._tb_xl_slider = QSlider(Qt.Orientation.Horizontal)
        self._tb_t_slider = QSlider(Qt.Orientation.Horizontal)
        self._tb_il_label = QLabel("IL --")
        self._tb_xl_label = QLabel("XL --")
        self._tb_t_label = QLabel("T --")
        for s in (self._tb_il_slider, self._tb_xl_slider, self._tb_t_slider):
            s.setRange(0, 0)
            s.setEnabled(False)
            s.setFixedWidth(100)
            s.setStyleSheet(
                "QSlider::groove:horizontal{height:4px;background:#e2e8f0;border-radius:2px;}"
                "QSlider::handle:horizontal{background:#586878;width:12px;height:12px;"
                "margin:-4px 0;border-radius:6px;}"
            )
        self._tb_il_slider.setStyleSheet(
            "QSlider::groove:horizontal{height:4px;background:#e2e8f0;border-radius:2px;}"
            "QSlider::handle:horizontal{background:#e53e3e;width:12px;height:12px;"
            "margin:-4px 0;border-radius:6px;}"
        )
        self._tb_xl_slider.setStyleSheet(
            "QSlider::groove:horizontal{height:4px;background:#e2e8f0;border-radius:2px;}"
            "QSlider::handle:horizontal{background:#38a169;width:12px;height:12px;"
            "margin:-4px 0;border-radius:6px;}"
        )
        self._tb_t_slider.setStyleSheet(
            "QSlider::groove:horizontal{height:4px;background:#e2e8f0;border-radius:2px;}"
            "QSlider::handle:horizontal{background:#3182ce;width:12px;height:12px;"
            "margin:-4px 0;border-radius:6px;}"
        )
        self._tb_il_label.setStyleSheet("color: #e53e3e; font-size: 11px; font-weight: bold;")
        self._tb_xl_label.setStyleSheet("color: #38a169; font-size: 11px; font-weight: bold;")
        self._tb_t_label.setStyleSheet("color: #3182ce; font-size: 11px; font-weight: bold;")

        self._tb_il_slider.valueChanged.connect(lambda v: self._on_tb_slider_changed("inline", v))
        self._tb_xl_slider.valueChanged.connect(lambda v: self._on_tb_slider_changed("crossline", v))
        self._tb_t_slider.valueChanged.connect(lambda v: self._on_tb_slider_changed("time", v))

        self._slice_label = QLabel("未加载")
        self._slice_label.setStyleSheet("color: #888; padding: 0 8px;")

        self._readout_label = QLabel("")
        self._readout_label.setStyleSheet(
            "color: #2d3748; font-size: 12px; font-family: monospace; padding: 0 8px;"
        )
        self._readout_label.setMinimumWidth(300)

        self._pick_btn = QPushButton(" 拾取层位")
        self._pick_btn.setCheckable(True)
        self._pick_btn.setIcon(self._get_ui_icon("pin.svg"))
        self._pick_btn.toggled.connect(self._on_pick_toggled)

        clear_pick_btn = QPushButton(" 清除拾取")
        clear_pick_btn.setIcon(self._get_ui_icon("undo.svg"))
        clear_pick_btn.clicked.connect(self._on_clear_picks)

        export_pick_btn = QPushButton(" 导出层位")
        export_pick_btn.setIcon(self._get_ui_icon("export.svg"))
        export_pick_btn.clicked.connect(self._on_export_picks)

        self._annotation_btn = QPushButton(" 标注")
        self._annotation_btn.setCheckable(True)
        self._annotation_btn.setIcon(self._get_ui_icon("plus.svg"))
        self._annotation_btn.toggled.connect(self._on_annotation_toggled)

        # Attribute combo + RGB fusion channel selectors
        from . import attribute_pipeline as _ap
        self._attr_combo = QComboBox()
        self._attr_combo.addItems(_ap.labels())
        self._attr_combo.currentIndexChanged.connect(self._on_attr_changed)

        self._rgb_r_combo = QComboBox()
        self._rgb_g_combo = QComboBox()
        self._rgb_b_combo = QComboBox()
        _attr_names = ["包络", "瞬时频率", "RMS振幅", "甜点", "相对阻抗"]
        for combo in (self._rgb_r_combo, self._rgb_g_combo, self._rgb_b_combo):
            combo.addItems(_attr_names)
            combo.setVisible(False)
            combo.currentIndexChanged.connect(self._on_rgb_channels_changed)
        self._rgb_r_combo.setCurrentIndex(0)
        self._rgb_g_combo.setCurrentIndex(1)
        self._rgb_b_combo.setCurrentIndex(2)
        self._rgb_r_label = QLabel(" R:")
        self._rgb_g_label = QLabel(" G:")
        self._rgb_b_label = QLabel(" B:")
        for lbl in (self._rgb_r_label, self._rgb_g_label, self._rgb_b_label):
            lbl.setVisible(False)

        crossplot_btn = QPushButton(" 交叉图")
        crossplot_btn.setIcon(self._get_ui_icon("plots.svg"))
        crossplot_btn.clicked.connect(self._on_crossplot)

        # Overlay volume controls (Phase 12a)
        self._overlay_btn = QPushButton(" 叠加")
        self._overlay_btn.setCheckable(True)
        self._overlay_btn.setIcon(self._get_ui_icon("layers.svg"))
        self._overlay_btn.toggled.connect(self._on_overlay_toggled)

        self._overlay_cmap_combo = QComboBox()
        self._overlay_cmap_combo.addItems(["jet", "gray", "seismic"])
        self._overlay_cmap_combo.currentTextChanged.connect(self._on_overlay_cmap_changed)

        self._overlay_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._overlay_opacity_slider.setRange(0, 100)
        self._overlay_opacity_slider.setValue(50)
        self._overlay_opacity_slider.setFixedWidth(80)
        self._overlay_opacity_slider.setStyleSheet(
            "QSlider::groove:horizontal{height:3px;background:#e2e8f0;border-radius:1px;}"
            "QSlider::handle:horizontal{background:#319795;width:10px;height:10px;"
            "margin:-4px 0;border-radius:5px;}"
        )
        self._overlay_opacity_slider.valueChanged.connect(self._on_overlay_opacity_changed)

        self.btn_coord = QPushButton(" 📍 网格(IL/XL)")
        self.btn_coord.setCheckable(True)
        self.btn_coord.setStyleSheet("QPushButton:checked { background: #2563eb; color: #ffffff; font-weight: bold; }")
        self._coord_mode = "grid"
        self.btn_coord.clicked.connect(self._toggle_coord_mode)

        bar.addWidget(load_btn)
        bar.addWidget(demo_btn)
        bar.addWidget(self.btn_coord)
        bar.addWidget(horizon_btn)
        bar.addWidget(horizon_list_btn)
        bar.addSeparator()
        bar.addWidget(self._pick_btn)
        bar.addWidget(clear_pick_btn)
        bar.addWidget(export_pick_btn)
        bar.addWidget(self._annotation_btn)
        bar.addSeparator()
        bar.addWidget(self._slice_label)
        bar.addWidget(self._readout_label)

        # Well-tie toggle button on row 1 (right-aligned via stretch later)
        self._well_tie_btn = QPushButton(" 井震标定")
        self._well_tie_btn.setCheckable(True)
        self._well_tie_btn.setIcon(self._get_ui_icon("share.svg"))
        self._well_tie_btn.toggled.connect(self._on_well_tie_toggled)
        bar.addSeparator()
        bar.addWidget(self._well_tie_btn)

        # ----- Row 2: 视图 | 属性 | 切片 -----
        # ----- Row 2: 视图渲染设定 -----
        bar2 = self._toolbar_row2
        bar2.addWidget(QLabel(" 3D模式:"))
        bar2.addWidget(self._3d_mode_combo)
        bar2.addWidget(self._opacity_combo)
        bar2.addWidget(self._hillshade_btn)
        bar2.addWidget(QLabel(" 剖面:"))
        bar2.addWidget(self._slice_type_combo)
        bar2.addWidget(QLabel(" 显示:"))
        bar2.addWidget(self._mode_combo)
        bar2.addWidget(QLabel(" 色标:"))
        bar2.addWidget(self._cmap_combo)
        bar2.addSeparator()
        bar2.addWidget(QLabel(" 雕刻:"))
        bar2.addWidget(self._sculpt_horizon_combo)
        bar2.addWidget(self._sculpt_mode_combo)
        bar2.addSeparator()
        bar2.addWidget(QLabel(" 裁剪:"))
        bar2.addWidget(self._clip_spin)
        bar2.addSeparator()
        bar2.addWidget(self._iso_checkbox)
        bar2.addWidget(self._iso_spin)

        # ----- Row 3: 叠加、特征属性与切片滑动条 -----
        bar3 = self._toolbar_row3
        bar3.addWidget(QLabel(" 属性:"))
        bar3.addWidget(self._attr_combo)
        bar3.addWidget(self._rgb_r_label)
        bar3.addWidget(self._rgb_r_combo)
        bar3.addWidget(self._rgb_g_label)
        bar3.addWidget(self._rgb_g_combo)
        bar3.addWidget(self._rgb_b_label)
        bar3.addWidget(self._rgb_b_combo)
        bar3.addWidget(crossplot_btn)
        bar3.addSeparator()
        bar3.addWidget(QLabel(" 叠加:"))
        bar3.addWidget(self._overlay_btn)
        bar3.addWidget(self._overlay_cmap_combo)
        bar3.addWidget(QLabel(" 不透明度:"))
        bar3.addWidget(self._overlay_opacity_slider)
        bar3.addSeparator()
        bar3.addWidget(QLabel(" IL:"))
        bar3.addWidget(self._tb_il_label)
        bar3.addWidget(self._tb_il_slider)
        bar3.addWidget(QLabel(" XL:"))
        bar3.addWidget(self._tb_xl_label)
        bar3.addWidget(self._tb_xl_slider)
        bar3.addWidget(QLabel(" T:"))
        bar3.addWidget(self._tb_t_label)
        bar3.addWidget(self._tb_t_slider)

        # Container holding three rows
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.addWidget(self._toolbar_row1)
        container_layout.addWidget(self._toolbar_row2)
        container_layout.addWidget(self._toolbar_row3)
        return container

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
        self._pending_slice[slice_type] = position
        self._slice_timer.start()  # Resets timer on each drag move
        # Sync toolbar slider from 3D slider
        self._sync_toolbar_slider(slice_type, position)

        # Sync slice type combo box index
        combo_map = {
            "inline": 0,
            "crossline": 1,
            "time": 2,
        }
        idx = combo_map.get(slice_type)
        if idx is not None:
            self._slice_type_combo.blockSignals(True)
            self._slice_type_combo.setCurrentIndex(idx)
            self._slice_type_combo.blockSignals(False)

    def _sync_toolbar_slider(self, slice_type: str, position: int):
        """Update the toolbar slider when position changes from 3D sliders."""
        slider_map = {
            "inline": self._tb_il_slider,
            "crossline": self._tb_xl_slider,
            "time": self._tb_t_slider,
        }
        slider = slider_map.get(slice_type)
        if slider and slider.isEnabled():
            slider.blockSignals(True)
            slider.setValue(position)
            slider.blockSignals(False)
            self._update_tb_slider_label(slice_type, position)

    def _on_tb_slider_changed(self, slice_type: str, value: int):
        """Toolbar slider changed: update label + debounce 3D scene + 2D profile."""
        self._update_tb_slider_label(slice_type, value)
        # Update 3D position state (cheap) without rebuilding slice planes yet.
        # The slice_changed signal triggers _on_slice_changed which debounces
        # both the 2D profile update and the 3D scene rebuild.
        self._renderer_3d.set_position_external(slice_type, value)

    @Slot()
    def _toggle_coord_mode(self):
        """Toggle between Grid coordinates (IL/XL) and Geographic coordinates (Easting/Northing in meters)."""
        if hasattr(self, "btn_coord") and self.btn_coord.isChecked():
            self._coord_mode = "geo"
            self.btn_coord.setText(" 🌐 地理(X/Y)")
        else:
            self._coord_mode = "grid"
            if hasattr(self, "btn_coord"):
                self.btn_coord.setText(" 📍 网格(IL/XL)")
        # Refresh current labels
        if hasattr(self, "_renderer_3d"):
            self._update_tb_slider_label("inline", self._renderer_3d._il_pos)
            self._update_tb_slider_label("crossline", self._renderer_3d._xl_pos)

    def _preview_to_survey_coords(
        self, slice_type: str, position: int
    ) -> tuple[float, float, float]:
        """Map preview-voxel slider index → full-grid IL / XL / time_ms.

        Toolbar sliders and Renderer3D use **downsampled** indices; 2D profiles
        and survey labels must use ``position * ds_factor`` (same as
        ``_apply_pending_slice``).
        """
        m = self._meta
        df = getattr(self, "_ds_factor", (1, 1, 1)) or (1, 1, 1)
        fi, fx, ft = int(df[0]), int(df[1]), int(df[2])
        if m is None:
            return float(position), float(position), float(position)
        il_pos = self._renderer_3d._il_pos if hasattr(self, "_renderer_3d") else 0
        xl_pos = self._renderer_3d._xl_pos if hasattr(self, "_renderer_3d") else 0
        if slice_type == "inline":
            il = m.iline_start + position * fi * m.iline_step
            xl = m.xline_start + xl_pos * fx * m.xline_step
            t_ms = m.t0_ms + (
                (self._renderer_3d._t_pos if hasattr(self, "_renderer_3d") else 0)
                * ft
                * m.dt_ms
            )
            return float(il), float(xl), float(t_ms)
        if slice_type == "crossline":
            il = m.iline_start + il_pos * fi * m.iline_step
            xl = m.xline_start + position * fx * m.xline_step
            t_ms = m.t0_ms + (
                (self._renderer_3d._t_pos if hasattr(self, "_renderer_3d") else 0)
                * ft
                * m.dt_ms
            )
            return float(il), float(xl), float(t_ms)
        # time: position is preview sample index
        il = m.iline_start + il_pos * fi * m.iline_step
        xl = m.xline_start + xl_pos * fx * m.xline_step
        t_ms = m.t0_ms + position * ft * m.dt_ms
        return float(il), float(xl), float(t_ms)

    def _update_tb_slider_label(self, slice_type: str, position: int):
        """Update the toolbar slider value label with actual survey coordinate."""
        m = self._meta
        if m is None:
            return
        il, xl, t_ms = self._preview_to_survey_coords(slice_type, position)
        if getattr(self, "_coord_mode", "grid") == "geo":
            if slice_type == "inline":
                x_geo, _ = m.il_xl_to_xy(il, xl)
                self._tb_il_label.setText(f"X {x_geo:.0f}m")
            elif slice_type == "crossline":
                _, y_geo = m.il_xl_to_xy(il, xl)
                self._tb_xl_label.setText(f"Y {y_geo:.0f}m")
            else:
                self._tb_t_label.setText(f"T {t_ms:.0f}")
        else:
            if slice_type == "inline":
                self._tb_il_label.setText(f"IL {il:.0f}")
            elif slice_type == "crossline":
                self._tb_xl_label.setText(f"XL {xl:.0f}")
            else:
                self._tb_t_label.setText(f"T {t_ms:.0f}")

    def _on_slice_step(self, slice_type: str, delta: int):
        """Handle Shift+wheel slice browsing: increment/decrement slice position."""
        if self._meta is None:
            return
        pos_map = {
            "inline": self._renderer_3d._il_pos,
            "crossline": self._renderer_3d._xl_pos,
            "time": self._renderer_3d._t_pos,
        }
        vol = self._renderer_3d._volume_data_cpu
        if vol is None:
            return
        max_map = {
            "inline": vol.shape[0],
            "crossline": vol.shape[1],
            "time": vol.shape[2],
        }
        current = pos_map[slice_type]
        new_pos = max(0, min(current + delta, max_map[slice_type] - 1))
        if new_pos == current:
            return
        self._renderer_3d.set_position_external(slice_type, new_pos)

    def _setup_toolbar_sliders(self):
        """Enable and configure toolbar sliders after data is loaded."""
        vol = self._renderer_3d._volume_data_cpu
        if vol is None:
            return
        ni, nx, nt = vol.shape
        for s, n in [(self._tb_il_slider, ni), (self._tb_xl_slider, nx), (self._tb_t_slider, nt)]:
            s.setRange(0, n - 1)
            s.setEnabled(True)
        self._tb_il_slider.setValue(self._renderer_3d._il_pos)
        self._tb_xl_slider.setValue(self._renderer_3d._xl_pos)
        self._tb_t_slider.setValue(self._renderer_3d._t_pos)
        self._update_tb_slider_label("inline", self._renderer_3d._il_pos)
        self._update_tb_slider_label("crossline", self._renderer_3d._xl_pos)
        self._update_tb_slider_label("time", self._renderer_3d._t_pos)
        self._refresh_isosurface_controls()

    @Slot()
    def _apply_pending_slice(self):
        if not self._pending_slice:
            return
        pending = dict(self._pending_slice)
        self._pending_slice.clear()

        # Rebuild only the 3D planes whose axis changed
        try:
            self._renderer_3d._update_slice_planes_for(set(pending))
        except (RuntimeError, AttributeError):
            return

        # Demo mode: slice from cached volume data directly
        if self._loader is None:
            vol = self._renderer_3d._volume_data_cpu
            if vol is None:
                return
            for slice_type, position in pending.items():
                if slice_type == "inline":
                    raw = vol[position, :, :]
                elif slice_type == "crossline":
                    raw = vol[:, position, :]
                else:
                    raw = vol[:, :, position]
                self._update_profile_panel(slice_type, position, raw.T)
            return

        if self._meta is None:
            return

        # Plane widget gives downsampled voxel indices.
        # Convert to actual inline/crossline numbers for segyio.
        m = self._meta
        df = self._ds_factor
        for slice_type, position in pending.items():
            if slice_type == "inline":
                actual_pos = m.iline_start + position * df[0] * m.iline_step
            elif slice_type == "crossline":
                actual_pos = m.xline_start + position * df[1] * m.xline_step
            else:
                actual_pos = position * df[2]

            cache_key = (slice_type, actual_pos)
            cached = self._cache.get(cache_key)
            if cached is not None:
                # Record the user's current position so a late in-flight
                # result for an older position can't overwrite the panel.
                self._latest_slice_request[slice_type] = actual_pos
                self._update_profile_panel(slice_type, actual_pos, cached.T)
            else:
                # Async: worker reads from disk; panel updates on slice_ready
                self._ensure_slice_worker()
                self._latest_slice_request[slice_type] = actual_pos
                self._slice_worker.request(
                    slice_type, actual_pos, self._segy_generation
                )

    @Slot(str, int, object, int)
    def _on_slice_ready(self, slice_type: str, actual_pos: int, data, generation: int):
        if generation != self._segy_generation:
            return
        self._cache.put((slice_type, actual_pos), data)
        # Latest-wins applies to the queue only; an in-flight read for a
        # superseded same-generation position must not update the panel.
        latest = self._latest_slice_request.get(slice_type)
        if latest is None or latest == actual_pos:
            self._update_profile_panel(slice_type, actual_pos, data.T)

    @Slot(str, int, int)
    def _on_slice_read_error(self, slice_type: str, actual_pos: int, generation: int):
        if generation != self._segy_generation:
            return
        self._slice_label.setText(f"Read error: {slice_type} {actual_pos}")

    @Slot(str, int, object, int)
    def _on_prefetch_ready(self, slice_type: str, actual_pos: int, data, generation: int):
        if generation != self._segy_generation:
            return
        self._cache.put((slice_type, actual_pos), data)

    def _update_profile_panel(self, slice_type: str, position: int, slice_2d: np.ndarray):
        """Route slice data to the correct profile panel and cache raw data for export."""
        info = self._build_slice_info(slice_type, position, slice_2d.shape)
        self._slice_data[slice_type] = slice_2d.copy()

        display = self._apply_attr(slice_2d)

        if slice_type == "inline":
            self._profile_il.update_profile(display, slice_info=info)
        elif slice_type == "crossline":
            self._profile_xl.update_profile(display, slice_info=info)
        else:
            self._profile_t.update_profile(display, slice_info=info)

        self._slice_label.setText(f"{slice_type.capitalize()} {position}")

    def _apply_attr(self, data: np.ndarray) -> np.ndarray:
        """Apply the current attribute mode to slice data."""
        from . import attribute_pipeline as _ap
        idx = self._attr_combo.currentIndex()
        si = self._meta.sample_interval if self._meta else 1.0
        return _ap.apply(idx, data, sample_interval_s=si / 1000.0)

    def _get_attr_fn(self, combo_idx: int):
        """Return the attribute function for a given RGB channel combo index."""
        from . import attributes as _attr
        _FN = [
            _attr.compute_envelope,        # 0
            _attr.compute_instantaneous_frequency,  # 1
            _attr.compute_rms_amplitude,   # 2
            _attr.compute_sweetness,       # 3
            _attr.compute_relative_impedance,  # 4
        ]
        return _FN[combo_idx] if combo_idx < len(_FN) else _attr.compute_envelope

    def _apply_rgb_fusion(self, data: np.ndarray) -> np.ndarray | None:
        """Compute RGB fusion from three attribute channels. Returns (H,W,4) RGBA or None."""
        from . import attributes as _attr
        si = self._meta.sample_interval if self._meta else 1.0
        si_s = si / 1000.0

        def _compute(ch_combo_idx: int) -> np.ndarray:
            fn = self._get_attr_fn(ch_combo_idx)
            kwargs = {}
            if fn in (_attr.compute_instantaneous_frequency, _attr.compute_sweetness):
                kwargs["sample_interval"] = si_s
            return fn(data, axis=0, **kwargs)

        r_attr = _compute(self._rgb_r_combo.currentIndex())
        g_attr = _compute(self._rgb_g_combo.currentIndex())
        b_attr = _compute(self._rgb_b_combo.currentIndex())

        rgb = _attr.fuse_rgb(r_attr, g_attr, b_attr)
        alpha = np.full((*rgb.shape[:2], 1), 255, dtype=np.uint8)
        return np.concatenate([rgb, alpha], axis=-1)

    def _export_slice(self, slice_type: str):
        """Export the current slice data or rendered image."""
        data = self._slice_data.get(slice_type)
        if data is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, f"导出 {slice_type.capitalize()} 剖面",
            f"{slice_type}_slice",
            "NumPy (*.npy);;CSV (*.csv);;PNG 图像 (*.png)"
        )
        if not path:
            return
        try:
            if path.endswith(".png"):
                widget_map = {
                    "inline": self._profile_il,
                    "crossline": self._profile_xl,
                    "time": self._profile_t,
                    "arbitrary": self._profile_arb,
                }
                widget = widget_map.get(slice_type)
                if widget:
                    pixmap = widget.grab()
                    pixmap.save(path, "PNG")
            elif path.endswith(".npy"):
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
        self._synth_worker = SyntheticWorker(self)
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
        import os
        name = os.path.basename(path).rsplit(".", 1)[0]
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

        # Cycle through colors for multiple horizons
        colors = [
            (1.0, 0.9, 0.2, 0.6),   # gold
            (0.2, 0.9, 0.5, 0.6),    # green
            (0.3, 0.6, 1.0, 0.6),    # blue
            (0.9, 0.4, 0.4, 0.6),    # red
            (0.8, 0.5, 1.0, 0.6),    # purple
        ]
        idx = len(self._horizon_grids) % len(colors)
        self._horizon_grids[name] = filled
        self._renderer_3d.add_horizon(filled, name=name, color=colors[idx])
        self._sculpt_horizon_combo.addItem(name)
        self._readout_label.setText(f"已加载层位: {name} ({len(self._horizon_grids)} 个)")

    def _remove_horizon(self, name: str):
        self._horizon_grids.pop(name, None)
        self._renderer_3d.remove_horizon(name)
        idx = self._sculpt_horizon_combo.findText(name)
        if idx >= 0:
            self._sculpt_horizon_combo.removeItem(idx)
        self._readout_label.setText(f"已移除层位: {name}")

    def _show_horizon_list(self):
        dialog = HorizonManagerDialog(
            list(self._horizon_grids.keys()),
            remove_callback=self._remove_horizon,
            parent=self,
        )
        dialog.exec()

    def _on_mode_changed(self, index: int):
        mode = "vd" if index == 0 else "wiggle"
        for pw in (self._profile_il, self._profile_xl, self._profile_t, self._profile_arb):
            pw.set_display_mode(mode)

    @Slot(int)
    def _on_slice_type_changed(self, index: int):
        if self._meta is None:
            return

        slice_types = ["inline", "crossline", "time"]
        if not (0 <= index < len(slice_types)):
            return
        slice_type = slice_types[index]

        pos_map = {
            "inline": self._renderer_3d._il_pos,
            "crossline": self._renderer_3d._xl_pos,
            "time": self._renderer_3d._t_pos,
        }
        position = pos_map.get(slice_type)
        if position is None:
            return

        widget_map = {
            "inline": self._profile_il,
            "crossline": self._profile_xl,
            "time": self._profile_t,
        }
        self._profile_widget = widget_map[slice_type]

        # Trigger an immediate slice read / render
        self._on_slice_changed(slice_type, position)

    def _on_sculpt_changed(self, _=None):
        horizon_name = self._sculpt_horizon_combo.currentText()
        if horizon_name == "无" or horizon_name not in self._horizon_grids:
            self._renderer_3d.set_sculpting_surface(None)
        else:
            mode_text = self._sculpt_mode_combo.currentText()
            mode = "above" if mode_text == "保留上部" else "below"
            self._renderer_3d.set_sculpting_surface(self._horizon_grids[horizon_name], mode)

    def _on_clip_changed(self, value: float):
        for pw in (self._profile_il, self._profile_xl, self._profile_t, self._profile_arb):
            pw._vd.set_clip_percentile(value)
        # Keep 3D orthogonal planes on the same colour scale as 2D profiles
        if hasattr(self._renderer_3d, "set_slice_clip_percentile"):
            self._renderer_3d.set_slice_clip_percentile(value)

    def _on_opacity_changed(self, index: int):
        modes = ["sharp", "linear", "sigmoid", "threshold"]
        if 0 <= index < len(modes):
            self._renderer_3d.set_opacity_mode(modes[index])

    def _refresh_isosurface_controls(self):
        from .isosurface import get_isosurface_extractor

        vol = self._renderer_3d.volume_data()
        ok = vol is not None and get_isosurface_extractor() is not None
        self._iso_checkbox.setEnabled(ok)
        self._iso_spin.setEnabled(ok)
        if not ok:
            self._iso_checkbox.setToolTip("等值面不可用（未注入提取器或未加载数据）")
            if self._iso_checkbox.isChecked():
                self._iso_checkbox.setChecked(False)
            return
        self._iso_checkbox.setToolTip("")
        vmin = float(np.nanmin(vol))
        vmax = float(np.nanmax(vol))
        self._iso_spin.blockSignals(True)
        self._iso_spin.setRange(vmin, vmax)
        self._iso_spin.setSingleStep((vmax - vmin) / 100.0 if vmax > vmin else 1.0)
        self._iso_spin.setValue((vmin + vmax) / 2.0)
        self._iso_spin.blockSignals(False)
        # Volume swapped while the isosurface was active: the mesh was cleared
        # by load_volume; schedule a rebuild with the new volume + threshold
        # instead of leaving a checked-but-empty state.
        if self._iso_checkbox.isChecked():
            self._iso_timer.start()

    def _on_isosurface_toggled(self, checked: bool):
        if checked:
            self._iso_timer.start()
        else:
            self._iso_timer.stop()
            self._renderer_3d.clear_isosurface()

    def _on_isosurface_threshold_changed(self, _value: float):
        if self._iso_checkbox.isChecked():
            self._iso_timer.start()

    def _rebuild_isosurface(self):
        from .isosurface import get_isosurface_extractor

        extractor = get_isosurface_extractor()
        vol = self._renderer_3d.volume_data()
        if extractor is None or vol is None or not self._iso_checkbox.isChecked():
            return
        try:
            verts, faces = extractor(vol, float(self._iso_spin.value()))
        except Exception:
            self._log.warning("isosurface extraction failed", exc_info=True)
            self._renderer_3d.clear_isosurface()
            self._iso_checkbox.setChecked(False)
            return
        self._renderer_3d.set_isosurface(verts, faces)

    def _on_hillshade_toggled(self, checked: bool):
        self._renderer_3d.set_hillshading(checked)

    def _on_attr_changed(self, index: int):
        # Toggle RGB channel selectors visibility
        from . import attribute_pipeline as _ap
        is_rgb = (index == _ap.rgb_index())
        for w in (self._rgb_r_combo, self._rgb_g_combo, self._rgb_b_combo,
                  self._rgb_r_label, self._rgb_g_label, self._rgb_b_label):
            w.setVisible(is_rgb)
        self._apply_current_attr()

    def _on_rgb_channels_changed(self):
        from . import attribute_pipeline as _ap
        if self._attr_combo.currentIndex() == _ap.rgb_index():
            self._apply_current_attr()

    def _on_crossplot(self):
        """Open an attribute crossplot dialog for the current slice."""
        raw = self._slice_data.get("inline")
        if raw is None:
            raw = self._slice_data.get("crossline")
        if raw is None:
            raw = self._slice_data.get("time")
        if raw is None:
            return
        si = self._meta.sample_interval if self._meta else 1.0
        dlg = CrossplotDialog(raw, si / 1000.0, parent=self)
        dlg.exec()

    def _apply_current_attr(self):
        """Re-render all cached slice data with the current attribute mode."""
        from . import attribute_pipeline as _ap
        attr_mode = self._attr_combo.currentIndex()
        rgb_idx = _ap.rgb_index()
        for st in ("inline", "crossline", "time"):
            raw = self._slice_data.get(st)
            if raw is None:
                continue
            info = self._build_slice_info(st, 0, raw.shape)
            # Recover position from info stored in the profile widget
            pw_map = {
                "inline": self._profile_il,
                "crossline": self._profile_xl,
                "time": self._profile_t,
            }
            pw = pw_map[st]
            existing_info = pw._vd.slice_info() if pw._vd else None
            if existing_info:
                info = existing_info

            if attr_mode == rgb_idx:  # RGB fusion
                rgba = self._apply_rgb_fusion(raw)
                if rgba is not None:
                    pw._vd.render_rgba(rgba, slice_info=info)
                continue

            display = raw
            if attr_mode != 0:
                display = self._apply_attr(raw)

            pw.update_profile(display, slice_info=info)

    # --- Cross-hair cursor linking ---

    def _current_il_xl_t(self) -> tuple[int, int, int]:
        """Get current slider positions as (il_index, xl_index, t_index)."""
        r = self._renderer_3d
        return r._il_pos, r._xl_pos, r._t_pos

    def _on_cursor_3d(self, h_val: float, v_val: float, slice_type: str):
        """Unified cursor handler: convert (h, v, slice_type) to 3D coords and link panels."""
        il_pos, xl_pos, t_pos = self._current_il_xl_t()
        m = self._meta

        # Convert slider positions to actual coordinate values
        il_val = (m.iline_start + il_pos * m.iline_step) if m else float(il_pos)
        xl_val = (m.xline_start + xl_pos * m.xline_step) if m else float(xl_pos)
        t_val = (m.t0_ms + t_pos * m.dt_ms) if m else float(t_pos)

        if slice_type == "inline":
            # h=xline, v=time, current il position
            self._set_crosshairs(il_val, h_val, v_val)
        elif slice_type == "crossline":
            # h=inline, v=time, current xl position
            self._set_crosshairs(h_val, xl_val, v_val)
        elif slice_type == "time":
            # h=inline, v=xline, current t position
            self._set_crosshairs(h_val, v_val, t_val)

    def _set_crosshairs(self, il_val: float, xl_val: float, t_val: float):
        """Set crosshair positions on all three orthogonal profile panels."""
        # IL panel: h=xline, v=time
        self._profile_xl._vd.set_crosshair(il_val, t_val)
        self._profile_t._vd.set_crosshair(il_val, xl_val)
        # XL panel: h=inline, v=time
        self._profile_il._vd.set_crosshair(xl_val, t_val)
        # T panel: h=inline, v=xline (already set above for IL→T and XL→T cases)
        # Update 3D cursor sphere
        self._renderer_3d.set_cursor_position(il_val, xl_val, t_val)

    # --- 3D click-to-jump ---

    def _on_jump(self, il_idx: float, xl_idx: float, t_idx: float):
        """Handle 3D click-to-jump: navigate all panels to the clicked position."""
        vol = self._renderer_3d._volume_data_cpu
        if vol is None:
            return
        ni, nx, nt = vol.shape
        il_pos = max(0, min(int(round(il_idx)), ni - 1))
        xl_pos = max(0, min(int(round(xl_idx)), nx - 1))
        t_pos = max(0, min(int(round(t_idx)), nt - 1))

        # Update all three slices
        self._renderer_3d.set_position_external("inline", il_pos)
        self._renderer_3d.set_position_external("crossline", xl_pos)
        self._renderer_3d.set_position_external("time", t_pos)

        # Show crosshairs at the jump position
        m = self._meta
        il_val = (m.iline_start + il_pos * m.iline_step) if m else float(il_pos)
        xl_val = (m.xline_start + xl_pos * m.xline_step) if m else float(xl_pos)
        t_val = (m.t0_ms + t_pos * m.dt_ms) if m else float(t_pos)
        self._set_crosshairs(il_val, xl_val, t_val)

    # --- Amplitude readout ---

    def _on_amplitude_readout(self, text: str):
        self._readout_label.setText(text)

    # --- Horizon picking ---

    def _on_pick_toggled(self, checked: bool):
        for pw in (self._profile_il, self._profile_xl, self._profile_t):
            pw._vd.enable_picking(checked)

    def _on_horizon_picked(self, h_val: float, v_val: float, _extra: float):
        """A horizon point was picked on one of the profile panels."""
        sender = self.sender()
        if sender is None:
            return
        info = sender.slice_info()
        if info is None:
            return

        m = self._meta
        st = info.slice_type
        pos = info.position

        il_val, xl_val, t_val = 0.0, 0.0, 0.0
        if st == "inline":
            il_val = float(m.iline_start + pos * m.iline_step) if m else float(pos)
            xl_val, t_val = h_val, v_val
        elif st == "crossline":
            xl_val = float(m.xline_start + pos * m.xline_step) if m else float(pos)
            il_val, t_val = h_val, v_val
        else:  # time
            t_val = float(m.t0_ms + pos * m.dt_ms) if m else float(pos)
            il_val, xl_val = h_val, v_val

        self._picked_points.append((il_val, xl_val, t_val))

        # Show on all 2D panels
        self._profile_il._vd.add_picked_point(xl_val, t_val)
        self._profile_xl._vd.add_picked_point(il_val, t_val)
        self._profile_t._vd.add_picked_point(il_val, xl_val)

        # Show in 3D
        self._renderer_3d.set_horizon_picks(self._picked_points)

        n = len(self._picked_points)
        self._readout_label.setText(f"已拾取 {n} 个点")

    def _on_clear_picks(self):
        self._picked_points.clear()
        for pw in (self._profile_il, self._profile_xl, self._profile_t):
            pw._vd.clear_picked_points()
        self._renderer_3d.set_horizon_picks([])
        self._readout_label.setText("")

    def _on_export_picks(self):
        if not self._picked_points:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出层位拾取点", "horizon_picks.csv",
            "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, "w") as f:
                f.write("inline,crossline,time_ms\n")
                for il, xl, t in self._picked_points:
                    f.write(f"{il:.1f},{xl:.1f},{t:.1f}\n")
            self._log.info("Exported %d picks to %s", len(self._picked_points), path)
        except Exception as exc:
            self._log.error("Export picks failed: %s", exc)

    # --- Annotation ---

    def _on_annotation_toggled(self, checked: bool):
        for pw in (self._profile_il, self._profile_xl, self._profile_t):
            pw._vd.enable_annotation_mode(checked)

    def current_seismic_trace(self) -> np.ndarray | None:
        """Return the vertical seismic trace at the current IL/XL intersection.

        Preference order:
        1. In-memory volume (demo / downsampled SEGY)
        2. ``SeismicLoader.read_trace`` when a SEGY file is open
        3. Column from the cached inline slice
        """
        vol = getattr(self._renderer_3d, "_volume_data_cpu", None)
        if vol is not None and getattr(vol, "ndim", 0) == 3:
            il = int(getattr(self._renderer_3d, "_il_pos", vol.shape[0] // 2))
            xl = int(getattr(self._renderer_3d, "_xl_pos", vol.shape[1] // 2))
            il = max(0, min(il, vol.shape[0] - 1))
            xl = max(0, min(xl, vol.shape[1] - 1))
            return np.asarray(vol[il, xl, :], dtype=np.float64)

        if self._loader is not None and self._meta is not None:
            m = self._meta
            df = self._ds_factor
            il_idx = int(getattr(self._renderer_3d, "_il_pos", 0))
            xl_idx = int(getattr(self._renderer_3d, "_xl_pos", 0))
            iline = m.iline_start + il_idx * df[0] * m.iline_step
            xline = m.xline_start + xl_idx * df[1] * m.xline_step
            try:
                return np.asarray(self._loader.read_trace(iline, xline), dtype=np.float64)
            except Exception as exc:
                self._log.warning("current_seismic_trace read_trace failed: %s", exc)

        il_data = self._slice_data.get("inline")
        if il_data is not None and getattr(il_data, "ndim", 0) == 2:
            xl = int(getattr(self._renderer_3d, "_xl_pos", il_data.shape[1] // 2))
            xl = max(0, min(xl, il_data.shape[1] - 1))
            return np.asarray(il_data[:, xl], dtype=np.float64)
        return None

    def _seed_demo_well_logs_if_needed(self, panel) -> None:
        """Provide synthetic sonic/density so Auto-Tie works without external LAS."""
        if getattr(panel, "_calibration", None) is not None:
            return
        m = self._meta
        n = int(m.n_samples) if m is not None else 100
        n = max(n, 50)
        depths = np.linspace(0.0, float(n) * 2.0, n)
        # Gentle structure + one impedance contrast for reflectivity spikes.
        phase = np.linspace(0.0, 6.0, n)
        sonic = 200.0 + 20.0 * np.sin(phase)
        density = 2.5 + 0.08 * np.sin(phase * 0.7)
        lo, hi = n // 3, n // 2
        sonic[lo:hi] -= 40.0
        density[lo:hi] -= 0.2
        try:
            from geoviz_well_tie.calibration import WellTieCalibration
        except ImportError:
            self._log.warning("geoviz_well_tie not available; cannot seed well logs")
            return
        panel.set_calibration(WellTieCalibration.from_sonic(depths, sonic))
        panel.set_well_logs(depths, sonic, density)

    def _on_auto_tie_requested(self) -> None:
        """Provide the current seismic trace to WellTiePanel.auto_tie()."""
        panel = self._well_tie_panel
        if panel is None:
            return
        trace = self.current_seismic_trace()
        if trace is None or len(trace) == 0:
            self._log.warning("Auto-Tie: no seismic trace at current IL/XL")
            if hasattr(panel, "_cc_label"):
                panel._cc_label.setText("CC: -- (无地震道)")
            return
        panel.auto_tie(trace)
        self._log.info(
            "Auto-Tie complete: shift=%s cc=%s",
            getattr(panel, "_shift_samples", None),
            getattr(panel, "_correlation_coeff", None),
        )

    def _on_synthetic_changed(self, twt, values) -> None:
        """Draw synthetic seismogram overlay on IL/XL profile panels."""
        if twt is None or values is None:
            return
        twt_arr = np.asarray(twt, dtype=np.float64)
        val_arr = np.asarray(values, dtype=np.float32)
        m = self._meta
        xl_pos = int(getattr(self._renderer_3d, "_xl_pos", 0))
        il_pos = int(getattr(self._renderer_3d, "_il_pos", 0))
        if m is not None:
            xl_coord = float(m.xline_start + xl_pos * m.xline_step)
            il_coord = float(m.iline_start + il_pos * m.iline_step)
        else:
            xl_coord = float(xl_pos)
            il_coord = float(il_pos)

        # Inline section: horizontal axis is crossline; crossline section: inline.
        self._profile_il._vd.set_synthetic_overlay(
            h_position=xl_coord,
            twt=twt_arr,
            values=val_arr,
            label="Synth",
            color="#e53e3e",
        )
        self._profile_xl._vd.set_synthetic_overlay(
            h_position=il_coord,
            twt=twt_arr,
            values=val_arr,
            label="Synth",
            color="#e53e3e",
        )

    def _on_well_tie_toggled(self, checked: bool):
        """Toggle the WellTiePanel visibility and wire Auto-Tie / synthetic signals."""
        from .well_tie_panel import WellTiePanel

        if checked:
            if self._well_tie_panel is None:
                self._well_tie_panel = WellTiePanel()
                self._well_tie_panel.setMaximumWidth(320)
                # Host supplies the live seismic trace; panel runs cross-correlation.
                self._well_tie_panel.auto_tie_requested.connect(self._on_auto_tie_requested)
                self._well_tie_panel.synthetic_changed.connect(self._on_synthetic_changed)
                self._seed_demo_well_logs_if_needed(self._well_tie_panel)
                # Insert into the main layout alongside the splitter
                h_layout = self.layout().itemAt(2)
                if h_layout and isinstance(h_layout, QHBoxLayout):
                    h_layout.insertWidget(0, self._well_tie_panel)
            else:
                # Re-seed only if still empty (e.g. first open before volume load).
                self._seed_demo_well_logs_if_needed(self._well_tie_panel)
            self._well_tie_panel.show()
        else:
            if self._well_tie_panel is not None:
                self._well_tie_panel.hide()

    def _on_annotation_added(self, h_val: float, v_val: float, text: str):
        """An annotation was placed on a profile panel; sync to 3D."""
        self._sync_annotations_to_3d()

    def _sync_annotations_to_3d(self):
        """Collect annotations from all profile panels and push to 3D renderer."""
        all_3d: list[tuple[float, float, float, str]] = []

        m = self._meta
        if m is None:
            self._renderer_3d.set_annotations(all_3d)
            return

        for pw in (self._profile_il, self._profile_xl, self._profile_t):
            for ann in pw._vd.annotations():
                st = ann.slice_type
                pos = ann.slice_position

                if st == "inline":
                    il = float(m.iline_start + pos * m.iline_step)
                    xl, t = ann.h_value, ann.v_value
                elif st == "crossline":
                    xl = float(m.xline_start + pos * m.xline_step)
                    il, t = ann.h_value, ann.v_value
                else:
                    t = float(m.t0_ms + pos * m.dt_ms)
                    il, xl = ann.h_value, ann.v_value

                all_3d.append((il, xl, t, ann.text))

        self._renderer_3d.set_annotations(all_3d)
