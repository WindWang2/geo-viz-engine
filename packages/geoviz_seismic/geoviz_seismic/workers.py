from __future__ import annotations

from dataclasses import dataclass
import logging
import math
import time

import numpy as np
from PySide6.QtCore import QCoreApplication, QMutex, QMutexLocker, QThread, QWaitCondition, Signal

from .loader import SeismicLoader

logger = logging.getLogger(__name__)

DEFAULT_MAX_PREVIEW_VOXELS = 128 * 128 * 128


def downsample_factor_for_budget(
    shape: tuple[int, int, int],
    *,
    max_voxels: int = DEFAULT_MAX_PREVIEW_VOXELS,
) -> tuple[int, int, int]:
    """Return near-isotropic integer strides whose output fits *max_voxels*."""
    dims = tuple(max(1, int(value)) for value in shape)
    budget = max(1, int(max_voxels))
    if math.prod(dims) <= budget:
        return (1, 1, 1)
    scale = (math.prod(dims) / budget) ** (1.0 / 3.0)
    factors = [max(1, int(math.floor(scale))) for _ in dims]

    def output_voxels() -> int:
        return math.prod(math.ceil(dim / factor) for dim, factor in zip(dims, factors))

    while output_voxels() > budget:
        axis = max(
            range(3),
            key=lambda index: math.ceil(dims[index] / factors[index]),
        )
        factors[axis] += 1
    return tuple(factors)


class _LoadInterrupted(RuntimeError):
    pass


class _WorkerCancellationToken:
    def __init__(self, worker: QThread) -> None:
        self._worker = worker

    def raise_if_cancelled(self) -> None:
        if self._worker.isInterruptionRequested():
            raise _LoadInterrupted("SEGY load interrupted")


@dataclass(frozen=True)
class SeismicLoadResult:
    generation: int
    meta: object
    volume: np.ndarray
    raw_inline: np.ndarray
    raw_crossline: np.ndarray
    raw_timeslice: np.ndarray
    path: str
    downsample_factor: tuple[int, int, int]


@dataclass(frozen=True)
class SeismicLoadError:
    generation: int
    message: str


_ACTIVE_WORKERS: set[QThread] = set()
_SHUTDOWN_CONNECTED = False


def _shutdown_background_workers(timeout_ms: int = 5_000) -> None:
    """Cooperatively stop all retained workers within one shared deadline."""
    workers = tuple(_ACTIVE_WORKERS)
    for worker in workers:
        if worker.isRunning():
            worker.requestInterruption()
    deadline = time.monotonic() + max(0, int(timeout_ms)) / 1000.0
    for worker in workers:
        if not worker.isRunning():
            continue
        remaining_ms = max(0, int((deadline - time.monotonic()) * 1000))
        if remaining_ms <= 0:
            break
        worker.wait(remaining_ms)


def retain_background_worker(worker: QThread) -> None:
    """Keep an unparented QThread alive until it actually stops."""
    global _SHUTDOWN_CONNECTED
    _ACTIVE_WORKERS.add(worker)
    worker.finished.connect(lambda worker=worker: _ACTIVE_WORKERS.discard(worker))
    app = QCoreApplication.instance()
    if app is not None and not _SHUTDOWN_CONNECTED:
        app.aboutToQuit.connect(_shutdown_background_workers)
        _SHUTDOWN_CONNECTED = True


def generate_synthetic(
    n_inlines: int = 200, n_crosslines: int = 200, n_samples: int = 200
) -> np.ndarray:
    """Generate synthetic seismic with geologically realistic structure:
    horizontal reflectors with gentle dip, a fault offset, and noise."""
    t = np.linspace(0, 4 * np.pi, n_samples, dtype=np.float32)
    il = np.arange(n_inlines, dtype=np.float32)
    xl = np.arange(n_crosslines, dtype=np.float32)

    dip_il = 0.02 * il[:, np.newaxis, np.newaxis]
    dip_xl = 0.015 * xl[np.newaxis, :, np.newaxis]
    t_3d = t[np.newaxis, np.newaxis, :]

    reflector = np.sin(t_3d + dip_il + dip_xl) + 0.5 * np.sin(
        2.3 * t_3d + dip_il + dip_xl
    )
    field = reflector.copy()

    fault_il = n_inlines // 2
    offset = 5
    field[fault_il:, :, offset:] = field[fault_il:, :, :-offset].copy()
    field[fault_il:, :, :offset] = 0
    rng = np.random.default_rng(42)
    noise = rng.normal(0, 0.15, field.shape).astype(np.float32)
    return field + noise


