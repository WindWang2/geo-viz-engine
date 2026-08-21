"""SliceReadWorker: latest-wins queue, own loader, prefetch, generation guard."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_worker_reads_and_prefetches(qapp, small_segy_path, qtbot):
    from geoviz_seismic.workers import SliceReadWorker
    from geoviz_seismic.loader import SeismicLoader

    loader = SeismicLoader(str(small_segy_path))
    meta = loader.inspect()
    mid_il = meta.iline_start + (meta.n_inlines // 2) * meta.iline_step
    loader.close()

    worker = SliceReadWorker()
    results = []
    prefetches = []
    worker.slice_ready.connect(lambda *a: results.append(a))
    worker.prefetch_ready.connect(lambda *a: prefetches.append(a))
    worker.start()
    try:
        worker.set_volume(str(small_segy_path), 1)
        worker.request("inline", mid_il, 1)
        qtbot.waitUntil(lambda: len(results) == 1, timeout=10000)
        qtbot.waitUntil(lambda: len(prefetches) >= 2, timeout=10000)
    finally:
        worker.stop()

    stype, pos, data, gen = results[0]
    assert stype == "inline"
    assert pos == mid_il
    assert gen == 1
    assert isinstance(data, np.ndarray)
    assert data.shape == (meta.n_crosslines, meta.n_samples)
    # Prefetch positions are neighbours of mid_il within bounds
    pref_positions = {p[1] for p in prefetches}
    assert mid_il not in pref_positions
    assert all(abs(p - mid_il) <= 2 * meta.iline_step for p in pref_positions)


def test_worker_does_not_prefetch_timeslices(qapp, small_segy_path, qtbot):
    """Timeslice I/O is O(volume); prefetch would stall the Time slider."""
    from geoviz_seismic.workers import SliceReadWorker
    from geoviz_seismic.loader import SeismicLoader

    loader = SeismicLoader(str(small_segy_path))
    meta = loader.inspect()
    mid_t = meta.n_samples // 2
    loader.close()

    worker = SliceReadWorker()
    results = []
    prefetches = []
    worker.slice_ready.connect(lambda *a: results.append(a))
    worker.prefetch_ready.connect(lambda *a: prefetches.append(a))
    worker.start()
    try:
        worker.set_volume(str(small_segy_path), 1)
        worker.request("time", mid_t, 1)
        qtbot.waitUntil(lambda: len(results) == 1, timeout=10000)
        qtbot.wait(200)
    finally:
        worker.stop()

    assert results[0][0] == "time"
    assert prefetches == []


def test_worker_latest_wins(qapp, small_segy_path, qtbot):
    from geoviz_seismic.workers import SliceReadWorker
    from geoviz_seismic.loader import SeismicLoader

    loader = SeismicLoader(str(small_segy_path))
    meta = loader.inspect()
    il0 = meta.iline_start
    il1 = il0 + meta.iline_step
    il2 = il1 + meta.iline_step
    loader.close()

    worker = SliceReadWorker()
    results = []
    worker.slice_ready.connect(lambda *a: results.append(a))
    # Queue requests BEFORE starting the thread: older same-type ones are dropped
    worker.set_volume(str(small_segy_path), 1)
    worker.request("inline", il0, 1)
    worker.request("inline", il1, 1)
    worker.request("inline", il2, 1)
    worker.start()
    try:
        qtbot.waitUntil(lambda: len(results) >= 1, timeout=10000)
    finally:
        worker.stop()
    # Only the latest inline request survives
    assert [r[1] for r in results] == [il2]


def test_worker_stale_generation_dropped(qapp, small_segy_path, qtbot):
    from geoviz_seismic.workers import SliceReadWorker
    from geoviz_seismic.loader import SeismicLoader

    loader = SeismicLoader(str(small_segy_path))
    meta = loader.inspect()
    mid_il = meta.iline_start + (meta.n_inlines // 2) * meta.iline_step
    loader.close()

    worker = SliceReadWorker()
    results = []
    worker.slice_ready.connect(lambda *a: results.append(a))
    worker.set_volume(str(small_segy_path), 5)
    worker.request("inline", mid_il, 4)  # stale generation vs volume's 5
    worker.start()
    try:
        qtbot.wait(300)
    finally:
        worker.stop()
    assert results == []


def test_worker_stop_and_restart(qapp, small_segy_path, qtbot):
    from geoviz_seismic.workers import SliceReadWorker
    from geoviz_seismic.loader import SeismicLoader

    loader = SeismicLoader(str(small_segy_path))
    meta = loader.inspect()
    mid_il = meta.iline_start + (meta.n_inlines // 2) * meta.iline_step
    loader.close()

    worker = SliceReadWorker()
    worker.start()
    worker.set_volume(str(small_segy_path), 1)
    worker.stop()
    assert not worker.isRunning()

    results = []
    worker.slice_ready.connect(lambda *a: results.append(a))
    worker.ensure_running()
    worker.request("inline", mid_il, 1)
    try:
        qtbot.waitUntil(lambda: len(results) == 1, timeout=10000)
    finally:
        worker.stop()
    assert results[0][1] == mid_il
