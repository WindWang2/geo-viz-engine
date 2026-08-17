from __future__ import annotations

import logging
import math
import os
import threading
import time

import numpy as np
import segyio

from .models import BinGridGeometry, SeismicVolumeMeta

logger = logging.getLogger(__name__)

# (abspath, mtime_ns, size) -> (iline_byte, xline_byte) or None (unstructured).
_GEOMETRY_FIELD_CACHE: dict[tuple[str, int, int], tuple[int, int] | None] = {}
_GEOMETRY_FIELD_CACHE_LOCK = threading.Lock()
_MISSING = object()

_HEADER_FIELD_CANDIDATES: tuple[tuple[object, str], ...] = (
    (segyio.TraceField.CDP, "CDP"),
    (segyio.TraceField.FieldRecord, "FieldRecord"),
    (segyio.TraceField.TRACE_SEQUENCE_LINE, "TraceSeqLine"),
    (segyio.TraceField.EnergySourcePoint, "EnergySourcePt"),
    (segyio.TraceField.INLINE_3D, "Inline3D"),
    (segyio.TraceField.CROSSLINE_3D, "Crossline3D"),
)


def clear_geometry_field_cache() -> None:
    """Drop the per-file geometry-field memo (tests / file-replaced-in-place)."""
    with _GEOMETRY_FIELD_CACHE_LOCK:
        _GEOMETRY_FIELD_CACHE.clear()


def _geometry_cache_key(path: str) -> tuple[str, int, int]:
    st = os.stat(path)
    mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)))
    return (os.path.abspath(path), mtime_ns, int(st.st_size))


def read_header_attribute(f, field) -> np.ndarray:
    """Read one trace-header field for every trace as int64.

    Prefers segyio's C-accelerated ``attributes`` collector; falls back to
    a per-trace header loop only when that path is unavailable.
    """
    try:
        return np.asarray(f.attributes(field)[:], dtype=np.int64)
    except Exception:
        n = int(f.tracecount)
        out = np.empty(n, dtype=np.int64)
        for i in range(n):
            out[i] = int(f.header[i][field])
        return out


def detect_iline_xline_fields(f) -> tuple[int, int] | None:
    """Return ``(iline_byte, xline_byte)`` if two header fields grid the file."""
    n_traces = int(f.tracecount)
    if n_traces < 2:
        return None
    field_arrays: dict[int, tuple[str, np.ndarray, int]] = {}
    for field, name in _HEADER_FIELD_CANDIDATES:
        arr = read_header_attribute(f, field)
        if arr.size != n_traces:
            continue
        nuniq = int(np.unique(arr).size)
        if nuniq > 1:
            field_arrays[int(field)] = (name, arr, nuniq)

    fields = list(field_arrays.keys())
    for i in range(len(fields)):
        for j in range(i + 1, len(fields)):
            _name_a, arr_a, n_a = field_arrays[fields[i]]
            _name_b, arr_b, n_b = field_arrays[fields[j]]
            if n_a * n_b != n_traces:
                continue
            packed = (arr_a.astype(np.int64) << 32) ^ (arr_b.astype(np.int64) & 0xFFFFFFFF)
            if int(np.unique(packed).size) != n_traces:
                continue
            # Field that changes on consecutive traces is the fast axis;
            # historical loader assigned that byte to segyio's ``iline``.
            if int(arr_a[0]) != int(arr_a[1]):
                return int(fields[i]), int(fields[j])
            return int(fields[j]), int(fields[i])
    return None


def _header_int(header, field) -> int:
    try:
        return int(header[field])
    except Exception:
        return 0


def _apply_coord_scalar(x: float, y: float, header) -> tuple[float, float]:
    """SEGY SourceGroupScalar: >0 multiply, <0 divide, 0 means metres."""
    scalar = _header_int(header, segyio.TraceField.SourceGroupScalar)
    if scalar > 0:
        return x * scalar, y * scalar
    if scalar < 0:
        return x / float(-scalar), y / float(-scalar)
    return x, y


