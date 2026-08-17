"""Regression tests for SeismicView async guards and indexing fixes.

Covers:
- synthetic auto-load worker must not overwrite/cancel an in-flight SEGY load
- the attribute result cache is byte/slice bounded (LRU eviction)
- arbitrary-slice time axis honours t0_ms and the downsample factor
- current_seismic_trace fallback scales the preview-voxel XL index to the
  full-resolution inline slice grid
"""
from __future__ import annotations

import os
import subprocess
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtCore import QObject, Signal


def _seismic_view_constructible() -> bool:
    """Check if SeismicView can be constructed offscreen.

    Widget init can trigger a C-level X error when the display is
    unavailable, which Python try/except cannot catch.  Use a subprocess
    probe to avoid crashing the test process.
    """
    code = (
        "import os; os.environ.setdefault('QT_QPA_PLATFORM','offscreen'); "
        "from PySide6.QtWidgets import QApplication; "
        "app=QApplication([]); "
        "from geoviz_seismic.seismic_view import SeismicView; "
        "v=SeismicView(auto_load=False); "
        "v.cleanup(); "
        "print('OK')"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            timeout=60,
        )
        return result.returncode == 0 and b"OK" in result.stdout
    except Exception:
        return False


requires_seismic_view = pytest.mark.skipif(
    not _seismic_view_constructible(),
    reason="SeismicView not constructible in this environment",
)

pytestmark = requires_seismic_view


class _FakeSynthWorker(QObject):
    """Stand-in for SyntheticWorker (never actually runs a thread)."""

    done = Signal(object)

    def __init__(self):
        super().__init__()
        self.interrupted = False

    def isRunning(self):
        return True

    def requestInterruption(self):
        self.interrupted = True


class _FakeSegyWorker(QObject):
    """Stand-in for SegyLoadWorker: signals exist, thread never starts."""

    done = Signal(object)
    error = Signal(object)
    finished = Signal()

    def __init__(self, path, parent=None, *, generation=0, **kwargs):
        super().__init__()
        self.path = path
        self.generation = generation
        self.interrupted = False

    def start(self):
        pass

    def isRunning(self):
        return True

    def requestInterruption(self):
        self.interrupted = True


def _make_view(qtbot, monkeypatch):
    from geoviz_seismic.seismic_view import SeismicView
    import geoviz_seismic.seismic_view as view_module

    monkeypatch.setattr(view_module, "SegyLoadWorker", _FakeSegyWorker)
    monkeypatch.setattr(view_module, "retain_background_worker", lambda worker: None)
    view = SeismicView(auto_load=False)
    qtbot.addWidget(view)
    return view


def _make_meta(**overrides):
    from geoviz_seismic.models import SeismicVolumeMeta

    kwargs = dict(
        filename="test.sgy",
        n_inlines=10,
        n_crosslines=12,
        n_samples=40,
        sample_interval=2.0,
        iline_start=100,
        iline_step=1,
        xline_start=200,
        xline_step=1,
        dt_ms=2.0,
        t0_ms=500.0,
    )
    kwargs.update(overrides)
    return SeismicVolumeMeta(**kwargs)


# --- 1. Synthetic worker guard -------------------------------------------


def test_segy_load_invalidates_pending_synthetic_worker(qtbot, monkeypatch):
    """load_segy_async during auto-load must neutralize the synth worker."""
    view = _make_view(qtbot, monkeypatch)
    synth = _FakeSynthWorker()
    synth.done.connect(view._on_synthetic_ready)
    view._synth_worker = synth
    loaded = []
    monkeypatch.setattr(view, "load_demo", lambda data: loaded.append(data))

    view.load_segy_async("/tmp/fake.sgy")
    assert synth.interrupted
    assert view._synth_worker is None
    assert view._segy_path == "/tmp/fake.sgy"
    generation_after_request = view._segy_generation

    # A late synthetic result must neither reach the slot (disconnected) nor
    # cancel the in-flight SEGY load via load_demo -> cancel_pending_segy_load.
    synth.done.emit(np.zeros((2, 2, 2), dtype=np.float32))
    assert loaded == []
    assert view._segy_generation == generation_after_request
    assert view._segy_path == "/tmp/fake.sgy"
    assert view._segy_worker is not None
    assert not view._segy_worker.interrupted


def test_synthetic_ready_drops_superseded_worker_result(qtbot, monkeypatch):
    """Queued results from a superseded synth worker are discarded by sender."""
    view = _make_view(qtbot, monkeypatch)
    stale = _FakeSynthWorker()
    current = _FakeSynthWorker()
    stale.done.connect(view._on_synthetic_ready)
    current.done.connect(view._on_synthetic_ready)
    view._synth_worker = current
    loaded = []
    monkeypatch.setattr(view, "load_demo", lambda data: loaded.append(data))

    stale.done.emit(np.zeros((2, 2, 2), dtype=np.float32))
    assert loaded == []

    # The current worker's own result still loads normally.
    data = np.ones((3, 3, 3), dtype=np.float32)
    current.done.emit(data)
    assert len(loaded) == 1
    assert loaded[0] is data


# --- 2. Bounded attribute cache -------------------------------------------


