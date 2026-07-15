from __future__ import annotations

import math
import shlex
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PySide6.QtWidgets import QWidget

from geoviz_plots import (
    LineSeries,
    PlotWidget,
    ScatterSeries,
    SurfaceWidget,
    interpolate_idw,
)

from ..contracts import PreparedPreview, PreviewCapabilities, PreviewKind, PreviewOptions, PreviewRequest
from ..errors import ErrorCode, GeoVizError


_SCHEMA_ERROR = "DAT 数据结构与资源类型不匹配"
_WELL_HEAD_MARKER = "WellHead File From SMI"
_HORIZON_MARKER = "XYZInlineCrossline"
_TIME_DEPTH_MARKER = "TimeDepth File From SMI"
_MAX_POINTS = 50_000
_MAX_SURFACE_AXIS = 256
_MAX_IDW_POINT_CELLS = 8_000_000


@dataclass(frozen=True)
class XYPreviewPayload:
    names: tuple[str, ...]
    x: np.ndarray
    y: np.ndarray


@dataclass(frozen=True)
class TimeDepthPreviewPayload:
    depth: np.ndarray
    time_ms: np.ndarray


@dataclass(frozen=True)
class SurfacePreviewPayload:
    grid_x: np.ndarray
    grid_y: np.ndarray
    grid_z: np.ndarray
    levels: tuple[float, ...]


class _DatSchemaError(ValueError):
    pass


def representative_indices(length: int, limit: int) -> np.ndarray:
    if length <= limit:
        return np.arange(length, dtype=np.int64)
    return np.linspace(0, length - 1, num=limit, dtype=np.int64)


def _normalized_semantic_type(request: PreviewRequest) -> str:
    return request.semantic_type.strip().lower()


def _read_header(path: str) -> tuple[str, ...]:
    header = []
    with open(path, "r", encoding="utf-8-sig") as stream:
        for raw_line in stream:
            line = raw_line.strip()
            if not line:
                continue
            if not line.startswith("#"):
                break
            header.append(line)
    return tuple(header)


def _header_tokens(line: str) -> tuple[str, ...]:
    try:
        return tuple(shlex.split(line.lstrip("#").strip()))
    except ValueError as error:
        raise _DatSchemaError(str(error)) from error


def _normalized_column(column: str) -> str:
    return "".join(character for character in column.casefold() if character.isalnum())


def _column_mapping(
    header: tuple[str, ...],
    aliases: dict[str, frozenset[str]],
    *,
    allowed_extras: frozenset[str] = frozenset(),
    row_width: int | None = None,
) -> dict[str, int] | None:
    if not header:
        return None
    tokens = _header_tokens(header[-1])
    if row_width is not None and len(tokens) != row_width:
        return None
    normalized = tuple(_normalized_column(token) for token in tokens)
    allowed_columns = allowed_extras.union(*(names for names in aliases.values()))
    if not normalized or any(column not in allowed_columns for column in normalized):
        return None
    mapping = {}
    for registered_name, accepted_names in aliases.items():
        matches = [
            index for index, column in enumerate(normalized) if column in accepted_names
        ]
        if len(matches) == 1:
            mapping[registered_name] = matches[0]
    if len(mapping) == len(aliases) and len(set(mapping.values())) == len(mapping):
        return mapping
    return None


_WELL_HEAD_COLUMNS = {
    "name": frozenset({"name", "well", "wellname"}),
    "x": frozenset({"x"}),
    "y": frozenset({"y"}),
}
_WELL_HEAD_EXTRA_COLUMNS = frozenset({"datum", "elevation", "gl", "kb", "td", "uwi"})
_HORIZON_COLUMNS = {
    "x": frozenset({"x"}),
    "y": frozenset({"y"}),
    "z": frozenset({"z"}),
}
_HORIZON_EXTRA_COLUMNS = frozenset({"crossline", "iline", "inline", "xline"})
_TIME_DEPTH_COLUMNS = {
    "depth": frozenset({"depth"}),
    "time": frozenset({"timems"}),
}
_TIME_DEPTH_EXTRA_COLUMNS = frozenset({"name", "velocity", "well", "wellname"})


def supports_well_head(request: PreviewRequest, header: tuple[str, ...]) -> bool:
    return (
        request.normalized_format == "dat"
        and _normalized_semantic_type(request) == "well_head"
        and any(_WELL_HEAD_MARKER in line for line in header)
    )


