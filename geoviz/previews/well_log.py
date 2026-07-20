from __future__ import annotations

from PySide6.QtWidgets import QWidget

from geoviz_well_log import (
    WellLogData,
    WellLogView,
    build_qpainter_tracks,
    load_las_preview,
    load_xml_preview,
)

from ..contracts import PreparedPreview, PreviewCapabilities, PreviewKind, PreviewOptions, PreviewRequest
from ..errors import ErrorCode, GeoVizError


class WellLogPreviewBackend:
    kind = PreviewKind.WELL_LOG

    def supports(self, request: PreviewRequest) -> bool:
        semantic_type = request.semantic_type.strip().lower()
        if semantic_type not in {"", "unknown", "well_log"}:
            return False
        return request.normalized_format in {"las", "xml"}

    def capabilities(self, request: PreviewRequest) -> PreviewCapabilities:
        return PreviewCapabilities(self.kind, ("zoom", "pan"))

    def prepare(self, request: PreviewRequest, options: PreviewOptions) -> PreparedPreview:
        try:
            if request.normalized_format == "xml":
                payload = load_xml_preview(
                    request.path,
                    max_curves=options.max_curves,
                    max_samples=options.max_depth_samples,
                )
            else:
                payload = load_las_preview(
                    request.path,
                    max_curves=options.max_curves,
                    max_samples=options.max_depth_samples,
                )
        except ValueError as error:
            raise GeoVizError(
                ErrorCode.INVALID_DATA,
                "无法解析测井数据",
                detail=str(error),
            ) from error
        except OSError as error:
            raise GeoVizError(
                ErrorCode.IO_ERROR,
                "无法读取测井数据",
                detail=str(error),
            ) from error

        estimated_bytes = max(
            8,
            8 * sum(len(curve.depth) + len(curve.values) for curve in payload.curves),
        )
        return PreparedPreview(
            kind=self.kind,
            title=request.label or payload.well_name,
            payload=payload,
            summary_rows=(
                ("井名", payload.well_name),
                ("深度范围", f"{payload.top_depth:g} – {payload.bottom_depth:g}"),
                ("曲线数", str(len(payload.curves))),
            ),
            estimated_bytes=estimated_bytes,
        )

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        return WellLogView(parent)

    def render(self, widget: QWidget, preview: PreparedPreview) -> None:
        payload = preview.payload
        if not isinstance(widget, WellLogView) or not isinstance(payload, WellLogData):
            raise GeoVizError(ErrorCode.RENDER_ERROR, "无法渲染 LAS 测井数据")
        widget.set_tracks(build_qpainter_tracks(payload))

    def release(self, widget: QWidget) -> None:
        if not isinstance(widget, WellLogView):
            raise GeoVizError(ErrorCode.RENDER_ERROR, "无法释放 LAS 测井画布")
        widget.set_tracks([])


__all__ = ["WellLogPreviewBackend"]
