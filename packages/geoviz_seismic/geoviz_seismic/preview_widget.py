from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from PySide6.QtCore import QCoreApplication, Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .loader import SeismicLoader
from .models import SeismicVolumeMeta, SliceInfo
from .profile_widget import ProfileWidget
from .workers import SliceReadWorker, retain_background_worker


@dataclass(frozen=True)
class SeismicSlice:
    data: np.ndarray
    info: SliceInfo


@dataclass(frozen=True)
class SeismicAxisSpec:
    """Discrete positions available along one slice mode (inline / crossline / time)."""

    start: int
    step: int
    count: int

    def clamp_index(self, index: int) -> int:
        if self.count <= 0:
            return 0
        return max(0, min(self.count - 1, int(index)))

    def position_at(self, index: int) -> int:
        return int(self.start + self.clamp_index(index) * max(self.step, 1))

    def index_of(self, position: int) -> int:
        if self.count <= 0:
            return 0
        step = max(self.step, 1)
        return self.clamp_index(int(round((int(position) - self.start) / step)))


@dataclass(frozen=True)
class SeismicPreviewPayload:
    slices: dict[str, SeismicSlice]
    initial_mode: str = "inline"
    source_path: str = ""
    max_slice_axis: int = 512
    axes: dict[str, SeismicAxisSpec] = field(default_factory=dict)
    meta: SeismicVolumeMeta | None = None


_MODE_LABELS = {
    "inline": "Inline",
    "crossline": "Crossline",
    "time": "Time sample",
}


def downsample_2d(data: np.ndarray, limit: int) -> np.ndarray:
    row_step = max(1, math.ceil(data.shape[0] / limit))
    col_step = max(1, math.ceil(data.shape[1] / limit))
    return np.ascontiguousarray(data[::row_step, ::col_step], dtype=np.float32)


def _sample_steps(data: np.ndarray, limit: int) -> tuple[int, int]:
    return (
        max(1, math.ceil(data.shape[0] / limit)),
        max(1, math.ceil(data.shape[1] / limit)),
    )


def _slice_info(
    mode: str,
    position: int,
    display_data: np.ndarray,
    meta: SeismicVolumeMeta,
    row_step: int,
    col_step: int,
) -> SliceInfo:
    if mode == "inline":
        horizontal = meta.xline_start + np.arange(display_data.shape[1]) * meta.xline_step
        vertical = meta.t0_ms + np.arange(display_data.shape[0]) * meta.dt_ms
        horizontal_label, vertical_label = "Crossline", "Time (ms)"
    elif mode == "crossline":
        horizontal = meta.iline_start + np.arange(display_data.shape[1]) * meta.iline_step
        vertical = meta.t0_ms + np.arange(display_data.shape[0]) * meta.dt_ms
        horizontal_label, vertical_label = "Inline", "Time (ms)"
    else:
        horizontal = meta.iline_start + np.arange(display_data.shape[1]) * meta.iline_step
        vertical = meta.xline_start + np.arange(display_data.shape[0]) * meta.xline_step
        horizontal_label, vertical_label = "Inline", "Crossline"

    return SliceInfo(
        slice_type=mode,
        position=position,
        axis_h_label=horizontal_label,
        axis_v_label=vertical_label,
        axis_h_values=horizontal[::col_step].astype(float).tolist(),
        axis_v_values=vertical[::row_step].astype(float).tolist(),
    )


def axis_specs_from_meta(meta: SeismicVolumeMeta) -> dict[str, SeismicAxisSpec]:
    return {
        "inline": SeismicAxisSpec(
            start=int(meta.iline_start),
            step=max(1, int(meta.iline_step)),
            count=max(1, int(meta.n_inlines)),
        ),
        "crossline": SeismicAxisSpec(
            start=int(meta.xline_start),
            step=max(1, int(meta.xline_step)),
            count=max(1, int(meta.n_crosslines)),
        ),
        "time": SeismicAxisSpec(
            start=0,
            step=1,
            count=max(1, int(meta.n_samples)),
        ),
    }


