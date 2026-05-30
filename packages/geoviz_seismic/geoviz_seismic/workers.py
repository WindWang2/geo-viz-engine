from __future__ import annotations

import numpy as np
from PySide6.QtCore import QThread, Signal

from .loader import SeismicLoader


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
