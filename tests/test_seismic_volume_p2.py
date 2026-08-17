"""P2 regressions for seismic volume findings #561-#565.

#559 / #560 were already correct at this HEAD (survey pick values are not
re-scaled; cursor/jump/synth go through ``_preview_to_survey_coords``).
"""

from __future__ import annotations

import time

import numpy as np
import pytest
import segyio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_2d_cdp_segy(path: str, n_traces: int = 40, n_samples: int = 30) -> None:
    """CDP-only 2-D line: no INLINE_3D/CROSSLINE_3D pair."""
    spec = segyio.spec()
    spec.format = 1
    spec.samples = np.arange(n_samples, dtype=np.float32) * 4.0
    spec.tracecount = n_traces
    with segyio.create(path, spec) as f:
        for i in range(n_traces):
            f.header[i] = {segyio.TraceField.CDP: i + 1}
            f.trace[i] = np.full(n_samples, float(i), dtype=np.float32)
        f.bin[segyio.BinField.Interval] = 4000
        f.bin[segyio.BinField.Samples] = n_samples


def _write_nonstandard_cube(
    path: str, n_il: int, n_xl: int, n_samples: int = 4
) -> None:
    """IL in FieldRecord, XL in CDP; standard 189/193 headers are zero."""
    spec = segyio.spec()
    spec.format = 1
    spec.samples = np.arange(n_samples, dtype=np.float32) * 4.0
    spec.tracecount = n_il * n_xl
    with segyio.create(path, spec) as f:
        for i in range(n_il):
            for j in range(n_xl):
                idx = i * n_xl + j
                f.header[idx] = {
                    segyio.TraceField.FieldRecord: 10 + i,
                    segyio.TraceField.CDP: 100 + j,
                    segyio.TraceField.INLINE_3D: 0,
                    segyio.TraceField.CROSSLINE_3D: 0,
                }
                f.trace[idx] = np.full(n_samples, float(i * 100 + j), dtype=np.float32)
        f.bin[segyio.BinField.Interval] = 4000
        f.bin[segyio.BinField.Samples] = n_samples


# ---------------------------------------------------------------------------
# #561 — survey-domain overlays must land inside the preview cube
# ---------------------------------------------------------------------------


def test_horizon_pick_scene_position_inside_cube(qtbot):
    """Pick (il=150, xl=250, t=800ms) on a start=100/200 survey stays in-cube."""
    from geoviz_seismic.models import SeismicVolumeMeta
    from geoviz_seismic.seismic_view import SeismicView

    view = SeismicView(auto_load=False)
    qtbot.addWidget(view)
    data = np.zeros((80, 80, 250), dtype=np.float32)
    view.load_demo(data)
    view._meta = SeismicVolumeMeta(
        filename="t",
        n_inlines=80,
        n_crosslines=80,
        n_samples=250,
        sample_interval=4.0,
        iline_start=100,
        iline_step=1,
        xline_start=200,
        xline_step=1,
        dt_ms=4.0,
        t0_ms=0.0,
    )
    view._ds_factor = (1, 1, 1)

    vox = view._survey_to_voxel(150.0, 250.0, 800.0)
    view._renderer_3d.set_horizon_picks([vox])
    pos = np.asarray(view._renderer_3d._picks_visual.pos)
    si, sx, st = view._renderer_3d._volume_spacing
    assert pos.shape == (1, 3)
    assert 0.0 <= pos[0, 0] <= 80 * si + 1e-6
    assert 0.0 <= pos[0, 1] <= 80 * sx + 1e-6
    assert 0.0 <= pos[0, 2] <= 250 * st + 1e-6
    # 800ms / 4ms = sample 200
    assert pos[0, 2] == pytest.approx(200.0 * st)


def test_add_horizon_ms_mesh_inside_cube(qtbot):
    """Horizon grid in milliseconds must be placed in preview-index scene space."""
    from geoviz_seismic.renderer_3d import Renderer3D

    widget = Renderer3D()
    qtbot.addWidget(widget)
    data = np.zeros((40, 50, 200), dtype=np.float32)
    spacing = (5.0, 4.0, 1.0)  # cube 200 x 200 x 200
    widget.load_volume(data, spacing=spacing)
    widget.set_survey_mapping(t0_ms=0.0, dt_ms=4.0, ds_factor=(1, 1, 1))

    # 400 ms = sample 100 of 200; must not be used raw as world-Z (400 > 200).
    grid_ms = np.full((40, 50), 400.0, dtype=np.float32)
    widget.add_horizon(grid_ms, name="h", z_unit="ms")
    mesh = widget._horizons["h"]
    verts = np.asarray(mesh.opts["meshdata"].vertexes())
    si, sx, st = spacing
    assert verts[:, 0].min() >= -1e-4
    assert verts[:, 0].max() <= 50 * sx + 1e-4
    assert verts[:, 1].min() >= -1e-4
    assert verts[:, 1].max() <= 40 * si + 1e-4
    assert verts[:, 2].min() >= -1e-4
    assert verts[:, 2].max() <= 200 * st + 1e-4
    assert np.allclose(verts[:, 2], 100.0 * st, atol=1e-4)