def supports_horizon(request: PreviewRequest, header: tuple[str, ...]) -> bool:
    return (
        request.normalized_format == "dat"
        and _normalized_semantic_type(request) == "horizon"
        and any(_HORIZON_MARKER in line for line in header)
    )


def supports_time_depth(request: PreviewRequest, header: tuple[str, ...]) -> bool:
    if request.normalized_format != "dat" or _normalized_semantic_type(request) != "time_depth":
        return False
    if any(_TIME_DEPTH_MARKER in line for line in header):
        return True
    return _column_mapping(
        header,
        _TIME_DEPTH_COLUMNS,
        allowed_extras=_TIME_DEPTH_EXTRA_COLUMNS,
    ) is not None


def _supports_with_header(request: PreviewRequest, predicate) -> bool:
    try:
        header = _read_header(request.path)
        return predicate(request, header)
    except (OSError, UnicodeError, _DatSchemaError):
        return False


def _split_data_line(line: str) -> tuple[str, ...]:
    try:
        return tuple(shlex.split(line))
    except ValueError as error:
        raise _DatSchemaError(str(error)) from error


def _scan_dat(path: str) -> tuple[tuple[str, ...], int, int]:
    header = []
    row_count = 0
    row_width = 0
    with open(path, "r", encoding="utf-8-sig") as stream:
        for raw_line in stream:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                header.append(line)
                continue
            row = _split_data_line(line)
            if not row:
                continue
            if row_width == 0:
                row_width = len(row)
            elif len(row) != row_width:
                raise _DatSchemaError("inconsistent row width")
            row_count += 1
    if row_count == 0:
        raise _DatSchemaError("no data rows")
    return tuple(header), row_count, row_width


def _iter_rows(path: str):
    with open(path, "r", encoding="utf-8-sig") as stream:
        for raw_line in stream:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            row = _split_data_line(line)
            if row:
                yield row


def _selected_rows(path: str, indices: np.ndarray, parse_row) -> list[tuple]:
    selected = []
    selected_position = 0
    for row_index, row in enumerate(_iter_rows(path)):
        parsed = parse_row(row)
        if selected_position < len(indices) and row_index == indices[selected_position]:
            selected.append(parsed)
            selected_position += 1
    if selected_position != len(indices):
        raise _DatSchemaError("row count changed while reading")
    return selected


def _finite_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise _DatSchemaError(f"not numeric: {value}") from error
    if not math.isfinite(parsed):
        raise _DatSchemaError(f"not finite: {value}")
    return parsed


def _value_at(row: tuple[str, ...], index: int) -> str:
    try:
        return row[index]
    except IndexError as error:
        raise _DatSchemaError("row has too few columns") from error


def _sample_limit(options: PreviewOptions) -> int:
    return max(1, min(int(options.max_points), _MAX_POINTS))


def _prepare_error(error: Exception) -> GeoVizError:
    if isinstance(error, OSError):
        return GeoVizError(ErrorCode.IO_ERROR, "无法读取 DAT 数据", detail=str(error))
    return GeoVizError(ErrorCode.INVALID_DATA, _SCHEMA_ERROR, detail=str(error))


def _well_head_payload(path: str, options: PreviewOptions) -> XYPreviewPayload:
    header, row_count, row_width = _scan_dat(path)
    if not any(_WELL_HEAD_MARKER in line for line in header):
        raise _DatSchemaError("missing well-head marker")
    mapping = _column_mapping(
        header,
        _WELL_HEAD_COLUMNS,
        allowed_extras=_WELL_HEAD_EXTRA_COLUMNS,
        row_width=row_width,
    ) or {"name": 0, "x": 1, "y": 2}

    def parse_row(row):
        name = _value_at(row, mapping["name"])
        if not name:
            raise _DatSchemaError("empty well name")
        return (
            name,
            _finite_float(_value_at(row, mapping["x"])),
            _finite_float(_value_at(row, mapping["y"])),
        )

    indices = representative_indices(row_count, _sample_limit(options))
    selected = _selected_rows(path, indices, parse_row)
    return XYPreviewPayload(
        names=tuple(row[0] for row in selected),
        x=np.ascontiguousarray([row[1] for row in selected], dtype=np.float64),
        y=np.ascontiguousarray([row[2] for row in selected], dtype=np.float64),
    )


