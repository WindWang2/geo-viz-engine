"""Chunked slice worker: LOD-aware interactive reads over a zarr store (#1082).

The production interactive path for DERIVED chunked volumes, mirroring
:class:`workers.SliceReadWorker`'s contract (latest-wins queue, per-slice
signals, cooperative stop) but reading through
:class:`chunked.ChunkedVolumeReader` with the frame-budget
:class:`lod.LodPolicy`:

- every request is served at the policy's current LOD (coarsened while
  reads blow the frame budget);
- when browsing goes quiet for the idle window, the worker refines the
  current slices one level finer per window until lod0 (finer results
  overwrite the panel — no flicker);
- a :class:`lod.DirectionalPrefetcher` follows slider movement at the
  current LOD on the worker's own reader (zarr reads are thread-safe).

Positions are LOGICAL survey values (inline/crossline numbers, sample
index for time slices) per the #1080 coordinate contract.
"""
from __future__ import annotations

import time

from PySide6.QtCore import QMutex, QMutexLocker, QThread, QWaitCondition, Signal

from geoviz_seismic.lod import DirectionalPrefetcher, LodPolicy


class ChunkedSliceWorker(QThread):
    """Background LOD slice reader over one chunked store."""

    slice_ready = Signal(str, int, object, int)    # type, logical_pos, ndarray, generation
    prefetch_ready = Signal(str, int, object, int)
    read_error = Signal(str, int, int)
    lod_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mutex = QMutex()
        self._cond = QWaitCondition()
        self._requests: dict[str, tuple[int, int]] = {}  # slice_type -> (pos, generation)
        self._last_positions: dict[str, tuple[int, int]] = {}  # type -> (pos, generation)
        self._store_path: str | None = None
        self._store_generation = -1
        self._geometry = None
        self._stop = False
        self._reader = None
        self._reader_error: str | None = None
        self.policy = LodPolicy(max_lod=4)
        self._prefetcher: DirectionalPrefetcher | None = None

    # ------------------------------------------------------- GUI-thread API --
    def ensure_running(self) -> None:
        """Start the worker thread if it is not running (idempotent)."""
        if not self.isRunning():
            self.start()

    def set_store(self, store_path: str, generation: int, geometry=None) -> None:
        """Point the worker at a chunked store (opened lazily in-run)."""
        with QMutexLocker(self._mutex):
            self._store_path = str(store_path)
            self._store_generation = int(generation)
            self._geometry = geometry
            self._reader = None
            self._reader_error = None
            self._requests.clear()
            self._last_positions.clear()
            self.policy.reset()
        self.ensure_running()
        self._cond.wakeAll()

    def request(self, slice_type: str, logical_pos: int, generation: int) -> None:
        with QMutexLocker(self._mutex):
            self._requests[slice_type] = (int(logical_pos), int(generation))
        self.ensure_running()
        self._cond.wakeAll()

    def stop(self) -> None:
        with QMutexLocker(self._mutex):
            self._stop = True
        if self._prefetcher is not None:
            self._prefetcher.cancel()
        self.requestInterruption()
        self._cond.wakeAll()
        self.wait(1500)

    # ------------------------------------------------------------- worker --
    def _open_reader(self):
        """Open (once) the ChunkedVolumeReader in the worker thread."""
        from geoviz_seismic.chunked import ChunkedVolumeReader

        with QMutexLocker(self._mutex):
            if self._reader is not None or self._store_path is None:
                return self._reader
            path, geometry = self._store_path, self._geometry
        try:
            reader = ChunkedVolumeReader(path, geometry=geometry)
        except Exception as exc:  # unreadable store: report once, stay idle
            with QMutexLocker(self._mutex):
                self._reader_error = f"{type(exc).__name__}: {exc}"
            return None
        with QMutexLocker(self._mutex):
            self._reader = reader
        reader.attach_cache(None)
        self._prefetcher = DirectionalPrefetcher(
            self._prefetch_read, ahead=4, max_lod=reader.max_lod
        )
        return reader

    def _read_at(self, reader, slice_type: str, pos: int, lod: int):
        if slice_type == "inline":
            return reader.read_inline(pos, lod=lod)
        if slice_type == "crossline":
            return reader.read_crossline(pos, lod=lod)
        return reader.read_timeslice(pos, lod=lod)

    def _prefetch_read(self, pos: int, lod: int) -> None:
        """DirectionalPrefetcher callback: inline-only ahead reads."""
        reader = self._reader
        gen = self._store_generation
        if reader is None:
            return
        t = self._prefetch_type
        data = self._read_at(reader, t, pos, lod)
        self.prefetch_ready.emit(t, int(pos), data, int(gen))

    _prefetch_type: str = "inline"

    def run(self):  # pragma: no cover - threaded loop, exercised via tests
        while True:
            requests: dict[str, tuple[int, int]] | None = None
            with QMutexLocker(self._mutex):
                while True:
                    if self._stop:
                        return
                    if self._requests:
                        requests = dict(self._requests)
                        self._requests.clear()
                        break
                    self._cond.wait(self._mutex, 50)
                    if not self._requests:
                        requests = None  # timeout tick -> idle refinement pass
                        break
            if requests is None:
                self._idle_refine_pass()
                continue
            self._serve_requests(requests)

    def _serve_requests(self, requests: dict[str, tuple[int, int]]) -> None:
        reader = self._open_reader()
        if reader is None:
            for slice_type, (_, gen) in requests.items():
                self.read_error.emit(slice_type, -1, int(gen))
            return
        for slice_type, (pos, gen) in requests.items():
            if gen != self._store_generation:
                continue
            t0 = time.perf_counter()
            lod = self.policy.select_lod()
            try:
                data = self._read_at(reader, slice_type, pos, lod)
            except Exception:
                self.read_error.emit(slice_type, int(pos), int(gen))
                continue
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            self.policy.record_read(lod, elapsed_ms)
            self.lod_changed.emit(lod)
            with QMutexLocker(self._mutex):
                self._last_positions[slice_type] = (pos, gen)
                self._prefetch_type = slice_type
            self.slice_ready.emit(slice_type, int(pos), data, int(gen))
            if self._prefetcher is not None:
                self._prefetcher.update(pos, lod=lod)

    def _idle_refine_pass(self) -> None:
        with QMutexLocker(self._mutex):
            last = dict(self._last_positions)
            gen_now = self._store_generation
            has_store = self._store_path is not None
        if not has_store or self._reader is None or not last:
            return
        refined = self.policy.refine_step()
        if refined is None:
            return
        self.lod_changed.emit(refined)
        for slice_type, (pos, gen) in last.items():
            if gen != gen_now:
                continue
            try:
                data = self._read_at(self._reader, slice_type, pos, refined)
            except Exception:
                continue
            self.slice_ready.emit(slice_type, int(pos), data, int(gen))


