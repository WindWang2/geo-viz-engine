from __future__ import annotations

from dataclasses import dataclass
import math
import time

import numpy as np
from PySide6.QtCore import QCoreApplication, QThread, Signal

from .loader import SeismicLoader

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
