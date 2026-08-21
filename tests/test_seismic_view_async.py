"""SeismicView async slice-read wiring and _on_jump consistency tests."""
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


class _FakeWorker(QObject):
    slice_ready = Signal(str, int, object, int)
    prefetch_ready = Signal(str, int, object, int)
    read_error = Signal(str, int, int)

    def __init__(self):
        super().__init__()
        self.requests = []
        self.volumes = []
        self.stopped = False
        self.started = False

    def start(self):
        self.started = True

    def set_volume(self, path, generation):
        self.volumes.append((path, generation))

    def request(self, slice_type, actual_pos, generation):
        self.requests.append((slice_type, actual_pos, generation))

    def stop(self):
        self.stopped = True

    def ensure_running(self):
        self.stopped = False


def _make_view(qtbot, monkeypatch) -> tuple:
    from geoviz_seismic.seismic_view import SeismicView
    import geoviz_seismic.seismic_view as view_module

    fake = _FakeWorker()
    monkeypatch.setattr(view_module, "SliceReadWorker", lambda *a, **k: fake)
    monkeypatch.setattr(view_module, "retain_background_worker", lambda worker: None)
    view = SeismicView(auto_load=False)
    qtbot.addWidget(view)
    return view, fake


def test_pending_slice_is_per_axis_dict(qtbot, monkeypatch):
    view, _ = _make_view(qtbot, monkeypatch)
    assert isinstance(view._pending_slice, dict)


def test_jump_refreshes_all_three_panels(qtbot, monkeypatch):
    view, _ = _make_view(qtbot, monkeypatch)
    # Simulate loaded demo volume
    vol = np.random.default_rng(1).random((10, 12, 14)).astype(np.float32)
    view._renderer_3d._volume_data_cpu = vol
    view._renderer_3d._loaded = True
    applied = []
    monkeypatch.setattr(
        view, "_update_profile_panel",
        lambda stype, pos, data: applied.append((stype, pos)),
    )
    view._on_jump(3, 5, 7)
    view._slice_timer.stop()
    view._apply_pending_slice()
    assert set(stype for stype, _ in applied) == {"inline", "crossline", "time"}


def test_cache_miss_requests_worker_instead_of_blocking(qtbot, monkeypatch):
    view, fake = _make_view(qtbot, monkeypatch)
    view._meta = type("M", (), {
        "iline_start": 100, "iline_step": 2,
        "xline_start": 200, "xline_step": 1,
    })()
    view._ds_factor = (1, 1, 1)
    view._loader = object()  # not None -> loader path
    view._segy_generation = 7
    view._pending_slice = {"inline": 4}
    view._apply_pending_slice()
    assert fake.requests == [("inline", 100 + 4 * 2, 7)]


def test_time_cache_miss_paints_preview_then_requests_worker(qtbot, monkeypatch):
    """2D Time panel should track the slider via the preview cube, not wait ~400ms."""
    view, fake = _make_view(qtbot, monkeypatch)
    view._meta = type("M", (), {
        "iline_start": 100, "iline_step": 1,
        "xline_start": 200, "xline_step": 1,
        "n_inlines": 10, "n_crosslines": 12, "n_samples": 20,
    })()
    view._ds_factor = (2, 2, 2)
    view._loader = object()
    view._segy_generation = 1
    vol = np.arange(5 * 6 * 10, dtype=np.float32).reshape(5, 6, 10)
    view._renderer_3d._volume_data_cpu = vol
    view._renderer_3d._loaded = True
    applied = []

    def _capture(stype, pos, data):
        applied.append((stype, pos, tuple(data.shape), float(data[0, 0])))

    monkeypatch.setattr(view, "_update_profile_panel", _capture)
    view._pending_slice = {"time": 4}
    view._apply_pending_slice()
    assert fake.requests == [("time", 8, 1)]
    assert applied[0][0] == "time"
    assert applied[0][1] == 8
    assert applied[0][2] == (12, 10)  # .T of cropped (nI, nX)
    # voxel (0,0,4) tiled by the (2,2) upsample
    assert applied[0][3] == pytest.approx(float(vol[0, 0, 4]))


def test_slice_ready_updates_panel_and_cache(qtbot, monkeypatch):
    view, fake = _make_view(qtbot, monkeypatch)
    view._meta = type("M", (), {
        "iline_start": 100, "iline_step": 2,
        "xline_start": 200, "xline_step": 1,
    })()
    view._ds_factor = (1, 1, 1)
    view._loader = object()
    view._segy_generation = 7
    applied = []
    monkeypatch.setattr(
        view, "_update_profile_panel",
        lambda stype, pos, data: applied.append((stype, pos)),
    )
    data = np.ones((5, 6), dtype=np.float32)
    view._on_slice_ready("inline", 108, data, 7)
    assert applied == [("inline", 108)]
    # Round-2 H10: cache keys are volume-scoped by the SEGY generation.
    assert view._cache.get((7, "inline", 108)) is data


def test_stale_generation_slice_ignored(qtbot, monkeypatch):
    view, fake = _make_view(qtbot, monkeypatch)
    view._segy_generation = 8
    applied = []
    monkeypatch.setattr(
        view, "_update_profile_panel",
        lambda stype, pos, data: applied.append((stype, pos)),
    )
    view._on_slice_ready("inline", 108, np.ones((2, 2), dtype=np.float32), 7)
    assert applied == []


def test_prefetch_only_fills_cache(qtbot, monkeypatch):
    view, _ = _make_view(qtbot, monkeypatch)
    view._segy_generation = 3
    applied = []
    monkeypatch.setattr(
        view, "_update_profile_panel",
        lambda stype, pos, data: applied.append((stype, pos)),
    )
    data = np.ones((4, 4), dtype=np.float32)
    view._on_prefetch_ready("time", 12, data, 3)
    assert applied == []
    assert view._cache.get((3, "time", 12)) is data


def test_worker_restarts_after_cleanup(qtbot, monkeypatch):
    view, fake = _make_view(qtbot, monkeypatch)
    # The slice worker must exist before cleanup can stop it (pre-existing
    # gap: the test never ensured the worker, so fake.stopped stayed False).
    view._ensure_slice_worker()
    # Simulate page-switch-away then back with a new SEGY
    view.cleanup()
    assert fake.stopped is True
    view._ensure_slice_worker()
    assert view._slice_worker_stopped is False
    assert fake.stopped is False


def test_stale_inflight_slice_does_not_update_panel(qtbot, monkeypatch):
    view, fake = _make_view(qtbot, monkeypatch)
    view._meta = type("M", (), {
        "iline_start": 100, "iline_step": 2,
        "xline_start": 200, "xline_step": 1,
    })()
    view._ds_factor = (1, 1, 1)
    view._loader = object()
    view._segy_generation = 7
    view._latest_slice_request = {"inline": 110}
    applied = []
    monkeypatch.setattr(
        view, "_update_profile_panel",
        lambda stype, pos, data: applied.append((stype, pos)),
    )
    import numpy as np
    # In-flight result for a superseded position: cached but panel not updated
    view._on_slice_ready("inline", 108, np.ones((2, 2), dtype=np.float32), 7)
    assert applied == []
    assert view._cache.get((7, "inline", 108)) is not None
    # Current position still updates
    view._on_slice_ready("inline", 110, np.ones((2, 2), dtype=np.float32), 7)
    assert applied == [("inline", 110)]
