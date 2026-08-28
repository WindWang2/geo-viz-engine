"""Unified volume access: one reader surface over Zarr v3 stores and SEG-Y (#1080).

``open_volume(path)`` returns a :class:`VolumeReader` regardless of the on-disk
format. Business code never learns whether the bytes come from a chunked
DERIVED store (the post-transcode production path) or a RAW SEG-Y file (the
browse-during-transcode fallback):

    vol = open_volume(path)
    sl  = vol.read_inline(1234, lod=2)      # logical inline VALUE at any level
    win = vol.read_voxel_window(0, 64, 0, 64, 0, 512)   # index-space, half-open
    ali = vol.read_arbitrary_line([(1200, 3000), (1250, 3100)], lod=1)

Coordinate contract (shared by both backends):

- ``read_inline``/``read_crossline`` take real inline/crossline VALUES from
  the survey grid (``geometry.iline_start`` + ``k * iline_step``). ``lod``
  never changes that: the caller keeps passing survey values and the reader
  maps ``value -> base index -> level index`` internally
  (``level_step = iline_step * 2**lod``).
- ``read_timeslice`` takes a zero-based SAMPLE index (axis order of the
  stored volume, no time-coordinate interpolation).
- ``read_voxel_window(il0, il1, xl0, xl1, t0, t1, *, lod)`` is the
  attribute/AI/horizon primitive: half-open BASE-INDEX bounds. Backends must
  satisfy it with chunk-coverage batch reads (one store slice), never
  point-wise loops.
- ``read_arbitrary_line(points, *, lod, interpolate=True)`` gathers traces
  along a polyline of (inline, xline) VALUE points by reading the bounding
  box once and interpolating in memory — not one random IO per point.

The SEG-Y backend implements the same contract on top of
:class:`geoviz_seismic.loader.SeismicLoader`; its ``lod`` decimates a
full-resolution slice after reading (display semantics identical to the
pre-#1080 viewer fallback). It is the compatibility/degraded path — the
chunked backend is the production one.
"""
from __future__ import annotations

import json
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import numpy as np

# ------------------------------------------------------------------------ #
# Geometry
# ------------------------------------------------------------------------ #


@dataclass(frozen=True)
class VolumeGeometry:
    """Regular survey grid the reader maps values through.

    ``source`` records where the grid came from: ``"store"`` (zarr
    attributes written by the transcoder), ``"headers"`` (SEG-Y trace
    headers) or ``"assumed"`` (1-based unit-step fallback for legacy
    prototype stores — coordinates are then index+1).
    """

    shape: tuple[int, int, int]
    iline_start: int = 1
    iline_step: int = 1
    xline_start: int = 1
    xline_step: int = 1
    source: str = "assumed"

    @property
    def iline_stop(self) -> int:  # exclusive, in value space
        return self.iline_start + self.shape[0] * self.iline_step

    @property
    def xline_stop(self) -> int:
        return self.xline_start + self.shape[1] * self.xline_step

    def iline_to_index(self, iline: int) -> int:
        """Nearest base-grid index for a logical inline value (validated)."""
        return _value_to_index(int(iline), self.iline_start, self.iline_step, self.shape[0], "inline")

    def xline_to_index(self, xline: int) -> int:
        return _value_to_index(int(xline), self.xline_start, self.xline_step, self.shape[1], "xline")


def _value_to_index(value: int, start: int, step: int, n: int, what: str) -> int:
    if step <= 0 or n <= 0:
        raise IndexError(f"{what} grid is degenerate (start={start}, step={step}, n={n})")
    k = round((value - start) / step)
    if k < 0 or k >= n:
        lo, hi = start, start + (n - 1) * step
        raise IndexError(f"{what} {value} outside survey [{lo}, {hi}]")
    return k


# ------------------------------------------------------------------------ #
# Reader contract
# ------------------------------------------------------------------------ #


