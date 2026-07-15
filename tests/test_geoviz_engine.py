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


def _backend_type(name, created):
    class Backend:
        def __init__(self):
            self.name = name
            created.append(self)

    Backend.__name__ = name
    return Backend


def _install_preview_modules(monkeypatch, available, *, include_well_stratification=False):
    created = []
    previews = ModuleType("geoviz.previews")
    previews.__path__ = []
    monkeypatch.setitem(sys.modules, "geoviz.previews", previews)

    if "well_log" in available:
        well_log = ModuleType("geoviz.previews.well_log")
        well_log.WellLogPreviewBackend = _backend_type("WellLogPreviewBackend", created)
        monkeypatch.setitem(sys.modules, "geoviz.previews.well_log", well_log)

    if "seismic" in available:
        seismic = ModuleType("geoviz.previews.seismic")
        seismic.SeismicPreviewBackend = _backend_type("SeismicPreviewBackend", created)
        monkeypatch.setitem(sys.modules, "geoviz.previews.seismic", seismic)

    if "dat" in available:
        dat = ModuleType("geoviz.previews.dat")
        names = ["XYScatterBackend", "TimeDepthBackend", "HorizonSurfaceBackend"]
        if include_well_stratification:
            names.append("WellStratificationBackend")
        for name in names:
            setattr(dat, name, _backend_type(name, created))
        monkeypatch.setitem(sys.modules, "geoviz.previews.dat", dat)

    return created


def test_default_factory_is_callable_before_preview_modules_exist(tmp_path: Path):
    engine = GeoVizEngine.default()
    request = PreviewRequest("r1", str(tmp_path / "wells.dat"), "well_head", "dat")

    assert engine._registry._backends == []
    assert not engine.supports(request)


@pytest.mark.parametrize(
    ("available", "include_well_stratification", "expected_names"),
    [
        (("well_log",), False, ["WellLogPreviewBackend"]),
        (("well_log", "seismic"), False, ["WellLogPreviewBackend", "SeismicPreviewBackend"]),
        (
            ("well_log", "seismic", "dat"),
            False,
            [
                "WellLogPreviewBackend",
                "SeismicPreviewBackend",
                "XYScatterBackend",
                "TimeDepthBackend",
                "HorizonSurfaceBackend",
            ],
        ),
        (
            ("well_log", "seismic", "dat"),
            True,
            [
                "WellLogPreviewBackend",
                "SeismicPreviewBackend",
                "XYScatterBackend",
                "TimeDepthBackend",
                "HorizonSurfaceBackend",
                "WellStratificationBackend",
            ],
        ),
    ],
)
def test_default_factory_accumulates_available_backends_in_final_order(
    monkeypatch, available, include_well_stratification, expected_names
):
    created = _install_preview_modules(
        monkeypatch,
        available,
        include_well_stratification=include_well_stratification,
    )

    engine = GeoVizEngine.default()

    assert engine._registry._backends == created
    assert [backend.name for backend in engine._registry._backends] == expected_names


@pytest.mark.parametrize(
    ("module_name", "required_name"),
    [
        ("well_log", "WellLogPreviewBackend"),
        ("seismic", "SeismicPreviewBackend"),
        ("dat", "XYScatterBackend"),
        ("dat", "TimeDepthBackend"),
        ("dat", "HorizonSurfaceBackend"),
    ],
)
def test_default_factory_rejects_missing_required_backend_class(monkeypatch, module_name, required_name):
    created = _install_preview_modules(monkeypatch, (module_name,))
    module = sys.modules[f"geoviz.previews.{module_name}"]
    delattr(module, required_name)

    with pytest.raises(AttributeError, match=required_name):
        GeoVizEngine.default()

    assert created == []


def test_default_factory_does_not_hide_internal_dependency_errors(monkeypatch):
    real_import_module = importlib.import_module

    def import_module(name):
        if name == "geoviz.previews.well_log":
            raise ModuleNotFoundError("No module named 'lasio'", name="lasio")
        return real_import_module(name)

    monkeypatch.setattr(importlib, "import_module", import_module)

    with pytest.raises(ModuleNotFoundError) as caught:
        GeoVizEngine.default()
    assert caught.value.name == "lasio"


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