# ---------------------------------------------------------------------------
# #562 — sculpting must normalize ms by the preview time extent
# ---------------------------------------------------------------------------


def test_sculpt_ms_horizon_normalizes_into_unit_interval(qtbot):
    """A mid-time ms horizon must produce shader hz in (0, 1), not ms/(nt-1)."""
    from geoviz_seismic.renderer_3d import Renderer3D

    widget = Renderer3D()
    qtbot.addWidget(widget)
    data = np.zeros((10, 10, 50), dtype=np.float32)
    widget.load_volume(data)
    widget.set_render_mode("volume")
    widget.set_survey_mapping(t0_ms=0.0, dt_ms=4.0, ds_factor=(1, 1, 1))

    # 50% of the preview time range: t0 + 0.5*(nt-1)*dt*ft
    mid_ms = 0.5 * (50 - 1) * 4.0
    grid_ms = np.full((10, 10), mid_ms, dtype=np.float32)
    widget.set_sculpting_surface(grid_ms, mode="below")

    norm = widget._volume_visual._sculpt_horizon_data
    assert norm is not None
    assert np.all(norm > 0.0)
    assert np.all(norm < 1.0)
    assert np.allclose(norm, 0.5, atol=1e-5)
    # The old formula (ms / (nt-1)) yields 98/49 = 2.0, rejected by the shader.
    assert not np.allclose(norm, mid_ms / 49.0)


def test_sculpt_ms_accounts_for_time_downsample(qtbot):
    from geoviz_seismic.renderer_3d import Renderer3D

    widget = Renderer3D()
    qtbot.addWidget(widget)
    data = np.zeros((8, 8, 40), dtype=np.float32)
    widget.load_volume(data)
    widget.set_render_mode("volume")
    widget.set_survey_mapping(t0_ms=100.0, dt_ms=4.0, ds_factor=(2, 2, 2))

    # mid_ms = t0 + 0.5*(nt-1)*dt*ft
    mid_ms = 100.0 + 0.5 * (40 - 1) * 4.0 * 2
    widget.set_sculpting_surface(np.full((8, 8), mid_ms), mode="above")
    norm = widget._volume_visual._sculpt_horizon_data
    assert np.allclose(norm, 0.5, atol=1e-5)


# ---------------------------------------------------------------------------
# #563 — unstructured / 2-D SEG-Y must load via trace indexing
# ---------------------------------------------------------------------------


def test_unstructured_2d_segy_loads_via_trace_index(tmp_path):
    from geoviz_seismic.loader import SeismicLoader

    path = str(tmp_path / "line2d.sgy")
    _write_2d_cdp_segy(path, n_traces=40, n_samples=30)

    loader = SeismicLoader(path)
    try:
        meta = loader.inspect()
        vol = loader.get_volume_downsampled(factor=(1, 1, 1))
        inline = loader.read_inline(int(meta.iline_start))
    finally:
        loader.close()

    assert meta.n_inlines == 1
    assert meta.n_crosslines == 40
    assert meta.n_samples == 30
    assert vol.shape == (1, 40, 30)
    assert inline.shape == (40, 30)
    assert inline.dtype == np.float32
    assert inline[7, 0] == pytest.approx(7.0)


# ---------------------------------------------------------------------------
# #564 — vectorized header scan + (path, mtime) memo
# ---------------------------------------------------------------------------


