from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QWidget

from geoviz import ErrorCode, GeoVizEngine, GeoVizError, PreviewKind, PreviewOptions, PreviewRequest
import geoviz_seismic
from geoviz_seismic import SeismicPreviewPayload, SeismicSlice
from geoviz_seismic.loader import SeismicLoader
from geoviz_seismic.models import SeismicVolumeMeta
from geoviz_seismic.preview_widget import downsample_2d
from geoviz.previews.seismic import downsample_2d as engine_downsample_2d


ENGINE_ROOT = Path(__file__).resolve().parents[1]
LOCAL_PACKAGE_ROOTS = (
    ENGINE_ROOT,
    *(ENGINE_ROOT / "packages" / name for name in (
        "geoviz_common",
        "geoviz_cross_well",
        "geoviz_map",
        "geoviz_paleo_map",
        "geoviz_plots",
        "geoviz_seismic",
        "geoviz_well_log",
        "geoviz_well_tie",
    )),
)


def _request(path: str | Path, *, semantic_type: str = "seismic", format: str = "sgy"):
    return PreviewRequest("seismic-1", str(path), semantic_type, format, "Middle slices")


def test_downsample_2d_bounds_each_axis_and_returns_float32_contiguous_array():
    data = np.arange(1_025 * 1_023, dtype=np.float64).reshape(1_025, 1_023)

    sampled = downsample_2d(data, 512)

    assert sampled.shape == (342, 512)
    assert sampled.dtype == np.float32
    assert sampled.flags.c_contiguous
    # Engine re-exports the same helper for public preview API.
    assert engine_downsample_2d(data, 512).shape == sampled.shape


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
    assert payload.source_path == str(small_segy_path)
    assert payload.max_slice_axis == 8
    assert set(payload.axes) == {"inline", "crossline", "time"}
    assert payload.axes["inline"].count >= 1
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


def _run_slice_preview_import_check(tmp_path: Path, *, env=None):
    script = textwrap.dedent(
        """
        import sys
        from pathlib import Path

        expected_checkout = Path(sys.argv[1]).resolve()

        assert "geoviz_seismic.renderer_3d" not in sys.modules
        import geoviz
        import geoviz_seismic
        assert Path(geoviz.__file__).resolve().is_relative_to(expected_checkout)
        assert Path(geoviz_seismic.__file__).resolve().is_relative_to(expected_checkout)
        from geoviz import GeoVizEngine
        from geoviz_seismic import SeismicPreviewPayload, SeismicPreviewWidget
        from geoviz.previews.seismic import SeismicPreviewBackend

        engine = GeoVizEngine.default()
        assert engine is not None
        assert SeismicPreviewBackend is not None
        assert SeismicPreviewPayload is not None
        assert SeismicPreviewWidget is not None
        assert "geoviz_seismic.renderer_3d" not in sys.modules
        print(geoviz.__file__)
        print(geoviz_seismic.__file__)
        """
    )
    child_env = (os.environ if env is None else env).copy()
    inherited_pythonpath = child_env.get("PYTHONPATH", "")
    child_env["PYTHONPATH"] = os.pathsep.join(
        [
            *(str(path) for path in LOCAL_PACKAGE_ROOTS),
            *([inherited_pythonpath] if inherited_pythonpath else []),
        ]
    )

    return subprocess.run(
        [sys.executable, "-c", script, str(ENGINE_ROOT)],
        cwd=tmp_path,
        env=child_env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_slice_preview_imports_do_not_load_renderer_3d_in_fresh_interpreter(tmp_path: Path):
    result = _run_slice_preview_import_check(tmp_path)

    assert result.returncode == 0, result.stderr
    module_paths = result.stdout.splitlines()
    assert len(module_paths) == 2
    assert all(
        Path(line).resolve().is_relative_to(ENGINE_ROOT) for line in module_paths
    )


def test_slice_preview_import_check_rejects_wrong_pythonpath(tmp_path: Path):
    fake_root = tmp_path / "wrong-checkout"
    fake_geoviz = fake_root / "geoviz"
    fake_previews = fake_geoviz / "previews"
    fake_seismic = fake_root / "geoviz_seismic"
    fake_previews.mkdir(parents=True)
    fake_seismic.mkdir(parents=True)
    fake_geoviz.joinpath("__init__.py").write_text(
        "class GeoVizEngine:\n"
        "    @classmethod\n"
        "    def default(cls):\n"
        "        return cls()\n",
        encoding="utf-8",
    )
    fake_previews.joinpath("__init__.py").write_text("", encoding="utf-8")
    fake_previews.joinpath("seismic.py").write_text(
        "SeismicPreviewBackend = object()\n", encoding="utf-8"
    )
    fake_seismic.joinpath("__init__.py").write_text(
        "SeismicPreviewPayload = object()\nSeismicPreviewWidget = object()\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(fake_root)

    result = _run_slice_preview_import_check(tmp_path, env=env)

    assert result.returncode == 0, result.stderr
    module_paths = result.stdout.splitlines()
    assert len(module_paths) == 2
    assert all(
        Path(line).resolve().is_relative_to(ENGINE_ROOT) for line in module_paths
    )


def test_backend_creates_preview_widget_and_renders_via_set_slices(
    qtbot, monkeypatch, small_segy_path
):
    created = []

    class FakePreviewWidget(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.slices_payloads = []
            self.cleaned_up = False
            created.append(self)

        def set_slices(self, payload):
            self.slices_payloads.append(payload)

        def cleanup(self):
            self.cleaned_up = True

    monkeypatch.setattr(geoviz_seismic, "SeismicPreviewWidget", FakePreviewWidget)
    preview = GeoVizEngine.default().prepare(
        _request(small_segy_path), PreviewOptions(max_slice_axis=16)
    )
    engine = GeoVizEngine.default()
    widget = engine.create_widget(preview.kind)
    qtbot.addWidget(widget)

    # create_widget returns the lightweight SeismicPreviewWidget (no 3-D
    # renderer, no async volume load), created lazily on first request.
    assert isinstance(widget, FakePreviewWidget)
    assert created == [widget]
    assert widget.slices_payloads == []

    # render() delegates to set_slices() with the middle slices already
    # prepared in prepare(); it does not open the SEGY again.
    engine.render(widget, preview)
    assert widget.slices_payloads == [preview.payload]

    engine.release(widget)
    assert widget.cleaned_up is True
