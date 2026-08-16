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


def _c3_request(data, c3_idx):
    return workers.AttrComputeRequest(
        generation=1,
        segy_generation=1,
        slice_type="inline",
        position=0,
        attr_idx=c3_idx,
        data=data,
        sample_interval_s=0.002,
    )


def test_c3_downsampled_display_computes_c3_exactly_once(monkeypatch):
    """Large 2-D C3 requests must return the upsampled coherence directly.

    Regression: the downsampled branch assigned the upsampled coherence map
    to ``data`` and then fell through to the shared ``_ap.apply`` tail,
    running C3 a second time on coherence values (wrong result, and the
    downsampling optimisation was defeated).
    """
    import numpy as np
    from geoviz_seismic import attribute_pipeline as ap

    c3_idx = ap.labels().index("相干性(C3)")
    rng = np.random.default_rng(0)
    data = rng.standard_normal((640, 32)).astype(np.float32)

    calls = []
    real_apply = ap.apply

    def spy_apply(idx, arr, sample_interval_s=1.0):
        calls.append(arr.shape)
        return real_apply(idx, arr, sample_interval_s=sample_interval_s)

    monkeypatch.setattr(ap, "apply", spy_apply)
    out = workers._compute_attr_display(_c3_request(data, c3_idx))

    # C3 ran exactly once, on the strided (half-resolution) input.
    assert calls == [data[::2, ::2].shape]
    assert out.shape == data.shape

    # Reference: a single C3 on the strided data, block-upsampled, cropped.
    small = real_apply(c3_idx, data[::2, ::2])
    ref = np.repeat(np.repeat(small, 2, axis=0), 2, axis=1)[
        : data.shape[0], : data.shape[1]
    ]
    np.testing.assert_allclose(out, ref, atol=1e-6)


def test_c3_small_slice_skips_downsample(monkeypatch):
    """Slices under the pixel threshold compute C3 directly, once."""
    import numpy as np
    from geoviz_seismic import attribute_pipeline as ap

    c3_idx = ap.labels().index("相干性(C3)")
    rng = np.random.default_rng(0)
    data = rng.standard_normal((64, 48)).astype(np.float32)

    calls = []
    real_apply = ap.apply

    def spy_apply(idx, arr, sample_interval_s=1.0):
        calls.append(arr.shape)
        return real_apply(idx, arr, sample_interval_s=sample_interval_s)

    monkeypatch.setattr(ap, "apply", spy_apply)
    out = workers._compute_attr_display(_c3_request(data, c3_idx))

    assert calls == [data.shape]
    np.testing.assert_allclose(out, real_apply(c3_idx, data), atol=1e-6)


def test_attr_combo_disables_attributes_without_2d_support(qtbot):
    """Combo entries for attributes undefined on 2-D slices (Gaussian/max
    curvature) must be disabled so users cannot select a guaranteed
    all-zero result."""
    from geoviz_seismic import attribute_pipeline as ap
    from geoviz_seismic import seismic_view as view_module

    view = view_module.SeismicView(auto_load=False)
    qtbot.addWidget(view)

    model = view._attr_combo.model()
    assert model.rowCount() == len(ap.ATTRIBUTES)
    for i, spec in enumerate(ap.ATTRIBUTES):
        item = model.item(i)
        if spec.supports_2d:
            assert item.isEnabled(), spec.label
        else:
            assert not item.isEnabled(), spec.label
