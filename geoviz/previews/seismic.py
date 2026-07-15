from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PySide6.QtWidgets import QWidget

from geoviz_seismic.loader import SeismicLoader
from geoviz_seismic.models import SeismicVolumeMeta, SliceInfo
from geoviz_seismic.preview_widget import (
    SeismicPreviewPayload,
    SeismicPreviewWidget,
    SeismicSlice,
)

from ..contracts import PreparedPreview, PreviewCapabilities, PreviewKind, PreviewOptions, PreviewRequest
from ..errors import ErrorCode, GeoVizError


def downsample_2d(data: np.ndarray, limit: int) -> np.ndarray:
    row_step = max(1, math.ceil(data.shape[0] / limit))
    col_step = max(1, math.ceil(data.shape[1] / limit))
    return np.ascontiguousarray(data[::row_step, ::col_step], dtype=np.float32)


def _sample_steps(data: np.ndarray, limit: int) -> tuple[int, int]:
    return (
        max(1, math.ceil(data.shape[0] / limit)),
        max(1, math.ceil(data.shape[1] / limit)),
    )


def _slice_info(
    mode: str,
    position: int,
    display_data: np.ndarray,
    meta: SeismicVolumeMeta,
    row_step: int,
    col_step: int,
) -> SliceInfo:
    if mode == "inline":
        horizontal = meta.xline_start + np.arange(display_data.shape[1]) * meta.xline_step
        vertical = meta.t0_ms + np.arange(display_data.shape[0]) * meta.dt_ms
        horizontal_label, vertical_label = "Crossline", "Time (ms)"
    elif mode == "crossline":
        horizontal = meta.iline_start + np.arange(display_data.shape[1]) * meta.iline_step
        vertical = meta.t0_ms + np.arange(display_data.shape[0]) * meta.dt_ms
        horizontal_label, vertical_label = "Inline", "Time (ms)"
    else:
        horizontal = meta.iline_start + np.arange(display_data.shape[1]) * meta.iline_step
        vertical = meta.xline_start + np.arange(display_data.shape[0]) * meta.xline_step
        horizontal_label, vertical_label = "Inline", "Crossline"

    return SliceInfo(
        slice_type=mode,
        position=position,
        axis_h_label=horizontal_label,
        axis_v_label=vertical_label,
        axis_h_values=horizontal[::col_step].astype(float).tolist(),
        axis_v_values=vertical[::row_step].astype(float).tolist(),
    )


def _prepare_slices(path: str, limit: int) -> tuple[SeismicPreviewPayload, SeismicVolumeMeta]:
    loader = SeismicLoader(path)
    try:
        meta = loader.inspect()
        middle_inline = meta.iline_start + (meta.n_inlines // 2) * meta.iline_step
        middle_crossline = meta.xline_start + (meta.n_crosslines // 2) * meta.xline_step
        middle_sample = meta.n_samples // 2

        raw_slices = {
            "inline": (middle_inline, loader.read_inline(middle_inline).T),
            "crossline": (middle_crossline, loader.read_crossline(middle_crossline).T),
            "time": (middle_sample, loader.read_timeslice(middle_sample).T),
        }
        slices = {}
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
        return SeismicPreviewPayload(slices=slices), meta
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
        return PreviewCapabilities(self.kind, ("slice_switch", "zoom", "pan"))

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
                ("切片", "Inline / Crossline / Time"),
            ),
            estimated_bytes=estimated_bytes,
        )

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        return SeismicPreviewWidget(parent)

    def render(self, widget: QWidget, preview: PreparedPreview) -> None:
        if not isinstance(widget, SeismicPreviewWidget) or not isinstance(
            preview.payload, SeismicPreviewPayload
        ):
            raise GeoVizError(ErrorCode.RENDER_ERROR, "无法渲染 SEGY 地震切片")
        widget.set_slices(preview.payload)

    def release(self, widget: QWidget) -> None:
        if not isinstance(widget, SeismicPreviewWidget):
            raise GeoVizError(ErrorCode.RENDER_ERROR, "无法释放 SEGY 地震切片")
        widget.clear()


__all__ = ["SeismicPreviewBackend", "downsample_2d"]
