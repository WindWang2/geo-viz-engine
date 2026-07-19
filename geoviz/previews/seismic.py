from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QWidget

from geoviz_seismic.loader import SeismicLoader
from geoviz_seismic.models import SeismicVolumeMeta
from geoviz_seismic.preview_widget import (
    SeismicPreviewPayload,
    SeismicSlice,
    axis_specs_from_meta,
    downsample_2d,
    load_preview_slice,
)

from ..contracts import PreparedPreview, PreviewCapabilities, PreviewKind, PreviewOptions, PreviewRequest
from ..errors import ErrorCode, GeoVizError


def _prepare_slices(path: str, limit: int) -> tuple[SeismicPreviewPayload, SeismicVolumeMeta]:
    """Open the SEGY once and read the three middle slices for initial preview."""
    from geoviz_seismic.preview_widget import (
        _read_raw_slice,
        _sample_steps,
        _slice_info,
    )

    loader = SeismicLoader(path)
    try:
        meta = loader.inspect()
        middle_inline = meta.iline_start + (meta.n_inlines // 2) * meta.iline_step
        middle_crossline = meta.xline_start + (meta.n_crosslines // 2) * meta.xline_step
        middle_sample = meta.n_samples // 2

        raw_slices = {
            "inline": (middle_inline, _read_raw_slice(loader, "inline", middle_inline)),
            "crossline": (
                middle_crossline,
                _read_raw_slice(loader, "crossline", middle_crossline),
            ),
            "time": (middle_sample, _read_raw_slice(loader, "time", middle_sample)),
        }
        slices: dict[str, SeismicSlice] = {}
        for mode, (position, display_data) in raw_slices.items():
            row_step, col_step = _sample_steps(display_data, limit)
            slices[mode] = SeismicSlice(
                data=downsample_2d(display_data, limit),
                info=_slice_info(
                    mode,
                    position,
                    display_data,
                    meta,
                    row_step,
                    col_step,
                ),
            )
        payload = SeismicPreviewPayload(
            slices=slices,
            source_path=str(path),
            max_slice_axis=limit,
            axes=axis_specs_from_meta(meta),
        )
        return payload, meta
    finally:
        loader.close()


class SeismicPreviewBackend:
    kind = PreviewKind.SEISMIC_2D

    def supports(self, request: PreviewRequest) -> bool:
        semantic_type = request.semantic_type.strip().lower()
        return request.normalized_format in {"sgy", "segy"} and semantic_type in {
            "",
            "unknown",
            "seismic",
            "seismic_2d",
        }

    def capabilities(self, request: PreviewRequest) -> PreviewCapabilities:
        return PreviewCapabilities(
            self.kind, ("slice_switch", "slice_scrub", "zoom", "pan")
        )

    @staticmethod
    def _show_profiles_only(widget: QWidget) -> None:
        """Keep the preview host in orthogonal-slice mode.

        The full ``SeismicView`` still supports 3-D volume mode in the main app,
        but preview tabs should stay on the 2-D profile surface.
        """
        if hasattr(widget, "set_render_mode"):
            widget.set_render_mode("planes")
            return
        mode_combo = getattr(widget, "_3d_mode_combo", None)
        if mode_combo is not None and hasattr(mode_combo, "setCurrentIndex"):
            mode_combo.setCurrentIndex(0)

    def prepare(self, request: PreviewRequest, options: PreviewOptions) -> PreparedPreview:
        try:
            slice_limit = max(1, min(options.max_slice_axis, 512))
            payload, meta = _prepare_slices(request.path, slice_limit)
        except ValueError as error:
            raise GeoVizError(
                ErrorCode.INVALID_DATA,
                "无法解析 SEGY 地震数据",
                detail=str(error),
            ) from error
        except OSError as error:
            raise GeoVizError(
                ErrorCode.IO_ERROR,
                "无法读取 SEGY 地震数据",
                detail=str(error),
            ) from error

        estimated_bytes = sum(item.data.nbytes for item in payload.slices.values())
        return PreparedPreview(
            kind=self.kind,
            title=request.label or Path(request.path).stem,
            payload=payload,
            summary_rows=(
                ("体尺寸", f"{meta.n_inlines} × {meta.n_crosslines} × {meta.n_samples}"),
                ("采样间隔", f"{meta.dt_ms:g} ms"),
                ("切片", "Inline / Crossline / Time · 可拖动滑条"),
            ),
            estimated_bytes=estimated_bytes,
        )

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        # Import only after the user has activated the visualization tab: the
        # full view imports the 3-D renderer and owns the async SEGY worker.
        from geoviz_seismic import SeismicView

        widget = SeismicView(parent=parent, auto_load=False)
        self._show_profiles_only(widget)
        return widget

    def render(self, widget: QWidget, preview: PreparedPreview) -> None:
        from geoviz_seismic import SeismicView

        payload = preview.payload
        if (
            not isinstance(widget, SeismicView)
            or not isinstance(payload, SeismicPreviewPayload)
            or not payload.source_path
        ):
            raise GeoVizError(ErrorCode.RENDER_ERROR, "无法渲染 SEGY 地震切片")
        widget.load_segy_async(payload.source_path)
        self._show_profiles_only(widget)

    def release(self, widget: QWidget) -> None:
        from geoviz_seismic import SeismicView

        if not isinstance(widget, SeismicView):
            raise GeoVizError(ErrorCode.RENDER_ERROR, "无法释放 SEGY 地震切片")
        widget.cleanup()


__all__ = ["SeismicPreviewBackend", "downsample_2d", "load_preview_slice"]
