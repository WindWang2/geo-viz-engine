from __future__ import annotations

import logging
import time

import numpy as np
import segyio

from .models import SeismicVolumeMeta

logger = logging.getLogger(__name__)


class SeismicLoader:
    """On-demand SEGY file reader built on segyio.

    Opens the file lazily on first access. Supports inline, crossline,
    and time-slice reads with optional down-sampled volume extraction.

    Usage::

        with SeismicLoader("cube.sgy") as loader:
            meta = loader.inspect()
            inline_100 = loader.read_inline(100)
    """

    def __init__(self, path: str):
        self._path = path
        self._f: segyio.SegyFile | None = None
        self._meta: SeismicVolumeMeta | None = None
        self._downsampled: np.ndarray | None = None

    def inspect(self) -> SeismicVolumeMeta:
        """Read SEGY headers and return volume metadata.

        Caches the result; safe to call repeatedly.
        """
        if self._meta is not None:
            return self._meta
        f = self._open()
        ilines = np.asarray(f.ilines, dtype=np.int32)
        xlines = np.asarray(f.xlines, dtype=np.int32)
        samples = np.asarray(f.samples, dtype=np.float64)
        try:
            dt_us = int(f.bin[segyio.BinField.Interval])
        except Exception:
            dt_us = 0
        if dt_us > 0:
            dt_ms = dt_us / 1000.0
        elif samples.size >= 2:
            dt_ms = float(samples[1] - samples[0])
        else:
            dt_ms = 4.0

        self._meta = SeismicVolumeMeta(
            filename=self._path,
            n_inlines=int(ilines.size),
            n_crosslines=int(xlines.size),
            n_samples=int(samples.size),
            sample_interval=dt_ms,
            iline_start=int(ilines[0]),
            iline_step=int(ilines[1] - ilines[0]) if ilines.size > 1 else 1,
            xline_start=int(xlines[0]),
            xline_step=int(xlines[1] - xlines[0]) if xlines.size > 1 else 1,
            dt_ms=dt_ms,
            t0_ms=float(samples[0]),
        )
        return self._meta

    def read_inline(self, iline: int) -> np.ndarray:
        """Read one inline slice. Returns shape ``(n_xlines, n_samples)``."""
        try:
            t0 = time.monotonic()
            f = self._open()
            data = np.asarray(f.iline[iline], dtype=np.float32)
            logger.debug("read_inline(%d): %.3fs, shape=%s", iline,
                         time.monotonic() - t0, data.shape)
            return data
        except (KeyError, ValueError) as e:
            raise ValueError(
                f"Failed to read inline {iline} from {self._path}: "
                f"{e}. Inline may be out of range "
                f"(available: {f.ilines[0]}-{f.ilines[-1]})."
            ) from e

    def read_crossline(self, xline: int) -> np.ndarray:
        """Read one crossline slice. Returns shape ``(n_inlines, n_samples)``."""
        try:
            t0 = time.monotonic()
            f = self._open()
            data = np.asarray(f.xline[xline], dtype=np.float32)
            logger.debug("read_crossline(%d): %.3fs, shape=%s", xline,
                         time.monotonic() - t0, data.shape)
            return data
        except (KeyError, ValueError) as e:
            raise ValueError(
                f"Failed to read crossline {xline} from {self._path}: "
                f"{e}. Crossline may be out of range "
                f"(available: {f.xlines[0]}-{f.xlines[-1]})."
            ) from e

    def read_timeslice(self, sample_idx: int) -> np.ndarray:
        """Read one time slice (zero-based index). Returns ``(n_inlines, n_xlines)``."""
        try:
            t0 = time.monotonic()
            f = self._open()
            meta = self._meta or self.inspect()
            try:
                data = np.asarray(f.depth_slice[sample_idx], dtype=np.float32)
            except (AttributeError, KeyError):
                result = np.empty((meta.n_inlines, meta.n_crosslines),
                                  dtype=np.float32)
                for i, il in enumerate(f.ilines.tolist()):
                    line = np.asarray(f.iline[il], dtype=np.float32)
                    result[i, :] = line[:, sample_idx]
                data = result
            logger.debug("read_timeslice(%d): %.3fs, shape=%s", sample_idx,
                         time.monotonic() - t0, data.shape)
            return data
        except (IndexError, KeyError) as e:
            meta = self._meta or self.inspect()
            raise ValueError(
                f"Failed to read time slice {sample_idx} from {self._path}: "
                f"{e}. Sample index may be out of range "
                f"(available: 0-{meta.n_samples - 1})."
            ) from e

    def get_volume_downsampled(self, factor: tuple[int, int, int] = (4, 4, 2)) -> np.ndarray:
        """Read the full volume with stride-based downsampling.

        Args:
            factor: Stride ``(inline, crossline, sample)``. ``(4, 4, 2)``
                reads every 4th inline, every 4th crossline, every 2nd sample.

        Returns:
            ``float32`` array of shape ``(n_il // fi, n_xl // fx, n_s // ft)``.
        """
        if self._downsampled is not None:
            return self._downsampled
        meta = self.inspect()
        f = self._open()
        fi, fx, ft = factor
        il_indices = range(0, meta.n_inlines, fi)
        xl_indices = range(0, meta.n_crosslines, fx)
        t_indices = range(0, meta.n_samples, ft)
        vol = np.empty((len(il_indices), len(xl_indices), len(t_indices)), dtype=np.float32)
        for i, il_idx in enumerate(il_indices):
            il = int(f.ilines[il_idx])
            line = np.asarray(f.iline[il], dtype=np.float32)
            vol[i, :, :] = line[np.array(xl_indices)][:, np.array(t_indices)]
        self._downsampled = vol
        return vol

    def close(self):
        """Close the underlying SEGY file handle."""
        if self._f is not None:
            self._f.close()
            self._f = None

    def _open(self) -> segyio.SegyFile:
        if self._f is None:
            self._f = segyio.open(self._path, "r", strict=False, ignore_geometry=False)
        return self._f

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False
