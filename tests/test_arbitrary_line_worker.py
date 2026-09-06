"""ArbitraryLineWorker protocol contract (thread safety, latest-wins, stop)."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("PySide6")

from geoviz_seismic.chunked_worker import ArbitraryLineWorker


class _FakeReader:
    def __init__(self, delay_matrix=None):
        self.calls: list[list[tuple[float, float]]] = []
        self._delay_matrix = delay_matrix

    def read_arbitrary_line(self, points, *, lod=0, interpolate=True):
        self.calls.append(list(points))
        if self._delay_matrix is not None:
            return self._delay_matrix
        n_points = len(points)
        return np.arange(n_points * 5, dtype=np.float32).reshape(n_points, 5)


def test_worker_emits_gather_for_requested_line(qtbot, monkeypatch):
    reader = _FakeReader()
    monkeypatch.setattr(
        "geoviz_seismic.chunked.open_volume", lambda path: reader
    )
    worker = ArbitraryLineWorker()
    worker.set_store("/fake/store", generation=3)
    worker.start()
    qtbot.wait_until(worker.isRunning, timeout=2000)
    with qtbot.waitSignal(worker.arbitrary_ready, timeout=3000) as blocker:
        worker.request_line([(100.0, 200.0), (101.0, 201.0), (102.0, 202.0)])
    data, generation = blocker.args
    assert generation == 3
    assert data.shape == (3, 5)  # (n_points, n_samples)
    assert reader.calls and len(reader.calls[-1]) == 3
    worker.stop()
    worker.wait(2000)


def test_worker_latest_request_wins(qtbot, monkeypatch):
    reader = _FakeReader()
    monkeypatch.setattr(
        "geoviz_seismic.chunked.open_volume", lambda path: reader
    )
    worker = ArbitraryLineWorker()
    worker.set_store("/fake/store", generation=1)
    worker.start()
    qtbot.wait_until(worker.isRunning, timeout=2000)
    worker.request_line([(1.0, 1.0), (2.0, 2.0)])
    worker.request_line([(9.0, 9.0), (8.0, 8.0), (7.0, 7.0), (6.0, 6.0)])
    received: list[tuple[int, ...]] = []
    worker.arbitrary_ready.connect(
        lambda data, gen: received.append(data.shape)
    )
    qtbot.wait_until(lambda: len(received) >= 1, timeout=3000)
    # Both queued requests may be served (they were serialized), but the last
    # emitted gather must be the 4-point line, never a stale first request
    # REPLACING it afterwards.
    assert received[-1] == (4, 5)
    worker.stop()
    worker.wait(2000)


def test_worker_stop_is_cooperative():
    worker = ArbitraryLineWorker()
    worker.start()
    worker.stop()
    assert worker.wait(2000)