class ArbitraryLineWorker(QThread):
    """One-shot full-resolution arbitrary-line gathers (L5).

    The 3-D curtain samples the downsampled PREVIEW volume; the arbitrary
    profile deserves full resolution. This worker reads
    ``ChunkedVolumeReader.read_arbitrary_line`` (one bounding-box window
    read + bilinear blend, #1080) on its own reader handle and emits the
    gather for the profile panel. Latest-request-wins: a new polyline
    replaces the pending read; cooperative stop on teardown.
    """

    arbitrary_ready = Signal(object, int)  # ndarray (n_points, n_samples), generation
    read_error = Signal(int)  # generation whose gather failed

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mutex = QMutex()
        self._cond = QWaitCondition()
        self._points: list[tuple[float, float]] | None = None
        self._store_path: str | None = None
        self._geometry = None
        self._generation = -1
        self._stop = False

    def set_store(self, store_path: str, generation: int, geometry=None) -> None:
        with QMutexLocker(self._mutex):
            self._store_path = str(store_path)
            self._geometry = geometry
            self._generation = int(generation)
            self._points = None
            self._cond.wakeAll()

    def request_line(self, points: list[tuple[float, float]]) -> None:
        """Request a gather along survey-space (inline, crossline) points."""
        with QMutexLocker(self._mutex):
            self._points = [(float(a), float(b)) for a, b in points]
            self._cond.wakeAll()

    def stop(self) -> None:
        """Cooperative stop: interrupt + wake + bounded wait (teardown safe).

        Mirrors :meth:`ChunkedSliceWorker.stop` — without the wait the thread
        can outlive the QThread wrapper and abort the process at destruction
        ("QThread: Destroyed while thread is still running").
        """
        self.requestInterruption()
        with QMutexLocker(self._mutex):
            self._stop = True
            self._cond.wakeAll()
        self.wait(1500)

    def run(self) -> None:  # noqa: D102 - QThread entry point
        while True:
            with QMutexLocker(self._mutex):
                # TIMED wait + interruption check: an untimed cond wait can
                # never observe requestInterruption, hanging teardown.
                while (
                    not self._stop
                    and not self.isInterruptionRequested()
                    and (self._points is None or self._store_path is None)
                ):
                    self._cond.wait(self._mutex, 50)
                if self._stop or self.isInterruptionRequested():
                    return
                points = self._points
                self._points = None
                store_path = self._store_path
                generation = self._generation
            try:
                from geoviz_seismic.chunked import open_volume

                reader = open_volume(store_path)
                data = reader.read_arbitrary_line(points, lod=0, interpolate=True)
            except Exception:
                # A failed gather must not die silently: the profile panel
                # holds the previous (stale) image otherwise. Emit the failed
                # generation so the consumer can drop/mark it.
                self.read_error.emit(int(generation))
                continue
            if data is not None and data.size:
                self.arbitrary_ready.emit(data, int(generation))