class SyntheticWorker(QThread):
    """Background thread for synthetic data generation."""

    done = Signal(object)  # np.ndarray

    def run(self):
        data = generate_synthetic()
        self.done.emit(data)


class SegyLoadWorker(QThread):
    """Background thread for SEGY file loading."""

    done = Signal(object)  # SeismicLoadResult
    error = Signal(object)  # SeismicLoadError

    def __init__(
        self,
        path: str,
        parent=None,
        *,
        generation: int = 0,
        max_voxels: int = DEFAULT_MAX_PREVIEW_VOXELS,
    ):
        super().__init__(parent)
        self._path = path
        self._generation = int(generation)
        self._max_voxels = max(1, int(max_voxels))

    def run(self):
        loader = None
        result = None
        failure = None
        token = _WorkerCancellationToken(self)
        try:
            loader = SeismicLoader(self._path)
            meta = loader.inspect()
            token.raise_if_cancelled()
            factor = downsample_factor_for_budget(
                (meta.n_inlines, meta.n_crosslines, meta.n_samples),
                max_voxels=self._max_voxels,
            )
            vol = loader.get_volume_downsampled(
                factor=factor,
                cancellation_token=token,
            )
            mid_il = meta.iline_start + (meta.n_inlines // 2) * meta.iline_step
            mid_xl = meta.xline_start + (meta.n_crosslines // 2) * meta.xline_step
            mid_t = meta.n_samples // 2  # index

            token.raise_if_cancelled()
            raw_il = loader.read_inline(mid_il)
            token.raise_if_cancelled()
            raw_xl = loader.read_crossline(mid_xl)
            token.raise_if_cancelled()
            raw_t = loader.read_timeslice(mid_t)
            token.raise_if_cancelled()
            result = SeismicLoadResult(
                generation=self._generation,
                meta=meta,
                volume=vol,
                raw_inline=raw_il,
                raw_crossline=raw_xl,
                raw_timeslice=raw_t,
                path=self._path,
                downsample_factor=factor,
            )
        except _LoadInterrupted:
            pass
        except Exception as exc:
            failure = SeismicLoadError(self._generation, str(exc))
        finally:
            if loader is not None:
                loader.close()
        if result is not None:
            self.done.emit(result)
        elif failure is not None:
            self.error.emit(failure)


@dataclass(frozen=True)
class AttrComputeRequest:
    """One slice-attribute computation request.

    Attributes:
        generation: View-level submission generation; the per-panel latest
            value supersedes older in-flight computations.
        segy_generation: Volume generation — results from a superseded
            volume must be dropped by the view.
        slice_type: ``"inline"``, ``"crossline"`` or ``"time"``.
        position: Survey position of the slice (line number or sample index).
        attr_idx: Index into :data:`attribute_pipeline.ATTRIBUTES`.
        data: 2-D raw slice (display orientation, as passed to the panel).
        sample_interval_s: Sample interval in seconds (trace attributes).
        rgb_channels: When not ``None``, compute an RGB fusion from these
            three attribute indices instead of a single attribute.
    """

    generation: int
    segy_generation: int
    slice_type: str
    position: int
    attr_idx: int
    data: np.ndarray
    sample_interval_s: float
    rgb_channels: tuple[int, int, int] | None = None

    @property
    def queue_key(self) -> tuple:
        """Worker-side latest-wins key: one pending computation per panel+mode."""
        return (self.slice_type, self.attr_idx, self.rgb_channels)


@dataclass(frozen=True)
class AttrComputeResult:
    generation: int
    segy_generation: int
    slice_type: str
    position: int
    attr_idx: int
    rgb_channels: tuple[int, int, int] | None
    display: np.ndarray


@dataclass(frozen=True)
class AttrComputeError:
    generation: int
    segy_generation: int
    slice_type: str
    position: int
    attr_idx: int
    message: str


_C3_ATTR_LABEL = "相干性(C3)"
_C3_DOWNSAMPLE_MIN_PIXELS = 600


def _compute_attr_display(request: AttrComputeRequest) -> np.ndarray:
    """Run the requested attribute computation (worker thread; no GUI access).

    C3 coherence is O(n_traces * n_t * window) per power-iteration row and
    is the slowest attribute on large slices — stride the input ~4x and
    block-upsample the result so the panel axis mapping and output shape
    stay unchanged.
    """
    from . import attribute_pipeline as _ap
    from . import attributes as _attr

    si = request.sample_interval_s
    if request.rgb_channels is not None:
        r = _ap.apply(request.rgb_channels[0], request.data, sample_interval_s=si)
        g = _ap.apply(request.rgb_channels[1], request.data, sample_interval_s=si)
        b = _ap.apply(request.rgb_channels[2], request.data, sample_interval_s=si)
        rgb = _attr.fuse_rgb(r, g, b)
        alpha = np.full((*rgb.shape[:2], 1), 255, dtype=np.uint8)
        return np.concatenate([rgb, alpha], axis=-1)

    is_c3 = (
        0 <= request.attr_idx < len(_ap.ATTRIBUTES)
        and _ap.ATTRIBUTES[request.attr_idx].label == _C3_ATTR_LABEL
    )
    data = request.data
    if is_c3 and data.ndim == 2 and max(data.shape) > _C3_DOWNSAMPLE_MIN_PIXELS:
        stride = 2
        small = data[::stride, ::stride]
        out_small = _ap.apply(request.attr_idx, small, sample_interval_s=si)
        upscaled = np.repeat(np.repeat(out_small, stride, axis=0), stride, axis=1)
        # ``upscaled`` already holds coherence values — return directly so the
        # shared tail below does not run C3 a second time on them.
        return upscaled[: request.data.shape[0], : request.data.shape[1]]
    return _ap.apply(request.attr_idx, data, sample_interval_s=si)


class AttrComputeWorker(QThread):
    """Background thread for slice attribute computation.

    C3 / curvature / RGB fusion take seconds on large slices and must not
    run on the GUI thread.  Mirrors the ``SegyLoadWorker`` generation
    pattern: the view bumps a per-panel generation on every submission and
    drops results whose generation no longer matches.
    """

    done = Signal(object)   # AttrComputeResult
    error = Signal(object)  # AttrComputeError

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mutex = QMutex()
        self._cond = QWaitCondition()
        self._queue: dict[tuple, AttrComputeRequest] = {}
        self._stop = False

    # --- GUI-thread API ---

    def submit(self, request: AttrComputeRequest) -> None:
        with QMutexLocker(self._mutex):
            # Latest wins: a newer request for the same panel+mode supersedes
            # any queued (e.g. intermediate drag positions).
            self._queue[request.queue_key] = request
        self._cond.wakeAll()

    def stop(self) -> None:
        with QMutexLocker(self._mutex):
            self._stop = True
            self._queue.clear()
        self._cond.wakeAll()
        self.wait(1500)

    def ensure_running(self) -> None:
        """Restart the worker after a stop (e.g. view cleanup)."""
        with QMutexLocker(self._mutex):
            self._stop = False
        if not self.isRunning():
            self.start()

    # --- worker thread ---

    def _take_next(self) -> AttrComputeRequest | None:
        with QMutexLocker(self._mutex):
            if not self._queue:
                return None
            key = next(iter(self._queue))
            return self._queue.pop(key)

    def run(self):
        while True:
            with QMutexLocker(self._mutex):
                if self._stop:
                    return
                if not self._queue:
                    self._cond.wait(self._mutex)
                    continue
            request = self._take_next()
            if request is None:
                continue
            try:
                display = _compute_attr_display(request)
            except Exception as exc:
                self.error.emit(AttrComputeError(
                    request.generation, request.segy_generation,
                    request.slice_type, request.position, request.attr_idx,
                    str(exc),
                ))
                continue
            self.done.emit(AttrComputeResult(
                request.generation, request.segy_generation,
                request.slice_type, request.position, request.attr_idx,
                request.rgb_channels, display,
            ))


class SliceReadWorker(QThread):
    """Long-lived background slice reader with a latest-wins queue and prefetch.

    Owns its own SeismicLoader inside the worker thread (segyio handles are
    not thread-safe). GUI thread submits requests; results come back via
    signals. Prefetch results use a separate signal so the view can cache
    them without refreshing panels.
    """

    slice_ready = Signal(str, int, object, int)    # type, actual_pos, ndarray, generation
    prefetch_ready = Signal(str, int, object, int)  # type, actual_pos, ndarray, generation
    read_error = Signal(str, int, int)              # type, actual_pos, generation

    _PREFETCH_OFFSETS = (1, -1, 2, -2)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mutex = QMutex()
        self._cond = QWaitCondition()
        self._requests: dict[str, tuple[int, int]] = {}  # slice_type -> (actual_pos, generation)
        self._volume_path: str | None = None
        self._volume_generation = 0
        self._volume_dirty = False
        self._stop = False

    # --- GUI-thread API ---

    def set_volume(self, path: str, generation: int) -> None:
        with QMutexLocker(self._mutex):
            self._volume_path = path
            self._volume_generation = int(generation)
            self._volume_dirty = True
            self._requests.clear()
        self._cond.wakeAll()

    def request(self, slice_type: str, actual_pos: int, generation: int) -> None:
        with QMutexLocker(self._mutex):
            # Latest wins: replace any queued request of the same slice type
            self._requests[slice_type] = (int(actual_pos), int(generation))
        self._cond.wakeAll()

    def stop(self) -> None:
        """Request cooperative shutdown without blocking the GUI thread.

        The worker observes ``_stop`` / the interruption on its next
        wake-up and exits; the global ``_ACTIVE_WORKERS`` registry keeps
        the thread object alive and reaps it once ``finished`` fires
        (detach semantics — a mid-read slice can not be interrupted, so
        we only wait a short courtesy window instead of hanging the GUI).
        """
        with QMutexLocker(self._mutex):
            self._stop = True
        self.requestInterruption()
        self._cond.wakeAll()
        self.wait(1500)

    def ensure_running(self) -> None:
        """Restart the worker if it was stopped (e.g. after view cleanup)."""
        with QMutexLocker(self._mutex):
            self._stop = False
        # Self-healing window: if run() is mid-exit, isRunning() is still
        # True so start() is skipped; the next cache-miss request re-triggers
        # _ensure_slice_worker() and starts the thread once run() has exited.
        if not self.isRunning():
            self.start()

    # --- worker thread ---

    def _take_next(self) -> tuple[str, int, int] | None:
        with QMutexLocker(self._mutex):
            if not self._requests:
                return None
            slice_type = next(iter(self._requests))
            pos, generation = self._requests.pop(slice_type)
            return slice_type, pos, generation

    def _current_volume(self) -> tuple[str | None, int, bool]:
        with QMutexLocker(self._mutex):
            dirty = self._volume_dirty
            self._volume_dirty = False
            return self._volume_path, self._volume_generation, dirty

    def run(self):
        loader = None
        failed_path: str | None = None
        try:
            while True:
                with QMutexLocker(self._mutex):
                    if self._stop:
                        return
                    if not self._requests and not self._volume_dirty:
                        self._cond.wait(self._mutex)
                        if self._stop:
                            return
                path, generation, dirty = self._current_volume()
                if dirty:
                    if loader is not None:
                        loader.close()
                        loader = None
                    failed_path = None
                if path is None:
                    continue
                if loader is None:
                    if failed_path == path:
                        # Loader construction already failed for this volume:
                        # drain/skip its requests instead of hot-looping on
                        # retries, but keep the thread alive.
                        with QMutexLocker(self._mutex):
                            self._requests.clear()
                        continue
                    try:
                        loader = SeismicLoader(path)
                    except Exception:
                        logger.exception("Failed to open SEGY volume: %s", path)
                        failed_path = path
                        continue
                item = self._take_next()
                if item is None:
                    continue
                slice_type, pos, gen = item
                if gen != generation:
                    continue  # stale request from a previous volume
                try:
                    data, meta, step = self._read(loader, slice_type, pos)
                except Exception:
                    logger.exception("Slice read failed: %s %d", slice_type, pos)
                    self.read_error.emit(slice_type, pos, gen)
                    continue
                self.slice_ready.emit(slice_type, pos, data, gen)
                self._prefetch(loader, meta, slice_type, pos, step, gen)
        finally:
            if loader is not None:
                loader.close()

    @staticmethod
    def _read(loader, slice_type: str, pos: int):
        meta = loader.inspect()
        if slice_type == "inline":
            return loader.read_inline(pos), meta, meta.iline_step
        if slice_type == "crossline":
            return loader.read_crossline(pos), meta, meta.xline_step
        return loader.read_timeslice(pos), meta, 1

    def _prefetch(self, loader, meta, slice_type: str, pos: int, step: int, gen: int) -> None:
        bounds = {
            "inline": (meta.iline_start, meta.iline_start + (meta.n_inlines - 1) * meta.iline_step),
            "crossline": (meta.xline_start, meta.xline_start + (meta.n_crosslines - 1) * meta.xline_step),
            "time": (0, meta.n_samples - 1),
        }
        lo, hi = bounds[slice_type]
        for off in self._PREFETCH_OFFSETS:
            if self.isInterruptionRequested():
                return
            neighbor = pos + off * step
            if not (lo <= neighbor <= hi):
                continue
            with QMutexLocker(self._mutex):
                if slice_type in self._requests:
                    return  # user request pending: prefetch later
            try:
                data, _, _ = self._read(loader, slice_type, neighbor)
            except Exception:
                continue
            self.prefetch_ready.emit(slice_type, neighbor, data, gen)