def _corner_xy(headers: list) -> list[tuple[float, float]] | None:
    """World (x, y) for 3 corner traces: prefer CDP_X/Y, else SourceX/Y."""
    cdp = [
        (
            float(_header_int(h, segyio.TraceField.CDP_X)),
            float(_header_int(h, segyio.TraceField.CDP_Y)),
        )
        for h in headers
    ]
    if any(x or y for x, y in cdp):
        pairs = cdp
    else:
        src = [
            (
                float(_header_int(h, segyio.TraceField.SourceX)),
                float(_header_int(h, segyio.TraceField.SourceY)),
            )
            for h in headers
        ]
        if not any(x or y for x, y in src):
            return None
        pairs = src
    return [_apply_coord_scalar(x, y, h) for (x, y), h in zip(pairs, headers)]


def _grid_trace_index(il_idx: int, xl_idx: int, n_il: int, n_xl: int, sorting) -> int:
    if sorting == segyio.TraceSortingFormat.CROSSLINE_SORTING:
        return int(xl_idx) * int(n_il) + int(il_idx)
    return int(il_idx) * int(n_xl) + int(xl_idx)


def _infer_bin_grid(f, ilines, xlines) -> BinGridGeometry | None:
    """Build BinGridGeometry from three corner CDP (or Source) coordinates.

    Reads only the origin, +1-inline, and +1-crossline traces — no full
    header scan. Returns None when coordinates are missing or degenerate.
    """
    try:
        n_il = int(len(ilines))
        n_xl = int(len(xlines))
        if n_il < 2 or n_xl < 2:
            return None
        n_traces = int(f.tracecount)
        if n_traces < n_il * n_xl:
            return None
        sorting = getattr(f, "sorting", None)
        corners = []
        for il_idx, xl_idx in ((0, 0), (1, 0), (0, 1)):
            idx = _grid_trace_index(il_idx, xl_idx, n_il, n_xl, sorting)
            if idx < 0 or idx >= n_traces:
                return None
            corners.append(f.header[idx])
        xy = _corner_xy(corners)
        if xy is None:
            return None
        (x0, y0), (x_il, y_il), (x_xl, y_xl) = xy
        il_dx, il_dy = x_il - x0, y_il - y0
        xl_dx, xl_dy = x_xl - x0, y_xl - y0
        il_spacing = math.hypot(il_dx, il_dy)
        xl_spacing = math.hypot(xl_dx, xl_dy)
        if il_spacing <= 0.0 or xl_spacing <= 0.0:
            return None
        # Clockwise from north (+Y), matching BinGridGeometry.
        az = math.degrees(math.atan2(il_dx, il_dy)) if (il_dx or il_dy) else 0.0
        az_rad = math.radians(az)
        sin_a, cos_a = math.sin(az_rad), math.cos(az_rad)
        pred_il = (-sin_a, cos_a)
        pred_xl = (cos_a, sin_a)
        if pred_il[0] * il_dx + pred_il[1] * il_dy < 0:
            il_spacing = -il_spacing
        if pred_xl[0] * xl_dx + pred_xl[1] * xl_dy < 0:
            xl_spacing = -xl_spacing
        return BinGridGeometry(
            x_origin=x0,
            y_origin=y0,
            il_azimuth_deg=az,
            il_spacing_m=il_spacing,
            xl_spacing_m=xl_spacing,
        )
    except Exception:
        logger.debug("bin_grid inference from CDP/Source headers failed", exc_info=True)
        return None


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
        self._downsample_factor: tuple[int, int, int] | None = None
        # "standard_189_193" (real INLINE_3D/CROSSLINE_3D geometry),
        # "detected_headers" (fast/slow header-pair fallback), or "pseudo".
        self._geometry_source = "pseudo"
        # (iline_byte, xline_byte) actually used for geometry, when known —
        # consumers scanning headers must read the SAME pair the loader did.
        self._geometry_fields = None

    @property
    def geometry_source(self) -> str:
        """How ilines/xlines were established (see _open)."""
        return self._geometry_source

    @property
    def geometry_fields(self) -> tuple[int, int] | None:
        """(iline, xline) trace-header byte positions used for geometry."""
        return self._geometry_fields

    def inspect(self) -> SeismicVolumeMeta:
        """Read SEGY headers and return volume metadata.

        Caches the result; safe to call repeatedly.
        """
        if self._meta is not None:
            return self._meta
        f = self._open()
        if f.ilines is None or f.xlines is None:
            # Fallback for unstructured mode: mock a single inline containing all traces as crosslines
            n_traces = f.tracecount
            ilines = np.array([1], dtype=np.int32)
            xlines = np.arange(1, n_traces + 1, dtype=np.int32)
        else:
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

        # Structured volumes may carry CDP_X/Y (or SourceX/Y). Infer a
        # BinGridGeometry from three corner traces; leave None when the
        # file has no usable coordinates so callers cannot silently use a
        # fabricated default grid.
        bin_grid = None
        if (
            f.ilines is not None
            and f.xlines is not None
            and ilines.size >= 2
            and xlines.size >= 2
            and self._geometry_source != "pseudo"
        ):
            bin_grid = _infer_bin_grid(f, ilines, xlines)

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
            geometry_source=self._geometry_source,
            geometry_fields=list(self._geometry_fields)
            if self._geometry_fields
            else None,
            bin_grid=bin_grid,
        )
        return self._meta

    def _uses_trace_index(self) -> bool:
        """True when structured ``f.iline`` / ``f.ilines`` accessors are unusable."""
        f = self._f
        if f is None:
            return False
        if getattr(f, "unstructured", False):
            return True
        if getattr(f, "ilines", None) is None or getattr(f, "xlines", None) is None:
            return True
        return self._geometry_source == "pseudo"

    @staticmethod
    def _header_axis_values(axis) -> list:
        if axis is None:
            return []
        try:
            return list(axis)
        except TypeError:
            return []

    def _trace_global_index(self, il_idx: int, xl_idx: int, meta: SeismicVolumeMeta) -> int:
        return int(il_idx) * int(meta.n_crosslines) + int(xl_idx)

    def _read_inline_from_traces(self, iline: int, meta: SeismicVolumeMeta) -> np.ndarray:
        f = self._open()
        step = meta.iline_step if meta.iline_step else 1
        il_idx = (int(iline) - meta.iline_start) // step
        if not (0 <= il_idx < meta.n_inlines):
            raise ValueError(
                f"Inline {iline} out of range "
                f"(available: {meta.iline_start}-"
                f"{meta.iline_start + (meta.n_inlines - 1) * step})."
            )
        n_xl, n_t = meta.n_crosslines, meta.n_samples
        out = np.empty((n_xl, n_t), dtype=np.float32)
        base = il_idx * n_xl
        for j in range(n_xl):
            out[j] = np.asarray(f.trace[base + j], dtype=np.float32)
        return out

    def _read_crossline_from_traces(self, xline: int, meta: SeismicVolumeMeta) -> np.ndarray:
        f = self._open()
        step = meta.xline_step if meta.xline_step else 1
        xl_idx = (int(xline) - meta.xline_start) // step
        if not (0 <= xl_idx < meta.n_crosslines):
            raise ValueError(
                f"Crossline {xline} out of range "
                f"(available: {meta.xline_start}-"
                f"{meta.xline_start + (meta.n_crosslines - 1) * step})."
            )
        n_il, n_xl, n_t = meta.n_inlines, meta.n_crosslines, meta.n_samples
        out = np.empty((n_il, n_t), dtype=np.float32)
        for i in range(n_il):
            out[i] = np.asarray(f.trace[i * n_xl + xl_idx], dtype=np.float32)
        return out

    def _read_timeslice_from_traces(
        self, sample_idx: int, meta: SeismicVolumeMeta, cancellation_token=None
    ) -> np.ndarray:
        f = self._open()
        if not (0 <= int(sample_idx) < meta.n_samples):
            raise ValueError(
                f"Failed to read time slice {sample_idx} from {self._path}: "
                f"Sample index may be out of range (available: 0-{meta.n_samples - 1})."
            )
        n_il, n_xl = meta.n_inlines, meta.n_crosslines
        out = np.empty((n_il, n_xl), dtype=np.float32)
        idx = int(sample_idx)
        for i in range(n_il):
            if cancellation_token is not None:
                cancellation_token.raise_if_cancelled()
            base = i * n_xl
            for j in range(n_xl):
                out[i, j] = np.asarray(f.trace[base + j], dtype=np.float32)[idx]
        return out

    def _volume_from_traces(
        self, factor: tuple[int, int, int], *, cancellation_token=None
    ) -> np.ndarray:
        meta = self._meta or self.inspect()
        f = self._open()
        fi, fx, ft = factor
        n_il, n_xl, n_t = meta.n_inlines, meta.n_crosslines, meta.n_samples
        il_idx = np.arange(0, n_il, fi)
        xl_idx = np.arange(0, n_xl, fx)
        t_idx = np.arange(0, n_t, ft)
        vol = np.empty((il_idx.size, xl_idx.size, t_idx.size), dtype=np.float32)
        for i, ii in enumerate(il_idx):
            if cancellation_token is not None:
                cancellation_token.raise_if_cancelled()
            base = int(ii) * n_xl
            for j, jj in enumerate(xl_idx):
                vol[i, j, :] = np.asarray(f.trace[base + int(jj)], dtype=np.float32)[t_idx]
        return vol

    def read_inline(self, iline: int) -> np.ndarray:
        """Read one inline slice. Returns shape ``(n_xlines, n_samples)``."""
        try:
            t0 = time.monotonic()
            f = self._open()
            meta = self._meta or self.inspect()
            if self._uses_trace_index():
                data = self._read_inline_from_traces(iline, meta)
            else:
                data = np.asarray(f.iline[iline], dtype=np.float32)
            logger.debug("read_inline(%d): %.3fs, shape=%s", iline,
                         time.monotonic() - t0, data.shape)
            return data
        except (KeyError, ValueError, AttributeError, TypeError) as e:
            ilines = self._header_axis_values(
                self._f.ilines if self._f is not None else None
            )
            raise ValueError(
                f"Failed to read inline {iline} from {self._path}: "
                f"{e}. Inline may be out of range "
                f"(available: {ilines[0] if len(ilines) > 0 else '?'}-{ilines[-1] if len(ilines) > 0 else '?'})."
            ) from e

    def read_crossline(self, xline: int) -> np.ndarray:
        """Read one crossline slice. Returns shape ``(n_inlines, n_samples)``."""
        try:
            t0 = time.monotonic()
            f = self._open()
            meta = self._meta or self.inspect()
            if self._uses_trace_index():
                data = self._read_crossline_from_traces(xline, meta)
            else:
                data = np.asarray(f.xline[xline], dtype=np.float32)
            logger.debug("read_crossline(%d): %.3fs, shape=%s", xline,
                         time.monotonic() - t0, data.shape)
            return data
        except (KeyError, ValueError, AttributeError, TypeError) as e:
            xlines = self._header_axis_values(
                self._f.xlines if self._f is not None else None
            )
            raise ValueError(
                f"Failed to read crossline {xline} from {self._path}: "
                f"{e}. Crossline may be out of range "
                f"(available: {xlines[0] if len(xlines) > 0 else '?'}-{xlines[-1] if len(xlines) > 0 else '?'})."
            ) from e

    def read_timeslice(self, sample_idx: int, *, cancellation_token=None) -> np.ndarray:
        """Read one time slice (zero-based index). Returns ``(n_inlines, n_xlines)``.

        Note: ``segyio`` ``depth_slice`` often returns ``(n_xlines, n_inlines)``
        for this geometry. We always normalize to volume axis order so 2D Time
        profiles match 3D horizontal planes (``volume[:, :, t]``).

        ``cancellation_token`` (optional) is polled while reading; pass one to
        abort the per-inline fallback early (it is O(volume) I/O).
        """
        try:
            t0 = time.monotonic()
            f = self._open()
            meta = self._meta or self.inspect()
            expected = (meta.n_inlines, meta.n_crosslines)
            if self._uses_trace_index():
                data = self._read_timeslice_from_traces(
                    sample_idx, meta, cancellation_token
                )
            else:
                try:
                    data = np.asarray(f.depth_slice[sample_idx], dtype=np.float32)
                except (AttributeError, KeyError, TypeError, ValueError):
                    # Slow path: depth_slice is unavailable, so build the slice
                    # inline by inline. Every trace of the cube is read — warn and
                    # poll the cancellation token so callers can abort early.
                    logger.warning(
                        "depth_slice unavailable for %s; reading time slice %d "
                        "via per-inline fallback (O(volume) I/O)",
                        self._path, sample_idx,
                    )
                    if cancellation_token is not None:
                        cancellation_token.raise_if_cancelled()
                    data = np.empty(expected, dtype=np.float32)
                    ilines = self._header_axis_values(getattr(f, "ilines", None))
                    if not ilines:
                        data = self._read_timeslice_from_traces(
                            sample_idx, meta, cancellation_token
                        )
                    else:
                        for i, il in enumerate(ilines):
                            if cancellation_token is not None:
                                cancellation_token.raise_if_cancelled()
                            line = np.asarray(f.iline[il], dtype=np.float32)
                            data[i, :] = line[:, sample_idx]
            data = self._normalize_timeslice_axes(data, meta)
            logger.debug("read_timeslice(%d): %.3fs, shape=%s", sample_idx,
                         time.monotonic() - t0, data.shape)
            return data
        except (IndexError, KeyError, AttributeError, TypeError) as e:
            meta = self._meta or self.inspect()
            raise ValueError(
                f"Failed to read time slice {sample_idx} from {self._path}: "
                f"{e}. Sample index may be out of range "
                f"(available: 0-{meta.n_samples - 1})."
            ) from e

    @staticmethod
    def _normalize_timeslice_axes(
        data: np.ndarray, meta: SeismicVolumeMeta
    ) -> np.ndarray:
        """Force timeslice to ``(n_inlines, n_crosslines)`` matching the cube."""
        expected = (int(meta.n_inlines), int(meta.n_crosslines))
        if data.shape == expected:
            return np.ascontiguousarray(data, dtype=np.float32)
        if data.shape == (expected[1], expected[0]):
            # segyio depth_slice often returns (n_xline, n_iline)
            return np.ascontiguousarray(data.T, dtype=np.float32)
        logger.warning(
            "timeslice shape %s does not match volume axes %s; returning as-is",
            data.shape,
            expected,
        )
        return np.ascontiguousarray(data, dtype=np.float32)

    def read_trace(self, iline: int, xline: int) -> np.ndarray:
        """Read a single trace at the given (inline, crossline) position.

        Uses direct trace indexing on the inline-sorted layout — one trace of
        I/O instead of gathering the whole inline gather (the old path cost
        O(n_xl * n_t) per call, which fenced fence extraction to ~1ms per
        column on large surveys).

        Returns:
            ``(n_samples,)`` float32 trace.
        """
        try:
            f = self._open()
            meta = self._meta or self.inspect()
            il_idx = (int(iline) - meta.iline_start) // meta.iline_step
            xl_idx = (int(xline) - meta.xline_start) // meta.xline_step
            if not (0 <= il_idx < meta.n_inlines):
                raise ValueError(
                    f"Inline {iline} out of range "
                    f"(available: {meta.iline_start}-{meta.iline_start + (meta.n_inlines - 1) * meta.iline_step})."
                )
            if not (0 <= xl_idx < meta.n_crosslines):
                raise ValueError(
                    f"({iline}, {xline}) out of range "
                    f"(inlines: {meta.iline_start}-{meta.iline_start + (meta.n_inlines - 1) * meta.iline_step}, "
                    f"crosslines: {meta.xline_start}-{meta.xline_start + (meta.n_crosslines - 1) * meta.xline_step})."
                )
            # Fast path: address the trace directly instead of pulling a whole
            # inline just for one trace. In structured mode segyio sorts traces
            # inline-then-crossline (INLINE_SORTING) or crossline-then-inline
            # (CROSSLINE_SORTING), so the global trace index is a simple stride
            # computation (Issue #64).
            sorting = getattr(f, "sorting", None)
            if self._uses_trace_index() or sorting is None:
                global_idx = self._trace_global_index(il_idx, xl_idx, meta)
                return np.asarray(f.trace[global_idx], dtype=np.float32)
            if sorting == segyio.TraceSortingFormat.INLINE_SORTING:
                global_idx = il_idx * meta.n_crosslines + xl_idx
                return np.asarray(f.trace[global_idx], dtype=np.float32)
            if sorting == segyio.TraceSortingFormat.CROSSLINE_SORTING:
                global_idx = xl_idx * meta.n_inlines + il_idx
                return np.asarray(f.trace[global_idx], dtype=np.float32)
            # Fallback: read the whole inline (e.g. unknown sorting) and index
            # the requested crossline column.
            inline_data = np.asarray(f.iline[iline], dtype=np.float32)
            return inline_data[xl_idx, :]
        except (KeyError, IndexError, ValueError, AttributeError, TypeError) as e:
            raise ValueError(
                f"Failed to read trace at ({iline}, {xline}) from {self._path}: {e}"
            ) from e

    def get_volume_downsampled(
        self,
        factor: tuple[int, int, int] = (4, 4, 2),
        *,
        cancellation_token=None,
    ) -> np.ndarray:
        """Read the full volume with stride-based downsampling.

        Args:
            factor: Stride ``(inline, crossline, sample)``. ``(4, 4, 2)``
                reads every 4th inline, every 4th crossline, every 2nd sample.

        Returns:
            ``float32`` array of shape ``(n_il // fi, n_xl // fx, n_s // ft)``.
        """
        factor = tuple(int(value) for value in factor)
        if len(factor) != 3 or any(value < 1 for value in factor):
            raise ValueError(f"downsample factor must contain three positive integers: {factor}")
        if self._downsampled is not None and self._downsample_factor == factor:
            return self._downsampled
        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()
        meta = self.inspect()
        f = self._open()
        fi, fx, ft = factor

        if self._uses_trace_index():
            vol = self._volume_from_traces(factor, cancellation_token=cancellation_token)
            self._downsampled = vol
            self._downsample_factor = factor
            return vol

        # Fast path: use segyio.tools.cube C-extension reader ONLY when reading
        # at full resolution (factor 1,1,1). When downsampling, tools.cube
        # reads the entire file into memory (1GB+ for a typical 500x500x1000
        # volume) just to slice it — the strided iline path below reads only
        # the needed fraction (e.g. 4x less I/O at factor 4,4,8).
        if (
            self._f is not None
            and not getattr(self._f, "unstructured", False)
            and factor == (1, 1, 1)
        ):
            try:
                raw_cube = segyio.tools.cube(f)
                vol = np.ascontiguousarray(raw_cube, dtype=np.float32)
                self._downsampled = vol
                self._downsample_factor = factor
                if cancellation_token is not None:
                    cancellation_token.raise_if_cancelled()
                return vol
            except Exception as e:
                logger.debug("segyio.tools.cube fast path unavailable (%s); using strided trace read", e)

        il_indices = range(0, meta.n_inlines, fi)
        xl_indices = range(0, meta.n_crosslines, fx)
        t_indices = range(0, meta.n_samples, ft)
        vol = np.empty((len(il_indices), len(xl_indices), len(t_indices)), dtype=np.float32)
        for i, il_idx in enumerate(il_indices):
            if cancellation_token is not None:
                cancellation_token.raise_if_cancelled()
            il = int(f.ilines[il_idx])
            line = np.asarray(f.iline[il], dtype=np.float32)
            vol[i, :, :] = line[np.array(xl_indices)][:, np.array(t_indices)]
        self._downsampled = vol
        self._downsample_factor = factor
        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()
        return vol

    def close(self):
        """Close the underlying SEGY file handle."""
        if self._f is not None:
            self._f.close()
            self._f = None

    def _close_handle(self) -> None:
        if self._f is not None:
            try:
                self._f.close()
            except Exception:
                pass
            self._f = None

    def _open_detected(self, found_il: int, found_xl: int) -> segyio.SegyFile:
        self._close_handle()
        try:
            self._f = segyio.open(
                self._path, "r", strict=False, ignore_geometry=False,
                iline=int(found_il), xline=int(found_xl),
            )
        except Exception:
            self._f = segyio.open(self._path, "r", strict=False, ignore_geometry=True)
        self._geometry_source = "detected_headers"
        self._geometry_fields = (int(found_il), int(found_xl))
        return self._f

    def _open_unstructured(self, n_traces: int | None = None) -> segyio.SegyFile:
        self._close_handle()
        if n_traces is None:
            logger.warning("Could not auto-detect geometry. Falling back to unstructured mode.")
        else:
            logger.warning(
                "Could not auto-detect geometry. Falling back to unstructured mode (%d traces).",
                n_traces,
            )
        self._f = segyio.open(self._path, "r", strict=False, ignore_geometry=True)
        self._geometry_source = "pseudo"
        self._geometry_fields = None
        return self._f

    def _open(self) -> segyio.SegyFile:
        if self._f is not None:
            return self._f
        
        # 1) Try standard geometry (iline=189, xline=193)
        try:
            self._f = segyio.open(self._path, "r", strict=False, ignore_geometry=False)
            ilines = getattr(self._f, "ilines", None)
            xlines = getattr(self._f, "xlines", None)
            # Quick sanity check: if ilines/xlines are valid, we're done
            if (
                ilines is not None
                and xlines is not None
                and len(ilines) > 1
                and len(xlines) > 1
            ):
                self._geometry_source = "standard_189_193"
                self._geometry_fields = (
                    int(segyio.TraceField.INLINE_3D),
                    int(segyio.TraceField.CROSSLINE_3D),
                )
                return self._f
            self._close_handle()
        except Exception:
            self._close_handle()
        
        # 2) Auto-detect non-standard iline/xline header byte locations
        logger.info("Standard SEGY geometry failed for %s — scanning for alternative header fields...", self._path)
        cache_key = _geometry_cache_key(self._path)
        with _GEOMETRY_FIELD_CACHE_LOCK:
            cached = _GEOMETRY_FIELD_CACHE.get(cache_key, _MISSING)

        if cached is not _MISSING:
            if cached is None:
                return self._open_unstructured()
            return self._open_detected(cached[0], cached[1])

        self._f = segyio.open(self._path, "r", strict=False, ignore_geometry=True)
        n_traces = self._f.tracecount
        found = detect_iline_xline_fields(self._f)
        self._close_handle()

        with _GEOMETRY_FIELD_CACHE_LOCK:
            _GEOMETRY_FIELD_CACHE[cache_key] = found

        if found is not None:
            logger.info(
                "Detected geometry: iline=byte %d, xline=byte %d",
                int(found[0]), int(found[1]),
            )
            return self._open_detected(found[0], found[1])
        return self._open_unstructured(n_traces)

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False
