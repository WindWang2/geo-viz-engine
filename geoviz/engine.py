from __future__ import annotations

from weakref import WeakKeyDictionary

from PySide6.QtCore import QCoreApplication, QThread
from PySide6.QtWidgets import QWidget

from .contracts import PreparedPreview, PreviewCapabilities, PreviewKind, PreviewOptions, PreviewRequest
from .errors import ErrorCode, GeoVizError
from .registry import PreviewBackend, PreviewRegistry


def _require_ui_thread() -> None:
    application = QCoreApplication.instance()
    if application is None or QThread.currentThread() is not application.thread():
        raise GeoVizError(ErrorCode.RENDER_ERROR, "Qt 控件操作必须在 UI 线程执行")


class GeoVizEngine:
    def __init__(self, backends: list[PreviewBackend] | tuple[PreviewBackend, ...] = ()) -> None:
        self._registry = PreviewRegistry(backends)
        self._widget_kinds: WeakKeyDictionary[QWidget, PreviewKind] = WeakKeyDictionary()

    @classmethod
    def default(cls) -> "GeoVizEngine":
        import importlib

        preview_package = f"{__package__}.previews"

        def optional_module(name: str):
            module_name = f"{preview_package}.{name}"
            try:
                return importlib.import_module(module_name)
            except ModuleNotFoundError as error:
                if error.name in {preview_package, module_name}:
                    return None
                raise

        backend_types = []

        well_log = optional_module("well_log")
        if well_log is not None:
            backend_types.append(getattr(well_log, "WellLogPreviewBackend"))

        seismic = optional_module("seismic")
        if seismic is not None:
            backend_types.append(getattr(seismic, "SeismicPreviewBackend"))

        dat = optional_module("dat")
        if dat is not None:
            backend_types.extend(
                [
                    getattr(dat, "XYScatterBackend"),
                    getattr(dat, "TimeDepthBackend"),
                    getattr(dat, "HorizonSurfaceBackend"),
                ]
            )
            try:
                backend_types.append(getattr(dat, "WellStratificationBackend"))
            except AttributeError:
                pass

        return cls([backend_type() for backend_type in backend_types])

    def supports(self, request: PreviewRequest) -> bool:
        try:
            self._registry.backend_for_request(request)
        except GeoVizError as error:
            if error.code is ErrorCode.UNSUPPORTED:
                return False
            raise
        return True

    def capabilities(self, request: PreviewRequest) -> PreviewCapabilities:
        return self._registry.backend_for_request(request).capabilities(request)

    def prepare(self, request: PreviewRequest, options: PreviewOptions) -> PreparedPreview:
        return self._registry.backend_for_request(request).prepare(request, options)

    def create_widget(self, kind: PreviewKind, parent: QWidget | None = None) -> QWidget:
        _require_ui_thread()
        backend = self._registry.backend_for_kind(kind)
        widget = backend.create_widget(parent)
        self._widget_kinds[widget] = kind
        return widget

    def render(self, widget: QWidget, preview: PreparedPreview) -> None:
        _require_ui_thread()
        self._registry.backend_for_kind(preview.kind).render(widget, preview)

    def release(self, widget: QWidget) -> None:
        _require_ui_thread()
        kind = self._widget_kinds[widget]
        self._registry.backend_for_kind(kind).release(widget)
        del self._widget_kinds[widget]
