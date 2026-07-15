import importlib
from pathlib import Path
from types import SimpleNamespace

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

    def supports(self, request):
        return request.normalized_format == "dat"

    def capabilities(self, request):
        return PreviewCapabilities(self.kind, ("zoom", "pan"))

    def prepare(self, request, options):
        return PreparedPreview(self.kind, request.label, {"path": request.path}, estimated_bytes=64)

    def create_widget(self, parent=None):
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


def test_compatibility_export_imports_only_when_requested(monkeypatch):
    sentinel = object()
    imported = []

    def fake_import_module(name):
        imported.append(name)
        return SimpleNamespace(WellLogData=sentinel)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    try:
        assert imported == []
        assert geoviz.WellLogData is sentinel
        assert imported == ["geoviz_well_log"]
    finally:
        geoviz.__dict__.pop("WellLogData", None)
