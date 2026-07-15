from __future__ import annotations

from typing import Protocol

from PySide6.QtWidgets import QWidget

from .contracts import PreparedPreview, PreviewCapabilities, PreviewKind, PreviewOptions, PreviewRequest
from .errors import ErrorCode, GeoVizError


class PreviewBackend(Protocol):
    kind: PreviewKind

    def supports(self, request: PreviewRequest) -> bool:
        raise NotImplementedError

    def capabilities(self, request: PreviewRequest) -> PreviewCapabilities:
        raise NotImplementedError

    def prepare(self, request: PreviewRequest, options: PreviewOptions) -> PreparedPreview:
        raise NotImplementedError

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        raise NotImplementedError

    def render(self, widget: QWidget, preview: PreparedPreview) -> None:
        raise NotImplementedError

    def release(self, widget: QWidget) -> None:
        raise NotImplementedError


class PreviewRegistry:
    def __init__(self, backends: list[PreviewBackend] | tuple[PreviewBackend, ...] = ()) -> None:
        self._backends = list(backends)

    def backend_for_request(self, request: PreviewRequest) -> PreviewBackend:
        for backend in self._backends:
            if backend.supports(request):
                return backend
        raise GeoVizError(ErrorCode.UNSUPPORTED, f"不支持的可视化格式: {request.normalized_format}")

    def backend_for_kind(self, kind: PreviewKind) -> PreviewBackend:
        for backend in self._backends:
            if backend.kind is kind:
                return backend
        raise GeoVizError(ErrorCode.UNSUPPORTED, f"未注册的预览类型: {kind}")
