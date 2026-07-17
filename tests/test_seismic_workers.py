from __future__ import annotations

import math
from types import SimpleNamespace

from geoviz_seismic import workers


def test_downsample_factor_enforces_voxel_budget():
    shape = (1200, 900, 600)
    budget = 2_000_000

    factor = workers.downsample_factor_for_budget(shape, max_voxels=budget)

    output_shape = tuple(math.ceil(size / stride) for size, stride in zip(shape, factor))
    assert math.prod(output_shape) <= budget
    assert workers.downsample_factor_for_budget((20, 30, 40), max_voxels=100_000) == (1, 1, 1)


def test_segy_worker_closes_loader_when_volume_read_fails(monkeypatch):
    instances = []

    class FakeLoader:
        def __init__(self, path):
            self.closed = False
            instances.append(self)

        def inspect(self):
            return SimpleNamespace(n_inlines=10, n_crosslines=20, n_samples=30)

        def get_volume_downsampled(self, *, factor, cancellation_token=None):
            raise RuntimeError("broken volume")

        def close(self):
            self.closed = True

    monkeypatch.setattr(workers, "SeismicLoader", FakeLoader)
    worker = workers.SegyLoadWorker("broken.sgy", generation=7)
    errors = []
    worker.error.connect(errors.append)

    worker.run()

    assert errors and "broken volume" in errors[0].message
    assert instances[0].closed is True


def test_segy_worker_result_carries_budget_factor_and_generation(monkeypatch):
    import numpy as np

    class FakeLoader:
        def __init__(self, path):
            self.factor = None

        def inspect(self):
            return SimpleNamespace(
                n_inlines=100,
                n_crosslines=80,
                n_samples=60,
                iline_start=10,
                iline_step=1,
                xline_start=20,
                xline_step=1,
            )

        def get_volume_downsampled(self, *, factor, cancellation_token=None):
            self.factor = factor
            return np.ones(tuple(math.ceil(v / f) for v, f in zip((100, 80, 60), factor)))

        def read_inline(self, value):
            return np.ones((80, 60))

        def read_crossline(self, value):
            return np.ones((100, 60))

        def read_timeslice(self, value):
            return np.ones((100, 80))

        def close(self):
            pass

    monkeypatch.setattr(workers, "SeismicLoader", FakeLoader)
    worker = workers.SegyLoadWorker("ok.sgy", generation=11, max_voxels=20_000)
    results = []
    worker.done.connect(results.append)

    worker.run()

    assert results[0].generation == 11
    assert results[0].downsample_factor != (1, 1, 1)
    assert results[0].volume.size <= 20_000


def test_seismic_view_rapid_load_accepts_only_latest_generation(qtbot, monkeypatch):
    import numpy as np
    from PySide6.QtCore import QObject, Signal
    from geoviz_seismic import seismic_view as view_module
    from geoviz_seismic.models import SeismicVolumeMeta

    instances = []

    class FakeWorker(QObject):
        done = Signal(object)
        error = Signal(object)
        finished = Signal()

        def __init__(self, path, *, generation=0, **kwargs):
            super().__init__()
            self.path = path
            self.generation = generation
            self.interrupted = False
            self.running = False
            instances.append(self)

        def start(self):
            self.running = True

        def isRunning(self):
            return self.running

        def requestInterruption(self):
            self.interrupted = True

    class FakeLoader:
        def __init__(self, path):
            self.path = path

        def close(self):
            pass

    monkeypatch.setattr(view_module, "SegyLoadWorker", FakeWorker)
    monkeypatch.setattr(view_module, "SeismicLoader", FakeLoader)
    monkeypatch.setattr(view_module, "retain_background_worker", lambda worker: None)
    view = view_module.SeismicView(auto_load=False)
    qtbot.addWidget(view)
    accepted = []
    view.segy_loaded.connect(accepted.append)

    view.load_segy_async("old.sgy")
    view.load_segy_async("new.sgy")

    assert instances[0].interrupted is True
    meta = SeismicVolumeMeta(
        filename="new.sgy",
        n_inlines=3,
        n_crosslines=3,
        n_samples=3,
        sample_interval=4.0,
        iline_start=0,
        iline_step=1,
        xline_start=0,
        xline_step=1,
        dt_ms=4.0,
        t0_ms=0.0,
    )

    def result(worker):
        return workers.SeismicLoadResult(
            generation=worker.generation,
            meta=meta,
            volume=np.ones((3, 3, 3), dtype=np.float32),
            raw_inline=np.ones((3, 3), dtype=np.float32),
            raw_crossline=np.ones((3, 3), dtype=np.float32),
            raw_timeslice=np.ones((3, 3), dtype=np.float32),
            path=worker.path,
            downsample_factor=(1, 1, 1),
        )

    instances[0].done.emit(result(instances[0]))
    assert accepted == []
    instances[1].done.emit(result(instances[1]))
    assert [item.path for item in accepted] == ["new.sgy"]

    view.load_segy_async("stale.sgy")
    stale_worker = instances[2]
    view.load_demo(np.zeros((3, 3, 3), dtype=np.float32))

    assert stale_worker.interrupted is True
    stale_worker.done.emit(result(stale_worker))
    assert [item.path for item in accepted] == ["new.sgy"]