def test_detect_geometry_uses_vectorized_attributes_not_header_loop():
    """200k-trace synthetic: detect the pair via attributes(), never header[i]."""
    from geoviz_seismic.loader import detect_iline_xline_fields

    n_il, n_xl = 400, 500  # 200k traces
    il = np.repeat(np.arange(n_il, dtype=np.int64), n_xl)
    xl = np.tile(np.arange(n_xl, dtype=np.int64), n_il)

    class _FakeSegy:
        tracecount = n_il * n_xl

        def __init__(self):
            self._fields = {
                int(segyio.TraceField.FieldRecord): il,
                int(segyio.TraceField.CDP): xl,
                int(segyio.TraceField.TRACE_SEQUENCE_LINE): np.zeros(self.tracecount, np.int64),
                int(segyio.TraceField.EnergySourcePoint): np.zeros(self.tracecount, np.int64),
                int(segyio.TraceField.INLINE_3D): np.zeros(self.tracecount, np.int64),
                int(segyio.TraceField.CROSSLINE_3D): np.zeros(self.tracecount, np.int64),
            }

        def attributes(self, field):
            arr = self._fields[int(field)]

            class _Collector:
                def __getitem__(self, sl):
                    return arr[sl]

            return _Collector()

        @property
        def header(self):
            raise AssertionError("header[i] Python loop must not run")

    t0 = time.perf_counter()
    pair = detect_iline_xline_fields(_FakeSegy())
    elapsed = time.perf_counter() - t0
    assert pair is not None
    assert set(pair) == {
        int(segyio.TraceField.FieldRecord),
        int(segyio.TraceField.CDP),
    }
    assert elapsed < 2.0


def test_nonstandard_geometry_probe_does_not_drop_slow_axis(tmp_path):
    """Slow-axis cardinality above a 512-trace probe: full scan must still grid.

    Sampling 512 traces cannot see 520 unique slow-axis values, so the old
    unique-count product never equals n_traces and fell through to unstructured.
    """
    from geoviz_seismic.loader import SeismicLoader, clear_geometry_field_cache

    clear_geometry_field_cache()
    path = str(tmp_path / "nonstd.sgy")
    n_il, n_xl = 520, 4
    _write_nonstandard_cube(path, n_il, n_xl, n_samples=4)

    loader = SeismicLoader(path)
    try:
        meta = loader.inspect()
        vol = loader.get_volume_downsampled(factor=(1, 1, 1))
    finally:
        loader.close()

    assert loader.geometry_source == "detected_headers"
    assert meta.n_inlines * meta.n_crosslines == n_il * n_xl
    assert vol.shape[0] * vol.shape[1] == n_il * n_xl
    assert vol.shape[2] == 4


def test_geometry_field_cache_skips_second_scan(tmp_path, monkeypatch):
    from geoviz_seismic import loader as loader_mod
    from geoviz_seismic.loader import SeismicLoader, clear_geometry_field_cache

    clear_geometry_field_cache()
    path = str(tmp_path / "nonstd_small.sgy")
    _write_nonstandard_cube(path, n_il=6, n_xl=5, n_samples=4)

    calls = {"n": 0}
    orig = loader_mod.read_header_attribute

    def _spy(f, field):
        calls["n"] += 1
        return orig(f, field)

    monkeypatch.setattr(loader_mod, "read_header_attribute", _spy)

    first = SeismicLoader(path)
    try:
        first.inspect()
    finally:
        first.close()
    n_first = calls["n"]
    assert n_first >= 1

    second = SeismicLoader(path)
    try:
        meta = second.inspect()
    finally:
        second.close()
    assert calls["n"] == n_first
    assert meta.n_inlines * meta.n_crosslines == 30


# ---------------------------------------------------------------------------
# #565 — wiggle decimates to the viewport and does not lock data-shaped mins
# ---------------------------------------------------------------------------


def test_wiggle_viewport_decimation_caps_samples_and_traces():
    from geoviz_seismic.profile_wiggle import viewport_decimation

    ts, sidx = viewport_decimation(1500, 1500, 800, 600, trace_step=1)
    assert ts >= (1500 + 800 - 1) // 800
    assert (1500 + ts - 1) // ts <= 800
    assert sidx.size <= 600 + 1
    assert int(sidx[0]) == 0
    assert int(sidx[-1]) == 1499


def test_wiggle_render_does_not_set_data_shaped_minimum(qtbot):
    from geoviz_seismic.profile_wiggle import ProfileWiggle

    widget = ProfileWiggle()
    qtbot.addWidget(widget)
    widget.resize(800, 600)
    data = np.random.randn(1500, 1500).astype(np.float32)
    widget.render(data, trace_step=1)
    assert widget.minimumWidth() <= 800
    assert widget.minimumHeight() <= 600


def test_wiggle_paint_1500_stays_within_budget(qtbot):
    from geoviz_seismic.profile_wiggle import ProfileWiggle

    widget = ProfileWiggle()
    qtbot.addWidget(widget)
    widget.setFixedSize(800, 600)
    data = np.random.randn(1500, 1500).astype(np.float32)
    widget.render(data, trace_step=1)
    widget.show()
    qtbot.waitExposed(widget)

    t0 = time.perf_counter()
    widget._cached_pixmap = None
    widget.repaint()
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.5
    assert widget.minimumWidth() <= 800
    assert widget.minimumHeight() <= 600