def _time_depth_payload(path: str, options: PreviewOptions) -> TimeDepthPreviewPayload:
    header, row_count, row_width = _scan_dat(path)
    mapping = _column_mapping(
        header,
        _TIME_DEPTH_COLUMNS,
        allowed_extras=_TIME_DEPTH_EXTRA_COLUMNS,
        row_width=row_width,
    )
    if mapping is None:
        raise _DatSchemaError("missing registered depth/time columns")

    def parse_row(row):
        return (
            _finite_float(_value_at(row, mapping["depth"])),
            _finite_float(_value_at(row, mapping["time"])),
        )

    indices = representative_indices(row_count, _sample_limit(options))
    selected = _selected_rows(path, indices, parse_row)
    depth = np.asarray([row[0] for row in selected], dtype=np.float64)
    time_ms = np.asarray([row[1] for row in selected], dtype=np.float64)
    order = np.argsort(depth, kind="stable")
    return TimeDepthPreviewPayload(
        depth=np.ascontiguousarray(depth[order]),
        time_ms=np.ascontiguousarray(time_ms[order]),
    )


def _surface_payload(path: str, options: PreviewOptions) -> SurfacePreviewPayload:
    header, row_count, row_width = _scan_dat(path)
    if not any(_HORIZON_MARKER in line for line in header):
        raise _DatSchemaError("missing horizon marker")
    mapping = _column_mapping(
        header,
        _HORIZON_COLUMNS,
        allowed_extras=_HORIZON_EXTRA_COLUMNS,
        row_width=row_width,
    ) or {"x": 0, "y": 1, "z": 2}

    def parse_row(row):
        return (
            _finite_float(_value_at(row, mapping["x"])),
            _finite_float(_value_at(row, mapping["y"])),
            _finite_float(_value_at(row, mapping["z"])),
        )

    source_indices = representative_indices(row_count, _sample_limit(options))
    selected = _selected_rows(path, source_indices, parse_row)
    source_x = np.asarray([row[0] for row in selected], dtype=np.float64)
    source_y = np.asarray([row[1] for row in selected], dtype=np.float64)
    source_z = np.asarray([row[2] for row in selected], dtype=np.float64)
    axis_limit = max(1, min(int(options.surface_grid_size), _MAX_SURFACE_AXIS))
    axis_size = min(axis_limit, max(2, math.ceil(math.sqrt(len(source_indices)))))
    grid_x = np.linspace(float(source_x.min()), float(source_x.max()), num=axis_size)
    grid_y = np.linspace(float(source_y.min()), float(source_y.max()), num=axis_size)

    grid_cells = len(grid_x) * len(grid_y)
    interpolation_limit = max(1, _MAX_IDW_POINT_CELLS // grid_cells)
    interpolation_indices = representative_indices(
        len(selected), min(len(selected), interpolation_limit)
    )
    grid_z = interpolate_idw(
        source_x[interpolation_indices],
        source_y[interpolation_indices],
        source_z[interpolation_indices],
        grid_x,
        grid_y,
    )
    finite_z = grid_z[np.isfinite(grid_z)]
    if finite_z.size == 0:
        raise _DatSchemaError("surface interpolation produced no finite values")
    levels_array = np.linspace(float(finite_z.min()), float(finite_z.max()), num=10)
    return SurfacePreviewPayload(
        grid_x=np.ascontiguousarray(grid_x, dtype=np.float64),
        grid_y=np.ascontiguousarray(grid_y, dtype=np.float64),
        grid_z=np.ascontiguousarray(grid_z, dtype=np.float64),
        levels=tuple(float(level) for level in levels_array),
    )


class XYScatterBackend:
    kind = PreviewKind.XY_SCATTER

    def supports(self, request: PreviewRequest) -> bool:
        return _supports_with_header(request, supports_well_head)

    def capabilities(self, request: PreviewRequest) -> PreviewCapabilities:
        return PreviewCapabilities(self.kind, ("zoom", "pan"))

    def prepare(self, request: PreviewRequest, options: PreviewOptions) -> PreparedPreview:
        try:
            payload = _well_head_payload(request.path, options)
        except (OSError, UnicodeError, _DatSchemaError) as error:
            raise _prepare_error(error) from error
        return PreparedPreview(
            kind=self.kind,
            title=request.label or Path(request.path).stem,
            payload=payload,
            summary_rows=(("井数", str(len(payload.names))),),
            estimated_bytes=payload.x.nbytes
            + payload.y.nbytes
            + sum(len(name.encode("utf-8")) for name in payload.names),
        )

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        return PlotWidget(parent)

    def render(self, widget: QWidget, preview: PreparedPreview) -> None:
        if not isinstance(widget, PlotWidget) or not isinstance(preview.payload, XYPreviewPayload):
            raise GeoVizError(ErrorCode.RENDER_ERROR, "无法渲染井位散点数据")
        widget.clear()
        widget.add_series(ScatterSeries(preview.payload.x, preview.payload.y, name=preview.title))
        widget.autofit()

    def release(self, widget: QWidget) -> None:
        if not isinstance(widget, PlotWidget):
            raise GeoVizError(ErrorCode.RENDER_ERROR, "无法释放井位散点画布")
        widget.clear()


class TimeDepthBackend:
    kind = PreviewKind.TIME_DEPTH

    def supports(self, request: PreviewRequest) -> bool:
        return _supports_with_header(request, supports_time_depth)

    def capabilities(self, request: PreviewRequest) -> PreviewCapabilities:
        return PreviewCapabilities(self.kind, ("zoom", "pan"))

    def prepare(self, request: PreviewRequest, options: PreviewOptions) -> PreparedPreview:
        try:
            payload = _time_depth_payload(request.path, options)
        except (OSError, UnicodeError, _DatSchemaError) as error:
            raise _prepare_error(error) from error
        return PreparedPreview(
            kind=self.kind,
            title=request.label or Path(request.path).stem,
            payload=payload,
            summary_rows=(("采样点", str(len(payload.depth))),),
            estimated_bytes=payload.depth.nbytes + payload.time_ms.nbytes,
        )

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        return PlotWidget(parent)

    def render(self, widget: QWidget, preview: PreparedPreview) -> None:
        if not isinstance(widget, PlotWidget) or not isinstance(
            preview.payload, TimeDepthPreviewPayload
        ):
            raise GeoVizError(ErrorCode.RENDER_ERROR, "无法渲染时深数据")
        widget.clear()
        widget.add_series(
            LineSeries(preview.payload.time_ms, preview.payload.depth, name=preview.title)
        )
        widget.autofit()

    def release(self, widget: QWidget) -> None:
        if not isinstance(widget, PlotWidget):
            raise GeoVizError(ErrorCode.RENDER_ERROR, "无法释放时深画布")
        widget.clear()


class HorizonSurfaceBackend:
    kind = PreviewKind.SURFACE

    def supports(self, request: PreviewRequest) -> bool:
        return _supports_with_header(request, supports_horizon)

    def capabilities(self, request: PreviewRequest) -> PreviewCapabilities:
        return PreviewCapabilities(self.kind, ("zoom", "pan", "contour_select"))

    def prepare(self, request: PreviewRequest, options: PreviewOptions) -> PreparedPreview:
        try:
            payload = _surface_payload(request.path, options)
        except (OSError, UnicodeError, _DatSchemaError) as error:
            raise _prepare_error(error) from error
        estimated_bytes = (
            payload.grid_x.nbytes
            + payload.grid_y.nbytes
            + payload.grid_z.nbytes
            + 8 * len(payload.levels)
        )
        return PreparedPreview(
            kind=self.kind,
            title=request.label or Path(request.path).stem,
            payload=payload,
            summary_rows=(("网格", f"{len(payload.grid_x)} × {len(payload.grid_y)}"),),
            estimated_bytes=estimated_bytes,
        )

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        return SurfaceWidget(parent)

    def render(self, widget: QWidget, preview: PreparedPreview) -> None:
        if not isinstance(widget, SurfaceWidget) or not isinstance(
            preview.payload, SurfacePreviewPayload
        ):
            raise GeoVizError(ErrorCode.RENDER_ERROR, "无法渲染层面数据")
        payload = preview.payload
        widget.set_grid_data(payload.grid_x, payload.grid_y, payload.grid_z, payload.levels)
        widget.autofit()

    def release(self, widget: QWidget) -> None:
        if not isinstance(widget, SurfaceWidget):
            raise GeoVizError(ErrorCode.RENDER_ERROR, "无法释放层面画布")
        widget.clear()


__all__ = [
    "HorizonSurfaceBackend",
    "SurfacePreviewPayload",
    "TimeDepthBackend",
    "TimeDepthPreviewPayload",
    "XYPreviewPayload",
    "XYScatterBackend",
    "representative_indices",
    "supports_horizon",
    "supports_time_depth",
    "supports_well_head",
]
