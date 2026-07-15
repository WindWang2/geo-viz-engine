import importlib
import subprocess
import sys
import textwrap
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from PySide6.QtWidgets import QLabel

import geoviz
from geoviz import (
    ErrorCode,
    GeoVizEngine,
    GeoVizError,
    PreparedPreview,
    PreviewCapabilities,
    PreviewKind,
    PreviewOptions,
    PreviewRequest,
)


class FakeBackend:
    kind = PreviewKind.XY_SCATTER

    def __init__(self):
        self.created_widgets = 0

    def supports(self, request):
        return request.normalized_format == "dat"

    def capabilities(self, request):
        return PreviewCapabilities(self.kind, ("zoom", "pan"))

    def prepare(self, request, options):
        return PreparedPreview(self.kind, request.label, {"path": request.path}, estimated_bytes=64)

    def create_widget(self, parent=None):
        self.created_widgets += 1
        return QLabel(parent)

    def render(self, widget, preview):
        widget.setText(preview.title)

    def release(self, widget):
        widget.clear()


def test_engine_routes_prepare_and_ui_calls(qtbot, tmp_path: Path):
    engine = GeoVizEngine([FakeBackend()])
    request = PreviewRequest("r1", str(tmp_path / "wells.dat"), "well_head", "dat", "Wells")
    assert engine.supports(request)
    assert engine.capabilities(request).interactions == ("zoom", "pan")
    preview = engine.prepare(request, PreviewOptions.local())
    widget = engine.create_widget(preview.kind)
    qtbot.addWidget(widget)
    engine.render(widget, preview)
    assert widget.text() == "Wells"
    engine.release(widget)
    assert widget.text() == ""


def test_engine_reports_unsupported_requests(tmp_path: Path):
    engine = GeoVizEngine([FakeBackend()])
    request = PreviewRequest("r1", str(tmp_path / "notes.txt"), "unknown", "txt")

    assert not engine.supports(request)
    with pytest.raises(GeoVizError) as caught:
        engine.prepare(request, PreviewOptions.local())
    assert caught.value.code is ErrorCode.UNSUPPORTED


def test_prepare_runs_in_worker_without_creating_qt_objects(tmp_path: Path):
    backend = FakeBackend()
    engine = GeoVizEngine([backend])
    request = PreviewRequest("r1", str(tmp_path / "wells.dat"), "well_head", "dat", "Wells")

    with ThreadPoolExecutor(max_workers=1) as executor:
        preview = executor.submit(engine.prepare, request, PreviewOptions.local()).result()

    assert preview.title == "Wells"
    assert backend.created_widgets == 0


def test_engine_rejects_ui_lifecycle_calls_from_worker(qtbot):
    engine = GeoVizEngine([FakeBackend()])
    widget = engine.create_widget(PreviewKind.XY_SCATTER)
    qtbot.addWidget(widget)
    preview = PreparedPreview(PreviewKind.XY_SCATTER, "Wells", {})

    calls = (
        lambda: engine.create_widget(PreviewKind.XY_SCATTER),
        lambda: engine.render(widget, preview),
        lambda: engine.release(widget),
    )
    with ThreadPoolExecutor(max_workers=1) as executor:
        for call in calls:
            with pytest.raises(GeoVizError) as caught:
                executor.submit(call).result()
            assert caught.value.code is ErrorCode.RENDER_ERROR

    engine.release(widget)


def test_default_factory_constructs_backends_in_deterministic_order(monkeypatch):
    created = []

    def backend_type(name):
        class Backend:
            def __init__(self):
                created.append(name)

        Backend.__name__ = name
        return Backend

    previews = ModuleType("geoviz.previews")
    previews.__path__ = []
    well_log = ModuleType("geoviz.previews.well_log")
    seismic = ModuleType("geoviz.previews.seismic")
    dat = ModuleType("geoviz.previews.dat")
    well_log.WellLogPreviewBackend = backend_type("WellLogPreviewBackend")
    seismic.SeismicPreviewBackend = backend_type("SeismicPreviewBackend")
    for name in (
        "XYScatterBackend",
        "TimeDepthBackend",
        "HorizonSurfaceBackend",
        "WellStratificationBackend",
    ):
        setattr(dat, name, backend_type(name))
    monkeypatch.setitem(sys.modules, "geoviz.previews", previews)
    monkeypatch.setitem(sys.modules, "geoviz.previews.well_log", well_log)
    monkeypatch.setitem(sys.modules, "geoviz.previews.seismic", seismic)
    monkeypatch.setitem(sys.modules, "geoviz.previews.dat", dat)

    GeoVizEngine.default()

    assert created == [
        "WellLogPreviewBackend",
        "SeismicPreviewBackend",
        "XYScatterBackend",
        "TimeDepthBackend",
        "HorizonSurfaceBackend",
        "WellStratificationBackend",
    ]


def test_import_geoviz_succeeds_without_optional_packages(tmp_path: Path):
    script = textwrap.dedent(
        """
        import builtins

        blocked_roots = {
            "geoviz_well_log",
            "geoviz_seismic",
            "geoviz_paleo_map",
            "geoviz_cross_well",
            "geoviz_plots",
        }
        real_import = builtins.__import__

        def blocked_import(name, *args, **kwargs):
            if name.split(".", 1)[0] in blocked_roots:
                raise ModuleNotFoundError(name)
            return real_import(name, *args, **kwargs)

        builtins.__import__ = blocked_import
        import geoviz
        assert geoviz.GeoVizEngine is not None
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


@pytest.mark.parametrize(
    ("export_name", "module_name"),
    [
        ("WellLogCanvas", "geoviz_well_log"),
        ("WellLogData", "geoviz_well_log"),
        ("CurveData", "geoviz_well_log"),
        ("build_qpainter_tracks", "geoviz_well_log"),
        ("SeismicView", "geoviz_seismic"),
        ("ProfileWidget", "geoviz_seismic"),
        ("PaleoMapCanvas", "geoviz_paleo_map"),
        ("CrossWellCanvas", "geoviz_cross_well"),
        ("PlotWidget", "geoviz_plots"),
        ("SurfaceWidget", "geoviz_plots"),
    ],
)
def test_compatibility_export_imports_only_when_requested(monkeypatch, export_name, module_name):
    sentinel = object()
    imported = []

    def fake_import_module(name):
        imported.append(name)
        return SimpleNamespace(**{export_name: sentinel})

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    try:
        assert imported == []
        assert getattr(geoviz, export_name) is sentinel
        assert imported == [module_name]
    finally:
        geoviz.__dict__.pop(export_name, None)