def test_attr_cache_is_bounded_and_evicts_lru(qtbot, monkeypatch):
    """_attr_cache uses RamSliceCache; over-budget writes evict oldest entries."""
    from geoviz_seismic.cache import RamSliceCache
    from geoviz_seismic.workers import AttrComputeResult

    view = _make_view(qtbot, monkeypatch)
    assert isinstance(view._attr_cache, RamSliceCache)

    # Swap in a tiny budget so the regression is observable: 3 slices max.
    view._attr_cache = RamSliceCache(max_bytes=10 * 1024 * 1024, max_slices=3)
    view._segy_generation = 5

    def submit(position: int, generation: int):
        view._pending_attr["inline"] = generation
        result = AttrComputeResult(
            generation=generation,
            segy_generation=5,
            slice_type="inline",
            position=position,
            attr_idx=1,
            rgb_channels=None,
            display=np.zeros((4, 4), dtype=np.float32),
        )
        view._on_attr_computed(result)

    for pos, gen in ((10, 1), (11, 2), (12, 3)):
        submit(pos, gen)
    assert len(view._attr_cache) == 3

    # Fourth entry must evict the oldest (position 10); total stays bounded.
    submit(13, 4)
    assert len(view._attr_cache) == 3
    assert view._attr_cache.get((5, "inline", 10, 1, None)) is None
    assert view._attr_cache.get((5, "inline", 13, 1, None)) is not None

    # Byte budget is enforced too: an oversized write evicts older entries
    # and the total stays bounded.
    view._attr_cache = RamSliceCache(max_bytes=200, max_slices=50)
    view._pending_attr["inline"] = 5
    small = AttrComputeResult(
        generation=5,
        segy_generation=5,
        slice_type="inline",
        position=20,
        attr_idx=1,
        rgb_channels=None,
        display=np.zeros((4, 4), dtype=np.float32),  # 64 B
    )
    view._on_attr_computed(small)
    assert view._attr_cache.get((5, "inline", 20, 1, None)) is not None

    view._pending_attr["inline"] = 6
    big = AttrComputeResult(
        generation=6,
        segy_generation=5,
        slice_type="inline",
        position=21,
        attr_idx=1,
        rgb_channels=None,
        display=np.zeros((16, 16), dtype=np.float32),  # 1 KiB > 200 B budget
    )
    view._on_attr_computed(big)
    assert view._attr_cache.get((5, "inline", 20, 1, None)) is None
    assert len(view._attr_cache) == 1


# --- 3. Arbitrary-slice time axis ------------------------------------------


def test_arbitrary_slice_time_axis_includes_downsample_and_t0(qtbot, monkeypatch):
    """axis_v_values must be t0_ms + row * dt_ms * ds_factor[2]."""
    view = _make_view(qtbot, monkeypatch)
    view._meta = _make_meta(dt_ms=2.0, t0_ms=500.0)
    view._ds_factor = (1, 1, 4)

    captured = {}
    monkeypatch.setattr(
        view._profile_arb,
        "update_profile",
        lambda data, slice_info=None: captured.update(info=slice_info),
    )
    data = np.zeros((6, 9), dtype=np.float32)
    view._on_arbitrary_changed(data)

    info = captured["info"]
    assert info.axis_v_values == [500.0 + i * 8.0 for i in range(6)]
    assert info.axis_h_values == list(range(9))

    # Without downsampling the axis is t0 + row * dt (unchanged behaviour).
    view._ds_factor = (1, 1, 1)
    view._on_arbitrary_changed(data)
    info = captured["info"]
    assert info.axis_v_values == [500.0 + i * 2.0 for i in range(6)]


# --- 4. Trace fallback XL indexing -----------------------------------------


def test_current_seismic_trace_fallback_scales_xl_index(qtbot, monkeypatch):
    """Fallback branch: preview _xl_pos must map to the full-res XL grid."""
    view = _make_view(qtbot, monkeypatch)
    view._renderer_3d._volume_data_cpu = None  # skip in-memory branch
    view._meta = _make_meta()
    view._ds_factor = (1, 3, 1)

    class _FailingLoader:
        def read_trace(self, iline, xline):
            raise RuntimeError("no trace available")

    view._loader = _FailingLoader()

    # Full-resolution inline slice (n_t, n_xl): every column is its index.
    n_t, n_xl = 4, 12
    view._slice_data["inline"] = np.tile(
        np.arange(n_xl, dtype=np.float32), (n_t, 1)
    )
    view._renderer_3d._xl_pos = 2  # preview voxel 2 -> full-res XL 6

    trace = view.current_seismic_trace()
    assert trace is not None
    assert len(trace) == n_t
    assert np.all(trace == 6.0)

    # Clamping still applies after scaling (2 * 3 = 6 <= n_xl - 1; use a
    # position beyond the edge to exercise the clamp).
    view._renderer_3d._xl_pos = 10  # 10 * 3 = 30 -> clamped to 11
    trace = view.current_seismic_trace()
    assert np.all(trace == 11.0)


def test_current_seismic_trace_prefers_full_res_loader_dt(qtbot, monkeypatch):
    """#697: well-tie must use native dt/samples, not the preview volume."""
    view = _make_view(qtbot, monkeypatch)
    view._meta = _make_meta(dt_ms=2.0, sample_interval=2.0, n_samples=40)
    view._ds_factor = (2, 2, 2)
    view._renderer_3d._volume_data_cpu = np.ones((5, 6, 20), dtype=np.float32)
    view._renderer_3d._il_pos = 1
    view._renderer_3d._xl_pos = 2

    class _FullLoader:
        def read_trace(self, iline, xline):
            return np.full(40, float(iline) + float(xline) * 0.01, dtype=np.float64)

    view._loader = _FullLoader()
    trace = view.current_seismic_trace()
    assert trace is not None
    assert len(trace) == 40
    assert view.current_seismic_dt_ms() == 2.0
