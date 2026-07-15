from __future__ import annotations

from weakref import WeakKeyDictionary

from PySide6.QtWidgets import QWidget

from .contracts import PreparedPreview, PreviewCapabilities, PreviewKind, PreviewOptions, PreviewRequest
from .errors import ErrorCode, GeoVizError
from .registry import PreviewBackend, PreviewRegistry


class GeoVizEngine:
    def __init__(self, backends: list[PreviewBackend] | tuple[PreviewBackend, ...] = ()) -> None:
        self._registry = PreviewRegistry(backends)
        self._widget_kinds: WeakKeyDictionary[QWidget, PreviewKind] = WeakKeyDictionary()

    @classmethod
    def default(cls) -> "GeoVizEngine":
        return cls()

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
        backend = self._registry.backend_for_kind(kind)
        widget = backend.create_widget(parent)
        self._widget_kinds[widget] = kind
        return widget

    def render(self, widget: QWidget, preview: PreparedPreview) -> None:
        self._registry.backend_for_kind(preview.kind).render(widget, preview)

    def release(self, widget: QWidget) -> None:
        kind = self._widget_kinds[widget]
        self._registry.backend_for_kind(kind).release(widget)
        del self._widget_kinds[widget]