def _slice_key(volume_id: str, slice_type: str, position: int, lod: int):
    try:
        from geoviz_seismic.cache import SliceCacheKey

        return SliceCacheKey(
            volume_id=volume_id,
            slice_type=slice_type,
            position=int(position),
            downsample_factor=(2**lod, 2**lod, 2**lod),
        )
    except Exception:
        return (volume_id, slice_type, int(position), 2**lod)


class VolumeReader(ABC):
    """Common read surface implemented by every backend (#1080)."""

    STRATEGIES = ("stride", "mean", "maxabs")

    def __init__(
        self,
        geometry: VolumeGeometry,
        *,
        volume_id: str,
        lod_strategy: str = "stride",
        max_lod: int = 4,
    ):
        if lod_strategy not in self.STRATEGIES:
            raise ValueError(f"lod_strategy must be one of {self.STRATEGIES}, got {lod_strategy!r}")
        self.geometry = geometry
        self.volume_id = volume_id
        self.lod_strategy = lod_strategy
        self.max_lod = max_lod
        self._cache: Any = _NullCache()
        self._lock = threading.RLock()

    # -- cache ------------------------------------------------------- #
    def attach_cache(self, cache: Any) -> None:
        """Plug in the production ``RamSliceCache`` (L1)."""
        self._cache = cache if cache is not None else _NullCache()

    def _cached_plane(self, slice_type: str, logical_position: int, lod: int, fetch: Callable[[], np.ndarray]):
        key = _slice_key(self.volume_id, slice_type, logical_position, lod)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        arr = fetch()
        self._cache.put(key, arr)
        return arr

    # -- meta -------------------------------------------------------- #
    @property
    def shape(self) -> tuple[int, int, int]:
        return self.geometry.shape

    # -- coordinate helpers ------------------------------------------ #
    def _level_index(self, base_index: int, lod: int, axis_len: int) -> int:
        idx = base_index >> lod
        if idx >= axis_len >> lod and idx >= (axis_len + (1 << lod) - 1) // (1 << lod):
            idx = min(idx, ((axis_len + (1 << lod) - 1) // (1 << lod)) - 1)
        return idx

    def _level_step(self, step: int, lod: int) -> int:
        return step * (2**lod)

    # -- required reads ---------------------------------------------- #
    @abstractmethod
    def read_inline(self, iline: int, *, lod: int = 0) -> np.ndarray:
        """``(n_xlines, n_samples)`` plane for a logical inline value."""

    @abstractmethod
    def read_crossline(self, xline: int, *, lod: int = 0) -> np.ndarray:
        """``(n_inlines, n_samples)`` plane for a logical crossline value."""

    @abstractmethod
    def read_timeslice(self, sample_idx: int, *, lod: int = 0) -> np.ndarray:
        """``(n_inlines, n_xlines)`` plane for a zero-based sample index."""

    @abstractmethod
    def read_trace(self, iline: int, xline: int, *, lod: int = 0) -> np.ndarray:
        """``(n_samples,)`` trace at a logical (inline, xline)."""

    @abstractmethod
    def read_voxel_window(
        self,
        il0: int,
        il1: int,
        xl0: int,
        xl1: int,
        t0: int,
        t1: int,
        *,
        lod: int = 0,
    ) -> np.ndarray:
        """Half-open BASE-index window ``[il0:il1, xl0:xl1, t0:t1]``.

        Batch: one chunk-coverage read per call, never per point/line.
        Returns an array of shape ``ceil spans / 2**lod`` per axis (stride
        semantics at lod>0).
        """

    @abstractmethod
    def read_arbitrary_line(
        self,
        points: Sequence[tuple[float, float]],
        *,
        lod: int = 0,
        interpolate: bool = True,
    ) -> np.ndarray:
        """``(n_points, n_samples_at_lod)`` gather along (inline, xline) values.

        Nearest trace when ``interpolate=False``; display-grade bilinear
        blend of the 4 surrounding traces otherwise. Implemented as one
        bounding-box read + in-memory interpolation (#1080: no per-point
        random IO on the chunked path).
        """

    # -- shared LOD decimation ---------------------------------------- #
    def _decimate_axis0_pair(self, arr: np.ndarray) -> np.ndarray:
        """Halve the LAST TWO axes of a 2-D plane (xline, samples)."""
        return _decimate2(arr, self.lod_strategy)


def _decimate2(arr: np.ndarray, strategy: str) -> np.ndarray:
    h, w = arr.shape
    h2, w2 = h // 2, w // 2
    if h2 == 0 or w2 == 0:
        return np.asarray(arr, dtype=np.float32)
    a = np.asarray(arr[: h2 * 2, : w2 * 2], dtype=np.float32)
    if strategy == "stride":
        return a[::2, ::2].copy()
    if strategy == "mean":
        return a.reshape(h2, 2, w2, 2).mean(axis=(1, 3))
    if strategy == "maxabs":
        b = a.reshape(h2, 2, w2, 2).reshape(h2, w2, 4)
        idx = np.abs(b).argmax(axis=-1)
        return np.take_along_axis(b, idx[..., None], axis=-1)[..., 0]
    raise ValueError(f"unknown LOD strategy {strategy!r}")


def _decimate3_stride(arr: np.ndarray) -> np.ndarray:
    """Stride-halve a 3-D block on every axis (SEG-Y window fallback)."""
    n0, n1, n2 = arr.shape
    n0, n1, n2 = n0 // 2, n1 // 2, n2 // 2
    if n0 == 0 or n1 == 0 or n2 == 0:
        return np.asarray(arr, dtype=np.float32)
    return np.asarray(arr[: n0 * 2, : n1 * 2, : n2 * 2], dtype=np.float32)[
        ::2, ::2, ::2
    ].copy()


class _NullCache:
    def get(self, key):
        return None

    def put(self, key, arr):
        return None


# ------------------------------------------------------------------------ #
# Chunked (Zarr v3) backend
# ------------------------------------------------------------------------ #


class ChunkedVolumeReader(VolumeReader):
    """Zarr v3 store reader with a lazy cascade LOD pyramid.

    Levels are sibling arrays ``<store>_l{n}`` built from the previous level
    (never touching the base store). ``ensure_lod``/``build_lod`` are the
    scheduler entry points; a read at a missing level builds it lazily under
    ``_lod_lock`` so concurrent readers never duplicate work.
    """

    def __init__(
        self,
        store_path: str | Path,
        *,
        lod_strategy: str = "stride",
        max_lod: int = 4,
        geometry: VolumeGeometry | None = None,
    ):
        import zarr

        self.path = str(store_path)
        self._zarr_mod = zarr
        self._base = zarr.open(self.path, mode="r")
        shape = tuple(int(x) for x in self._base.shape)
        if geometry is None:
            geometry = self.geometry_from_store(self.path, shape)
        super().__init__(
            geometry,
            volume_id=self.path,
            lod_strategy=lod_strategy,
            max_lod=max_lod,
        )
        self._levels: dict[int, Any] = {0: self._base}
        self.lod_build_seconds: dict[int, float] = {}
        self._lod_lock = threading.RLock()

    # ------------------------------------------------------------ meta --
    @staticmethod
    def geometry_from_store(store_path: str | Path, shape: tuple[int, int, int]) -> VolumeGeometry:
        """Grid from the store's ``zarr.json`` attributes (transcoder-written).

        Falls back to the assumed 1-based unit-step grid when the attributes
        are absent (legacy/prototype stores); ``geometry.source`` records
        which happened so callers can rebind via :meth:`attach_geometry`.
        """
        meta_path = Path(store_path) / "zarr.json"
        try:
            doc = json.loads(meta_path.read_text())
        except (OSError, ValueError):
            return VolumeGeometry(shape=shape)
        attrs = doc.get("attributes") or {}
        il = attrs.get("iline") or {}
        xl = attrs.get("xline") or {}

        def _axis(spec: dict, n: int) -> tuple[int, int]:
            start, step = spec.get("start"), spec.get("step")
            if not isinstance(start, int) or not isinstance(step, int) or step <= 0:
                return 1, 1
            return start, step

        return VolumeGeometry(
            shape=shape,
            iline_start=_axis(il, shape[0])[0],
            iline_step=_axis(il, shape[0])[1],
            xline_start=_axis(xl, shape[1])[0],
            xline_step=_axis(xl, shape[1])[1],
            source="store" if il else "assumed",
        )

    def attach_geometry(self, geometry: VolumeGeometry) -> None:
        """Override the assumed grid (e.g. from the catalog's survey binding)."""
        with self._lock:
            self.geometry = geometry

    # ------------------------------------------------------------- LOD --
    def _decimate3(self, arr: np.ndarray) -> np.ndarray:
        ni, nx, nt = arr.shape
        ni2, nx2, nt2 = ni // 2, nx // 2, nt // 2
        if ni2 == 0 or nx2 == 0 or nt2 == 0:
            return np.asarray(arr, dtype=np.float32)
        a = np.asarray(arr[: ni2 * 2, : nx2 * 2, : nt2 * 2], dtype=np.float32)
        s = self.lod_strategy
        if s == "stride":
            return a[::2, ::2, ::2].copy()
        if s == "mean":
            return a.reshape(ni2, 2, nx2, 2, nt2, 2).mean(axis=(1, 3, 5))
        if s == "maxabs":
            b = a.reshape(ni2, 2, nx2, 2, nt2, 2).reshape(ni2, nx2, nt2, 8)
            idx = np.abs(b).argmax(axis=-1)
            return np.take_along_axis(b, idx[..., None], axis=-1)[..., 0]
        raise ValueError(f"unknown LOD strategy {s!r}")

    def _level_shape(self, lod: int) -> tuple[int, int, int]:
        n = self.geometry.shape
        f = 2**lod
        return tuple((x + f - 1) // f for x in n)  # type: ignore[return-value]

    def _level_path(self, lod: int) -> str:
        """Sibling store for level ``lod``; strategy is part of the name so
        readers with different decimation strategies never reuse each
        other's levels (they are NOT interchangeable data)."""
        if self.lod_strategy == "stride":
            return f"{self.path}_l{lod}"
        return f"{self.path}_l{lod}_{self.lod_strategy}"

    def _validate_level_store(self, path: str, lod: int) -> bool:
        meta = Path(path) / "zarr.json"
        if not meta.exists():
            return False
        try:
            doc = json.loads(meta.read_text())
            return list(doc.get("shape", [])) == list(self._level_shape(lod))
        except Exception:
            return False

    def build_lod(self, lod: int, *, progress: Callable[[float], None] | None = None) -> float:
        """Build level ``lod`` (from ``lod-1``) if missing; returns seconds."""
        if lod == 0:
            return 0.0
        if lod > self.max_lod:
            raise ValueError(f"lod={lod} exceeds max_lod={self.max_lod}")
        with self._lod_lock:
            if lod in self._levels:
                return 0.0
            out_path = self._level_path(lod)
            if not self._validate_level_store(out_path, lod):
                from zarr.codecs import BloscCodec

                lower = self._level(lod - 1)
                src_shape = tuple(int(x) for x in lower.shape)
                dst_shape = tuple(x // 2 for x in src_shape)
                t0 = time.perf_counter()
                dst = self._zarr_mod.create_array(
                    out_path,
                    shape=dst_shape,
                    dtype="float32",
                    chunks=(64, 128, 128),
                    shards=(128, 512, 512),
                    compressors=[BloscCodec(cname="zstd", clevel=5, shuffle="shuffle")],
                    overwrite=True,
                    attributes={
                        "lod_strategy": self.lod_strategy,
                        "base_store": self.path,
                    },
                )
                n0 = dst_shape[0]
                done = 0
                for i0 in range(0, n0, 64):
                    i1 = min(i0 + 64, n0)
                    dst[i0:i1, :, :] = self._decimate3(
                        np.asarray(lower[i0 * 2 : i1 * 2, :, :])
                    )
                    done = i1
                    if progress is not None:
                        progress(done / max(n0, 1))
                self.lod_build_seconds[lod] = time.perf_counter() - t0
            self._levels[lod] = self._zarr_mod.open(out_path, mode="r")
            return self.lod_build_seconds.get(lod, 0.0)

    def ensure_lods(self, max_lod: int) -> None:
        for lod in range(1, max_lod + 1):
            self.build_lod(lod)

    def _level(self, lod: int):
        if lod in self._levels:
            return self._levels[lod]
        self.build_lod(lod)
        return self._levels[lod]

    def has_lod(self, lod: int) -> bool:
        return lod in self._levels or self._validate_level_store(
            self._level_path(lod), lod
        )

    # ---------------------------------------------------------- reads --
    def read_inline(self, iline: int, *, lod: int = 0) -> np.ndarray:
        base_i = self.geometry.iline_to_index(iline)
        lvl = self._level(lod)
        lvl_i = self._level_index(base_i, lod, self.geometry.shape[0])
        return self._cached_plane(
            "inline", int(iline), lod, lambda: np.asarray(lvl[lvl_i, :, :])
        )

    def read_crossline(self, xline: int, *, lod: int = 0) -> np.ndarray:
        base_j = self.geometry.xline_to_index(xline)
        lvl = self._level(lod)
        lvl_j = self._level_index(base_j, lod, self.geometry.shape[1])
        return self._cached_plane(
            "crossline", int(xline), lod, lambda: np.asarray(lvl[:, lvl_j, :])
        )

    def read_timeslice(self, sample_idx: int, *, lod: int = 0) -> np.ndarray:
        nt = self.geometry.shape[2]
        k = int(sample_idx)
        if not 0 <= k < nt:
            raise IndexError(f"sample {k} outside [0, {nt})")
        lvl = self._level(lod)
        lvl_k = self._level_index(k, lod, nt)
        return self._cached_plane(
            "timeslice", k, lod, lambda: np.asarray(lvl[:, :, lvl_k])
        )

    def read_trace(self, iline: int, xline: int, *, lod: int = 0) -> np.ndarray:
        lvl = self._level(lod)
        i = self._level_index(self.geometry.iline_to_index(iline), lod, self.geometry.shape[0])
        j = self._level_index(self.geometry.xline_to_index(xline), lod, self.geometry.shape[1])
        return np.asarray(lvl[i, j, :])

    def read_voxel_window(
        self, il0, il1, xl0, xl1, t0, t1, *, lod: int = 0
    ) -> np.ndarray:
        n = self.geometry.shape
        il0, il1 = max(0, int(il0)), min(n[0], int(il1))
        xl0, xl1 = max(0, int(xl0)), min(n[1], int(xl1))
        t0, t1 = max(0, int(t0)), min(n[2], int(t1))
        if il1 <= il0 or xl1 <= xl0 or t1 <= t0:
            raise ValueError(
                f"empty window [{il0}:{il1}, {xl0}:{xl1}, {t0}:{t1}]"
            )
        if lod == 0:
            # One zarr slice == one chunk-coverage batch read.
            return np.asarray(self._base[il0:il1, xl0:xl1, t0:t1])
        f = 2**lod
        lvl = self._level(lod)
        li0, li1 = il0 // f + (1 if il0 % f else 0), (il1 + f - 1) // f
        lj0, lj1 = xl0 // f + (1 if xl0 % f else 0), (xl1 + f - 1) // f
        lk0, lk1 = t0 // f + (1 if t0 % f else 0), (t1 + f - 1) // f
        li1, lj1, lk1 = min(li1, lvl.shape[0]), min(lj1, lvl.shape[1]), min(lk1, lvl.shape[2])
        block = np.asarray(lvl[li0:li1, lj0:lj1, lk0:lk1])
        # Align back to the requested base-index bounds (stride semantics).
        bi = (li0 * f - il0) // f
        bj = (lj0 * f - xl0) // f
        bk = (lk0 * f - t0) // f
        return block[
            max(0, bi) : bi + (il1 - il0 + f - 1) // f,
            max(0, bj) : bj + (xl1 - xl0 + f - 1) // f,
            max(0, bk) : bk + (t1 - t0 + f - 1) // f,
        ]

    # Box budget: beyond this, a polyline's bounding box is not worth one
    # batched read and the gather degrades to per-trace reads (~4 per point).
    _BOX_READ_BUDGET_BYTES = 2 * 1024**3

    def read_arbitrary_line(
        self, points, *, lod: int = 0, interpolate: bool = True
    ) -> np.ndarray:
        pts = np.asarray(points, dtype=np.float64)
        if pts.ndim != 2 or pts.shape[1] != 2 or len(pts) == 0:
            raise ValueError("points must be an (n, 2) array of (inline, xline) values")
        g = self.geometry
        lvl = self._level(lod)
        f = 2**lod
        fi = (pts[:, 0] - g.iline_start) / (g.iline_step * f)
        fj = (pts[:, 1] - g.xline_start) / (g.xline_step * f)
        n_lvl = (int(lvl.shape[0]), int(lvl.shape[1]))
        if not interpolate:
            ii = np.rint(fi).astype(int)
            jj = np.rint(fj).astype(int)
            self._assert_level_in_range(ii, jj, n_lvl)
            return self._gather_traces(lvl, ii, jj)
        i0 = max(0, int(np.floor(fi.min())))
        i1 = min(n_lvl[0] - 1, int(np.ceil(fi.max())) + 1)
        j0 = max(0, int(np.floor(fj.min())))
        j1 = min(n_lvl[1] - 1, int(np.ceil(fj.max())) + 1)
        nt_lvl = int(lvl.shape[2])
        box_bytes = (i1 - i0 + 1) * (j1 - j0 + 1) * nt_lvl * 4
        if box_bytes > self._BOX_READ_BUDGET_BYTES:
            # Thin diagonal across the whole survey: per-point gather is
            # cheaper than materialising the bounding box.
            ii = np.clip(np.floor(fi).astype(int), 0, n_lvl[0] - 2)
            jj = np.clip(np.floor(fj).astype(int), 0, n_lvl[1] - 2)
            return self._bilinear_from_traces(lvl, fi, fj, ii, jj)
        box = np.asarray(lvl[i0 : i1 + 1, j0 : j1 + 1, :])
        ri = np.clip(fi - i0, 0, box.shape[0] - 1.001)
        rj = np.clip(fj - j0, 0, box.shape[1] - 1.001)
        i_lo = np.floor(ri).astype(int)
        j_lo = np.floor(rj).astype(int)
        di = (ri - i_lo)[:, None]
        dj = (rj - j_lo)[:, None]
        t00 = box[i_lo, j_lo, :]
        t01 = box[i_lo, j_lo + 1, :]
        t10 = box[i_lo + 1, j_lo, :]
        t11 = box[i_lo + 1, j_lo + 1, :]
        return (
            (t00 * (1 - dj) + t01 * dj) * (1 - di)
            + (t10 * (1 - dj) + t11 * dj) * di
        ).astype(np.float32)

    def _assert_level_in_range(self, ii: np.ndarray, jj: np.ndarray, n_lvl) -> None:
        if (ii < 0).any() or (ii >= n_lvl[0]).any():
            bad = int(ii[(ii < 0) | (ii >= n_lvl[0])][0])
            raise IndexError(f"arbitrary-line inline maps outside the survey (level index {bad})")
        if (jj < 0).any() or (jj >= n_lvl[1]).any():
            bad = int(jj[(jj < 0) | (jj >= n_lvl[1])][0])
            raise IndexError(f"arbitrary-line xline maps outside the survey (level index {bad})")

    def _gather_traces(self, lvl, ii: np.ndarray, jj: np.ndarray) -> np.ndarray:
        """Point-paired trace gather in ONE coordinate selection (batched
        chunk reads under the hood; no per-point store round-trips)."""
        nt = int(lvl.shape[2])
        kk = np.broadcast_to(np.arange(nt), (len(ii), nt)).ravel()
        coords = (np.repeat(ii, nt), np.repeat(jj, nt), kk)
        return np.asarray(lvl.vindex[coords]).reshape(len(ii), nt)

    def _bilinear_from_traces(self, lvl, fi, fj, ii, jj) -> np.ndarray:
        di = (fi - ii)[:, None]
        dj = (fj - jj)[:, None]
        t00 = self._gather_traces(lvl, ii, jj)
        t01 = self._gather_traces(lvl, ii, jj + 1)
        t10 = self._gather_traces(lvl, ii + 1, jj)
        t11 = self._gather_traces(lvl, ii + 1, jj + 1)
        return (
            (t00 * (1 - dj) + t01 * dj) * (1 - di)
            + (t10 * (1 - dj) + t11 * dj) * di
        ).astype(np.float32)


# ------------------------------------------------------------------------ #
# SEG-Y fallback backend
# ------------------------------------------------------------------------ #


class SegyVolumeReader(VolumeReader):
    """Same contract over RAW SEG-Y via :class:`SeismicLoader` (degraded path).

    ``lod`` decimates after a full-resolution read (the viewer's historical
    fallback semantics). Windows and arbitrary lines assemble from inline
    reads — segyio has no box read; the chunked backend is the production
    path, this one exists so browsing works before the transcode finishes
    (#1079 browse-during-transcode).
    """

    def __init__(self, path: str | Path, *, lod_strategy: str = "stride", max_lod: int = 4):
        from geoviz_seismic.loader import SeismicLoader

        self._loader = SeismicLoader(str(path))
        meta = self._loader.inspect()
        geometry = VolumeGeometry(
            shape=(meta.n_inlines, meta.n_crosslines, meta.n_samples),
            iline_start=meta.iline_start,
            iline_step=max(1, meta.iline_step),
            xline_start=meta.xline_start,
            xline_step=max(1, meta.xline_step),
            source="headers",
        )
        super().__init__(
            geometry,
            volume_id=str(path),
            lod_strategy=lod_strategy,
            max_lod=max_lod,
        )

    @property
    def loader(self):
        return self._loader

    def _plane_at_lod(self, arr: np.ndarray, lod: int) -> np.ndarray:
        for _ in range(lod):
            arr = _decimate2(arr, self.lod_strategy)
        return arr

    def _il_value(self, base_index: int) -> int:
        return self.geometry.iline_start + int(base_index) * self.geometry.iline_step

    def _xl_value(self, base_index: int) -> int:
        return self.geometry.xline_start + int(base_index) * self.geometry.xline_step

    def read_inline(self, iline: int, *, lod: int = 0) -> np.ndarray:
        self.geometry.iline_to_index(iline)  # range validation
        return self._cached_plane(
            "inline", int(iline), lod,
            lambda: self._plane_at_lod(self._loader.read_inline(int(iline)), lod),
        )

    def read_crossline(self, xline: int, *, lod: int = 0) -> np.ndarray:
        self.geometry.xline_to_index(xline)
        return self._cached_plane(
            "crossline", int(xline), lod,
            lambda: self._plane_at_lod(self._loader.read_crossline(int(xline)), lod),
        )

    def read_timeslice(self, sample_idx: int, *, lod: int = 0) -> np.ndarray:
        k = int(sample_idx)
        if not 0 <= k < self.geometry.shape[2]:
            raise IndexError(f"sample {k} outside [0, {self.geometry.shape[2]})")
        return self._cached_plane(
            "timeslice", k, lod,
            lambda: self._plane_at_lod(self._loader.read_timeslice(k), lod),
        )

    def read_trace(self, iline: int, xline: int, *, lod: int = 0) -> np.ndarray:
        self.geometry.iline_to_index(iline)
        self.geometry.xline_to_index(xline)
        arr = self._loader.read_trace(int(iline), int(xline))
        return arr[:: 2**lod].copy() if lod else arr

    def read_voxel_window(
        self, il0, il1, xl0, xl1, t0, t1, *, lod: int = 0
    ) -> np.ndarray:
        n = self.geometry.shape
        il0, il1 = max(0, int(il0)), min(n[0], int(il1))
        xl0, xl1 = max(0, int(xl0)), min(n[1], int(xl1))
        t0, t1 = max(0, int(t0)), min(n[2], int(t1))
        if il1 <= il0 or xl1 <= xl0 or t1 <= t0:
            raise ValueError(f"empty window [{il0}:{il1}, {xl0}:{xl1}, {t0}:{t1}]")
        planes = [
            self._loader.read_inline(self._il_value(i))[xl0:xl1, t0:t1]
            for i in range(il0, il1)
        ]
        block = np.stack(planes)
        for _ in range(lod):
            block = _decimate3_stride(block)
        return block

    def read_arbitrary_line(
        self, points, *, lod: int = 0, interpolate: bool = True
    ) -> np.ndarray:
        pts = np.asarray(points, dtype=np.float64)
        if pts.ndim != 2 or pts.shape[1] != 2 or len(pts) == 0:
            raise ValueError("points must be an (n, 2) array of (inline, xline) values")
        g = self.geometry
        f = 2**lod
        fi_all = (pts[:, 0] - g.iline_start) / g.iline_step
        fj_all = (pts[:, 1] - g.xline_start) / g.xline_step
        i_span = max(1, int(np.ceil(fi_all.max())) - int(np.floor(fi_all.min())) + 1)
        if interpolate and i_span <= 256:
            i0 = max(0, int(np.floor(fi_all.min())))
            i1 = min(g.shape[0], i0 + i_span)
            box = np.stack(
                [self._loader.read_inline(self._il_value(i)) for i in range(i0, i1)]
            )  # (n_il_span, n_xl, nt)
            ri = np.clip(fi_all - i0, 0, box.shape[0] - 1.001)
            rj = np.clip(fj_all, 0, box.shape[1] - 1.001)
            i_lo = np.floor(ri).astype(int)
            j_lo = np.floor(rj).astype(int)
            di = (ri - i_lo)[:, None]
            dj = (rj - j_lo)[:, None]
            t00, t01 = box[i_lo, j_lo, :], box[i_lo, j_lo + 1, :]
            t10, t11 = box[i_lo + 1, j_lo, :], box[i_lo + 1, j_lo + 1, :]
            out = (t00 * (1 - dj) + t01 * dj) * (1 - di) + (
                t10 * (1 - dj) + t11 * dj
            ) * di
            out = out.astype(np.float32)
            return out[:, ::f].copy() if lod else out
        ii = np.rint(fi_all / f).astype(int)
        jj = np.rint(fj_all / f).astype(int)
        if (ii < 0).any() or (ii * f >= g.shape[0]).any():
            raise IndexError("arbitrary-line inline outside the survey")
        if (jj < 0).any() or (jj * f >= g.shape[1]).any():
            raise IndexError("arbitrary-line xline outside the survey")
        traces = np.stack(
            [
                self._loader.read_trace(
                    self._il_value(min(i * f, g.shape[0] - 1)),
                    self._xl_value(min(j * f, g.shape[1] - 1)),
                )
                for i, j in zip(ii, jj)
            ]
        )
        return traces[:, ::f].copy() if lod else traces


# ------------------------------------------------------------------------ #
# Factory
# ------------------------------------------------------------------------ #


def looks_like_zarr_store(path: str | Path) -> bool:
    p = Path(path)
    return p.is_dir() and (p / "zarr.json").exists()


def open_volume(
    path: str | Path,
    *,
    lod_strategy: str = "stride",
    max_lod: int = 4,
    geometry: VolumeGeometry | None = None,
) -> VolumeReader:
    """Open a seismic volume behind the unified reader surface (#1080).

    - directory containing ``zarr.json`` → :class:`ChunkedVolumeReader`
    - ``.sgy`` / ``.segy`` file → :class:`SegyVolumeReader`
    """
    p = Path(path)
    if looks_like_zarr_store(p):
        return ChunkedVolumeReader(
            p, lod_strategy=lod_strategy, max_lod=max_lod, geometry=geometry
        )
    if p.suffix.lower() in {".sgy", ".segy"} or p.exists():
        return SegyVolumeReader(p, lod_strategy=lod_strategy, max_lod=max_lod)
    raise FileNotFoundError(f"no seismic volume at {p}")