def _meta_from_axes(axes: dict[str, SeismicAxisSpec]) -> SeismicVolumeMeta | None:
    """Best-effort metadata reconstructed from axis specs (payloads without ``meta``).

    The time axis only encodes sample indices (t0=0, dt=1), so time-axis tick
    labels degrade to sample numbers when the real metadata was not carried.
    """
    inline = axes.get("inline")
    crossline = axes.get("crossline")
    time = axes.get("time")
    if inline is None or crossline is None or time is None:
        return None
    return SeismicVolumeMeta(
        filename="",
        n_inlines=inline.count,
        n_crosslines=crossline.count,
        n_samples=time.count,
        sample_interval=float(time.step),
        iline_start=inline.start,
        iline_step=inline.step,
        xline_start=crossline.start,
        xline_step=crossline.step,
        dt_ms=float(time.step),
        t0_ms=float(time.start),
    )


def _read_raw_slice(loader: SeismicLoader, mode: str, position: int) -> np.ndarray:
    """Return display-oriented array (rows=vertical, cols=horizontal)."""
    if mode == "inline":
        return loader.read_inline(int(position)).T
    if mode == "crossline":
        return loader.read_crossline(int(position)).T
    if mode == "time":
        return loader.read_timeslice(int(position)).T
    raise ValueError(f"unknown seismic slice mode: {mode}")


def load_preview_slice(
    path: str,
    mode: str,
    position: int,
    limit: int,
    *,
    meta: SeismicVolumeMeta | None = None,
) -> SeismicSlice:
    """Load a single downsampled slice for interactive preview scrubbing."""
    loader = SeismicLoader(path)
    try:
        volume_meta = meta or loader.inspect()
        display_data = _read_raw_slice(loader, mode, position)
        row_step, col_step = _sample_steps(display_data, limit)
        return SeismicSlice(
            data=downsample_2d(display_data, limit),
            info=_slice_info(
                mode,
                int(position),
                display_data,
                volume_meta,
                row_step,
                col_step,
            ),
        )
    finally:
        loader.close()



