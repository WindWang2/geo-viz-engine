from __future__ import annotations

import subprocess
import sys
import textwrap
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QComboBox

from geoviz import ErrorCode, GeoVizEngine, GeoVizError, PreviewKind, PreviewOptions, PreviewRequest
from geoviz_seismic import SeismicPreviewWidget, SeismicPreviewPayload, SeismicSlice
from geoviz_seismic.loader import SeismicLoader
from geoviz_seismic.models import SeismicVolumeMeta
from geoviz_seismic.profile_widget import ProfileWidget
from geoviz.previews.seismic import downsample_2d


def _request(path: str | Path, *, semantic_type: str = "seismic", format: str = "sgy"):
    return PreviewRequest("seismic-1", str(path), semantic_type, format, "Middle slices")


def test_downsample_2d_bounds_each_axis_and_returns_float32_contiguous_array():
    data = np.arange(1_025 * 1_023, dtype=np.float64).reshape(1_025, 1_023)

    sampled = downsample_2d(data, 512)

    assert sampled.shape == (342, 512)
    assert sampled.dtype == np.float32
    assert sampled.flags.c_contiguous


def test_default_backend_supports_only_segy_seismic_requests(tmp_path: Path):
    engine = GeoVizEngine.default()

    assert engine.supports(_request(tmp_path / "cube.SGY"))
    assert engine.supports(_request(tmp_path / "cube.segy", semantic_type="unknown", format=".SEGY"))
    assert not engine.supports(_request(tmp_path / "cube.sgy", semantic_type="well_log"))
    assert not engine.supports(_request(tmp_path / "cube.las", format="las"))


def test_prepare_reads_only_bounded_middle_slices_and_closes_loader(
    monkeypatch, small_segy_path
):
    def reject_volume(*args, **kwargs):
        raise AssertionError("seismic preview must not read a volume")

    original_close = SeismicLoader.close
    close_states = []

    def tracking_close(loader):
        was_open = loader._f is not None
        original_close(loader)
        close_states.append((was_open, loader._f is None))

    monkeypatch.setattr(SeismicLoader, "get_volume_downsampled", reject_volume)
    monkeypatch.setattr(SeismicLoader, "close", tracking_close)

    options = PreviewOptions(max_slice_axis=8)
    with ThreadPoolExecutor(max_workers=1) as executor:
        preview = executor.submit(
            GeoVizEngine.default().prepare,
            _request(small_segy_path),
            options,
        ).result()

    payload = preview.payload
    assert preview.kind is PreviewKind.SEISMIC_2D
    assert preview.title == "Middle slices"
    assert isinstance(payload, SeismicPreviewPayload)
    assert payload.initial_mode == "inline"
    assert tuple(payload.slices) == ("inline", "crossline", "time")
    assert (True, True) in close_states
    assert preview.estimated_bytes == sum(item.data.nbytes for item in payload.slices.values())

    expected = {
        "inline": (105, "Crossline", "Time (ms)"),
        "crossline": (210, "Inline", "Time (ms)"),
        "time": (15, "Inline", "Crossline"),
    }
    for mode, seismic_slice in payload.slices.items():
        assert isinstance(seismic_slice, SeismicSlice)
        assert seismic_slice.data.ndim == 2
        assert max(seismic_slice.data.shape) <= options.max_slice_axis
        assert seismic_slice.data.dtype == np.float32
        assert seismic_slice.data.flags.c_contiguous
        position, horizontal_label, vertical_label = expected[mode]
        assert seismic_slice.info.slice_type == mode
        assert seismic_slice.info.position == position
        assert seismic_slice.info.axis_h_label == horizontal_label
        assert seismic_slice.info.axis_v_label == vertical_label
        assert len(seismic_slice.info.axis_h_values) == seismic_slice.data.shape[1]
        assert len(seismic_slice.info.axis_v_values) == seismic_slice.data.shape[0]


def test_prepare_closes_loader_when_a_slice_read_fails(monkeypatch, small_segy_path):
    original_close = SeismicLoader.close
    close_states = []

    def tracking_close(loader):
        was_open = loader._f is not None
        original_close(loader)
        close_states.append((was_open, loader._f is None))

    def reject_inline(loader, iline):
        raise ValueError("damaged inline")

    monkeypatch.setattr(SeismicLoader, "close", tracking_close)
    monkeypatch.setattr(SeismicLoader, "read_inline", reject_inline)

    with pytest.raises(GeoVizError) as caught:
        GeoVizEngine.default().prepare(_request(small_segy_path), PreviewOptions.local())

    assert caught.value.code is ErrorCode.INVALID_DATA
    assert (True, True) in close_states


def test_prepare_never_exceeds_hard_512_axis_cap(monkeypatch, tmp_path: Path):
    class LargeSliceLoader:
        def __init__(self, path):
            self.closed = False

        def inspect(self):
            return SeismicVolumeMeta(
                filename="large.sgy",
                n_inlines=700,
                n_crosslines=600,
                n_samples=800,
                sample_interval=4.0,
                iline_start=100,
                iline_step=1,
                xline_start=200,
                xline_step=1,
                dt_ms=4.0,
            )

        def read_inline(self, iline):
            return np.zeros((600, 800), dtype=np.float32)

        def read_crossline(self, xline):
            return np.zeros((700, 800), dtype=np.float32)

        def read_timeslice(self, sample):
            return np.zeros((700, 600), dtype=np.float32)

        def close(self):
            self.closed = True

    monkeypatch.setattr("geoviz.previews.seismic.SeismicLoader", LargeSliceLoader)

    preview = GeoVizEngine.default().prepare(
        _request(tmp_path / "large.sgy"), PreviewOptions(max_slice_axis=1_024)
    )

    assert all(max(item.data.shape) <= 512 for item in preview.payload.slices.values())


def test_slice_preview_imports_do_not_load_renderer_3d_in_fresh_interpreter(tmp_path: Path):
    script = textwrap.dedent(
        """
        import sys

        assert "geoviz_seismic.renderer_3d" not in sys.modules
        from geoviz import GeoVizEngine
        from geoviz_seismic import SeismicPreviewPayload, SeismicPreviewWidget
        from geoviz.previews.seismic import SeismicPreviewBackend

        engine = GeoVizEngine.default()
        assert engine is not None
        assert SeismicPreviewBackend is not None
        assert SeismicPreviewPayload is not None
        assert SeismicPreviewWidget is not None
        assert "geoviz_seismic.renderer_3d" not in sys.modules
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_widget_switches_stable_slice_modes(qtbot, small_segy_path):
    preview = GeoVizEngine.default().prepare(
        _request(small_segy_path), PreviewOptions(max_slice_axis=16)
    )
    engine = GeoVizEngine.default()
    widget = engine.create_widget(preview.kind)
    qtbot.addWidget(widget)

    assert isinstance(widget, SeismicPreviewWidget)
    combo = widget.findChild(QComboBox)
    profile = widget.findChild(ProfileWidget)
    assert combo is not None
    assert profile is not None
    assert [combo.itemData(index) for index in range(combo.count())] == [
        "inline",
        "crossline",
        "time",
    ]

    engine.render(widget, preview)
    assert profile._current_data is preview.payload.slices["inline"].data
    assert profile._current_slice_info is preview.payload.slices["inline"].info

    combo.setCurrentIndex(combo.findData("time"))
    assert profile._current_data is preview.payload.slices["time"].data
    assert profile._current_slice_info is preview.payload.slices["time"].info

    engine.release(widget)
    assert widget._slices == {}
    assert profile._overlay.text() == "暂无地震切片"
    assert not profile._overlay.isHidden()