class SeismicPreviewWidget(QWidget):
    """A bounded 2-D seismic preview without any OpenGL dependencies.

    Supports mode switching (inline / crossline / time) and a position slider
    that re-reads a single SEGY slice on demand when ``source_path`` + ``axes``
    are present on the payload.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._slices: dict[str, SeismicSlice] = {}
        self._source_path: str = ""
        self._max_slice_axis: int = 512
        self._axes: dict[str, SeismicAxisSpec] = {}
        self._meta: SeismicVolumeMeta | None = None
        self._suppress_slider = False
        # Background slice reader: owns a long-lived SeismicLoader inside a
        # QThread so the UI thread never performs SEGY I/O.  ``_generation``
        # invalidates in-flight/queued results after the volume or clear().
        self._slice_worker: SliceReadWorker | None = None
        self._slice_worker_stopped = True
        self._generation = 0
        self._latest_requests: dict[str, int] = {}
        self._prefetch_cache: dict[tuple[str, int], SeismicSlice] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(8)

        self.mode_combo = QComboBox(self)
        self.mode_combo.addItem("Inline", "inline")
        self.mode_combo.addItem("Crossline", "crossline")
        self.mode_combo.addItem("Time", "time")
        controls.addWidget(self.mode_combo)

        self.position_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.position_slider.setMinimum(0)
        self.position_slider.setMaximum(0)
        self.position_slider.setEnabled(False)
        self.position_slider.setToolTip("拖动调整剖面位置")
        controls.addWidget(self.position_slider, 1)

        self.position_label = QLabel("—", self)
        self.position_label.setMinimumWidth(96)
        self.position_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        controls.addWidget(self.position_label)

        layout.addLayout(controls)

        self.profile = ProfileWidget(self)
        layout.addWidget(self.profile)

        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.setInterval(80)
        self._reload_timer.timeout.connect(self._reload_current_position)

        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.position_slider.valueChanged.connect(self._on_slider_changed)
        self.clear()

    def set_slices(self, payload: SeismicPreviewPayload) -> None:
        self._slices = dict(payload.slices)
        self._source_path = str(payload.source_path or "")
        self._max_slice_axis = max(1, int(payload.max_slice_axis or 512))
        self._axes = dict(payload.axes or {})
        self._meta = payload.meta or _meta_from_axes(self._axes)

        # Point the background reader at this volume; the bumped generation
        # discards queued/in-flight requests left over from a previous volume.
        self._generation += 1
        self._latest_requests = {}
        self._prefetch_cache = {}
        if self._source_path:
            self._ensure_slice_worker()
            self._slice_worker.set_volume(self._source_path, self._generation)

        initial_index = self.mode_combo.findData(payload.initial_mode)
        if initial_index < 0:
            initial_index = 0
        self._suppress_slider = True
        try:
            self.mode_combo.setCurrentIndex(initial_index)
            self._configure_slider_for_mode(self.mode_combo.currentData())
            # Prefer the preloaded middle-slice position when present.
            mode = self.mode_combo.currentData()
            preloaded = self._slices.get(mode)
            if preloaded is not None and mode in self._axes:
                self.position_slider.setValue(
                    self._axes[mode].index_of(preloaded.info.position)
                )
            self._update_position_label(self.position_slider.value())
        finally:
            self._suppress_slider = False
        self._show_selected_slice()

    def clear(self) -> None:
        self._reload_timer.stop()
        self._generation += 1
        self._latest_requests = {}
        self._prefetch_cache = {}
        self._stop_slice_worker()
        self._slices = {}
        self._source_path = ""
        self._axes = {}
        self._meta = None
        self._suppress_slider = True
        try:
            self.position_slider.setEnabled(False)
            self.position_slider.setMaximum(0)
            self.position_slider.setValue(0)
            self.position_label.setText("—")
        finally:
            self._suppress_slider = False
        self.profile.set_overlay_text("暂无地震切片")

    def _on_mode_changed(self, *_args) -> None:
        if self._suppress_slider:
            return
        mode = self.mode_combo.currentData()
        self._configure_slider_for_mode(mode)
        preloaded = self._slices.get(mode)
        if preloaded is not None and mode in self._axes:
            self._suppress_slider = True
            try:
                self.position_slider.setValue(
                    self._axes[mode].index_of(preloaded.info.position)
                )
            finally:
                self._suppress_slider = False
        self._update_position_label(self.position_slider.value())
        self._show_selected_slice()

    def _on_slider_changed(self, index: int) -> None:
        self._update_position_label(index)
        if self._suppress_slider:
            return
        # Use preloaded slice immediately when it matches; otherwise debounce SEGY I/O.
        mode = self.mode_combo.currentData()
        axis = self._axes.get(mode)
        if axis is None:
            return
        position = axis.position_at(index)
        preloaded = self._slices.get(mode)
        if preloaded is not None and int(preloaded.info.position) == position:
            self._apply_slice(preloaded)
            return
        self._reload_timer.start()

    def _configure_slider_for_mode(self, mode: str | None) -> None:
        axis = self._axes.get(mode or "")
        can_scrub = (
            bool(self._source_path)
            and axis is not None
            and axis.count > 1
        )
        self.position_slider.setEnabled(can_scrub)
        if axis is None or axis.count <= 0:
            self.position_slider.setMaximum(0)
            self.position_slider.setValue(0)
            return
        self.position_slider.setMaximum(max(0, axis.count - 1))
        # Keep current index if still in range; otherwise middle.
        if self.position_slider.value() > axis.count - 1:
            self.position_slider.setValue(axis.count // 2)

    def _update_position_label(self, index: int) -> None:
        mode = self.mode_combo.currentData() or "inline"
        axis = self._axes.get(mode)
        label = _MODE_LABELS.get(mode, mode)
        if axis is None or axis.count <= 0:
            self.position_label.setText("—")
            return
        position = axis.position_at(index)
        if mode == "time":
            self.position_label.setText(f"{label}: {position}")
        else:
            self.position_label.setText(f"{label}: {position}")

    def _show_selected_slice(self, *args) -> None:
        mode = self.mode_combo.currentData()
        seismic_slice = self._slices.get(mode)
        if seismic_slice is None:
            # Try loading from disk if we only have axes (edge case).
            self._reload_current_position()
            return
        axis = self._axes.get(mode)
        if axis is not None:
            desired = axis.position_at(self.position_slider.value())
            if int(seismic_slice.info.position) != desired and self._source_path:
                self._reload_current_position()
                return
        self._apply_slice(seismic_slice)

    def _reload_current_position(self) -> None:
        mode = self.mode_combo.currentData()
        if not mode or not self._source_path:
            return
        axis = self._axes.get(mode)
        if axis is None or axis.count <= 0:
            return
        position = axis.position_at(self.position_slider.value())
        preloaded = self._slices.get(mode)
        if preloaded is not None and int(preloaded.info.position) == position:
            self._apply_slice(preloaded)
            return
        cached = self._prefetch_cache.pop((mode, position), None)
        if cached is not None:
            self._slices[mode] = cached
            self._apply_slice(cached)
            return
        # Async: the worker keeps one SeismicLoader open and re-reads only the
        # requested slice; results arrive via slice_ready on the UI thread.
        self._ensure_slice_worker()
        self._latest_requests[mode] = position
        self._slice_worker.request(mode, position, self._generation)

    def _build_slice_from_raw(self, mode: str, position: int, data) -> SeismicSlice:
        """Convert a worker-produced raw slice into a display SeismicSlice."""
        if self._meta is None:
            raise ValueError("missing volume metadata")
        display_data = np.asarray(data).T
        row_step, col_step = _sample_steps(display_data, self._max_slice_axis)
        return SeismicSlice(
            data=downsample_2d(display_data, self._max_slice_axis),
            info=_slice_info(
                mode,
                int(position),
                display_data,
                self._meta,
                row_step,
                col_step,
            ),
        )

    def _on_slice_ready(
        self, slice_type: str, actual_pos: int, data, generation: int
    ) -> None:
        if generation != self._generation or not self._source_path:
            return
        if self._latest_requests.get(slice_type) != actual_pos:
            return  # superseded by a newer position request
        try:
            seismic_slice = self._build_slice_from_raw(slice_type, actual_pos, data)
        except Exception as error:  # noqa: BLE001 — UI boundary
            self.profile.set_overlay_text(f"切片加载失败: {error}")
            return
        self._slices[slice_type] = seismic_slice
        if slice_type == self.mode_combo.currentData():
            self._apply_slice(seismic_slice)

    def _on_prefetch_ready(
        self, slice_type: str, actual_pos: int, data, generation: int
    ) -> None:
        if generation != self._generation or not self._source_path:
            return
        try:
            seismic_slice = self._build_slice_from_raw(slice_type, actual_pos, data)
        except Exception:  # noqa: BLE001 — prefetch failure is non-fatal
            return
        if len(self._prefetch_cache) >= 32:
            self._prefetch_cache.clear()
        self._prefetch_cache[(slice_type, actual_pos)] = seismic_slice

    def _on_slice_read_error(
        self, slice_type: str, actual_pos: int, generation: int
    ) -> None:
        if generation != self._generation:
            return
        self.profile.set_overlay_text(f"切片加载失败: {slice_type} {actual_pos}")

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

    def _stop_slice_worker(self) -> None:
        """Stop the slice-read worker exactly once (idempotent)."""
        if self._slice_worker is not None and not self._slice_worker_stopped:
            self._slice_worker_stopped = True
            self._slice_worker.stop()

    def cleanup(self) -> None:
        """Stop the background reader and reset the widget (e.g. on release)."""
        self._generation += 1
        self._stop_slice_worker()
        self.clear()

    def __del__(self):
        # Widgets are often dropped without cleanup() (tests, tab switches);
        # the long-lived worker thread must not outlive the process or it
        # aborts at interpreter teardown ("QThread: Destroyed while still
        # running").
        try:
            self._stop_slice_worker()
        except Exception:  # noqa: BLE001, S110 — best-effort teardown
            pass

    def _apply_slice(self, seismic_slice: SeismicSlice) -> None:
        self.profile.set_overlay_text(None)
        self.profile.update_profile(seismic_slice.data, slice_info=seismic_slice.info)


__all__ = [
    "SeismicAxisSpec",
    "SeismicPreviewPayload",
    "SeismicPreviewWidget",
    "SeismicSlice",
    "axis_specs_from_meta",
    "downsample_2d",
    "load_preview_slice",
]
