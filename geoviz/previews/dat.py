from __future__ import annotations

import math
import re
import shlex
import sys
from dataclasses import dataclass, field
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
from geoviz_cross_well import FormationTop, FormationTopsPreviewWidget

from ..contracts import PreparedPreview, PreviewCapabilities, PreviewKind, PreviewOptions, PreviewRequest
from ..errors import ErrorCode, GeoVizError


_SCHEMA_ERROR = "DAT 数据结构与资源类型不匹配"
_WELL_HEAD_MARKER = "WellHead File From SMI"
_HORIZON_MARKER = "XYZInlineCrossline"
_TIME_DEPTH_MARKER = "TimeDepth File From SMI"
_WELL_TOPS_MARKER_LINE = "#WellTops File From SMI"
_WELL_TOPS_COLUMNS = (
    "WellName",
    "Name",
    "MD",
    "X",
    "Y",
    "Z",
    "TVD",
    "Time(ms)",
)
_MAX_POINTS = 50_000
_MAX_SURFACE_AXIS = 256
_MAX_IDW_POINT_CELLS = 8_000_000
_MAX_HEADER_LINES = 256
_MAX_HEADER_CHARS = 64 * 1_024


@dataclass(frozen=True)
class PreviewRowIssue:
    source_row: int
    reason: str


@dataclass(frozen=True)
class XYPreviewDiagnostics:
    total_records: int = 0
    valid_records: int = 0
    issues: tuple[PreviewRowIssue, ...] = ()
    omitted_issue_count: int = 0

    @property
    def skipped_count(self) -> int:
        return self.total_records - self.valid_records


@dataclass(frozen=True)
class SourceCoordinateStatus:
    """Explicit metadata facts used to judge an XY preview's trust context."""

    source_crs_provenance: str = "undeclared"
    coordinate_units_provenance: str = "unknown"
    comparison_crs: str = ""
    comparison_matches_source: bool | None = None

    @property
    def comparison_mismatch(self) -> bool:
        return self.comparison_matches_source is False


@dataclass(frozen=True)
class XYPreviewPayload:
    names: tuple[str, ...]
    x: np.ndarray
    y: np.ndarray
    resource_id: str = ""
    record_ids: tuple[int, ...] = ()
    source_rows: tuple[int, ...] = ()
    source_version: str = ""
    source_crs: str = ""
    coordinate_units: str = ""
    coordinate_status: SourceCoordinateStatus = field(
        default_factory=SourceCoordinateStatus
    )
    diagnostics: XYPreviewDiagnostics = field(
        default_factory=XYPreviewDiagnostics
    )
    # Optional per-row extra identity surfaced by the well-head backend when
    # the file declares a ``UWI`` column; empty tuple otherwise.  Aligned
    # with ``names`` (one entry per valid record).
    uwis: tuple[str, ...] = ()


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


class _WellResourceLimitError(_DatSchemaError):
    pass


def representative_indices(length: int, limit: int) -> np.ndarray:
    if length <= limit:
        return np.arange(length, dtype=np.int64)
    return np.linspace(0, length - 1, num=limit, dtype=np.int64)


def _normalized_semantic_type(request: PreviewRequest) -> str:
    return request.semantic_type.strip().lower()


def _read_header(path: str) -> tuple[str, ...]:
    header = []
    header_chars = 0
    with open(path, "r", encoding="utf-8-sig") as stream:
        for raw_line in stream:
            line = raw_line.strip()
            if not line:
                continue
            if not line.startswith("#"):
                break
            header_chars = _retain_header_line(header, header_chars, line)
    return tuple(header)


def _header_tokens(line: str) -> tuple[str, ...]:
    if line.count('"') % 2:
        raise _DatSchemaError("unclosed double quote in header")
    return tuple(line.lstrip("#").strip().split())


def _retain_header_line(header: list[str], header_chars: int, line: str) -> int:
    if len(header) >= _MAX_HEADER_LINES or header_chars + len(line) > _MAX_HEADER_CHARS:
        return header_chars
    header.append(line)
    return header_chars + len(line)


def _normalized_column(column: str) -> str:
    column = column.casefold().replace("'", "prime")
    return "".join(character for character in column if character.isalnum())


def _column_mapping(
    header: tuple[str, ...],
    aliases: dict[str, frozenset[str]],
    *,
    allowed_extras: frozenset[str] = frozenset(),
    row_width: int | None = None,
) -> dict[str, int] | None:
    allowed_columns = allowed_extras.union(*(names for names in aliases.values()))
    candidates = []
    for line in header:
        tokens = _header_tokens(line)
        if row_width is not None and len(tokens) != row_width:
            continue
        normalized = tuple(_normalized_column(token) for token in tokens)
        if not normalized or any(column not in allowed_columns for column in normalized):
            continue
        mapping = {}
        for registered_name, accepted_names in aliases.items():
            matches = [
                index for index, column in enumerate(normalized) if column in accepted_names
            ]
            if len(matches) == 1:
                mapping[registered_name] = matches[0]
        if len(mapping) == len(aliases) and len(set(mapping.values())) == len(mapping):
            candidates.append(mapping)
    if not candidates or any(candidate != candidates[0] for candidate in candidates[1:]):
        return None
    return candidates[0]


_WELL_HEAD_COLUMNS = {
    "name": frozenset({"name", "well", "wellname"}),
    "x": frozenset({"x"}),
    "y": frozenset({"y"}),
}
_WELL_HEAD_EXTRA_COLUMNS = frozenset(
    {
        "bottomx",
        "bottomy",
        "datum",
        "elevation",
        "gl",
        "kb",
        "td",
        "totaldepth",
        "uwi",
        "welltype",
    }
)
_TIME_DEPTH_COLUMNS = {
    "depth": frozenset({"depth"}),
    "time": frozenset({"timems"}),
}
_TIME_DEPTH_EXTRA_COLUMNS = frozenset({"name", "velocity", "well", "wellname"})
_SMI_TIME_DEPTH_FIELDS = frozenset({"time", "tvdss", "tvd", "md", "tvdprime", "well"})
_DEPTH_FIELD_PRIORITY = ("md", "tvd", "tvdss", "tvdprime")
_MILLISECOND_UNITS = frozenset({"ms", "msec", "millisecond", "milliseconds"})
_LENGTH_UNITS = frozenset({"m", "meter", "meters", "ft", "feet"})


def _horizon_field_mapping(header: tuple[str, ...], row_width: int) -> dict[str, int]:
    mapping = {}
    used_indices = set()
    for line in header:
        tokens = _header_tokens(line)
        if len(tokens) < 3 or tokens[0].casefold() != "field:":
            continue
        try:
            index = int(tokens[1]) - 1
        except ValueError as error:
            raise _DatSchemaError("invalid horizon field index") from error
        name = _normalized_column(tokens[2])
        if name not in {"x", "y", "z"}:
            continue
        if name in mapping or index in used_indices or not 0 <= index < row_width:
            raise _DatSchemaError("ambiguous horizon field mapping")
        mapping[name] = index
        used_indices.add(index)
    if set(mapping) != {"x", "y", "z"}:
        raise _DatSchemaError("missing horizon field mapping")
    return mapping


def _unit_declarations(header: tuple[str, ...]) -> dict[str, str]:
    units = {}
    for line in header:
        tokens = _header_tokens(line)
        if len(tokens) != 2 or not tokens[1].startswith("."):
            continue
        field = _normalized_column(tokens[0])
        unit = _normalized_column(tokens[1].lstrip("."))
        if field in units and units[field] != unit:
            raise _DatSchemaError("conflicting field units")
        units[field] = unit
    return units


def _source_crs_declaration(header: tuple[str, ...]) -> str:
    declarations = []
    for line in header:
        body = line.lstrip("#").strip()
        if ":" not in body:
            continue
        key, value = body.split(":", 1)
        if _normalized_column(key) not in {"crs", "sourcecrs"}:
            continue
        value = value.strip()
        if not value:
            raise _DatSchemaError("empty SourceCRS declaration")
        declarations.append(value)
    if not declarations:
        return ""
    if any(
        not _same_explicit_crs(declaration, declarations[0])
        for declaration in declarations[1:]
    ):
        raise _DatSchemaError("conflicting SourceCRS declarations")
    return declarations[0]


def _canonical_explicit_crs(value: str) -> str:
    """Normalize only explicit CRS syntax; never infer from coordinate values."""
    normalized = " ".join(value.casefold().split())
    match = re.search(r"\bepsg\s*:\s*(\d+)\b", normalized)
    return f"epsg:{match.group(1)}" if match else normalized


def _same_explicit_crs(left: str, right: str) -> bool:
    return _canonical_explicit_crs(left) == _canonical_explicit_crs(right)


def _merge_declared_metadata(
    explicit: str,
    declared: str,
    *,
    name: str,
) -> str:
    explicit = explicit.strip()
    declared = declared.strip()
    if (
        explicit
        and declared
        and not _same_explicit_crs(explicit, declared)
    ):
        raise _DatSchemaError(f"conflicting {name} declarations")
    return explicit or declared


def _metadata_provenance(explicit: str, declared: str, *, missing: str) -> str:
    if explicit and declared:
        return "asset+file"
    if explicit:
        return "asset"
    if declared:
        return "file"
    return missing


def _registered_depth_type(header: tuple[str, ...]) -> str | None:
    for line in header:
        body = line.lstrip("#").strip()
        if ":" not in body:
            continue
        key, value = body.split(":", 1)
        if _normalized_column(key) not in {"depth", "depthtype"}:
            continue
        tokens = value.split()
        if len(tokens) != 1:
            raise _DatSchemaError("invalid depth type metadata")
        return _normalized_column(tokens[0])
    return None


def _smi_time_depth_mapping(
    header: tuple[str, ...], row_width: int
) -> dict[str, int] | None:
    if not any(_TIME_DEPTH_MARKER in line for line in header):
        return None
    candidates = []
    for line in header:
        tokens = _header_tokens(line)
        if len(tokens) != row_width:
            continue
        fields = tuple(_normalized_column(token) for token in tokens)
        if all(field in _SMI_TIME_DEPTH_FIELDS for field in fields) and fields.count("time") == 1:
            candidates.append(fields)
    if len(candidates) != 1:
        raise _DatSchemaError("missing or ambiguous time-depth field declaration")

    fields = candidates[0]
    units = _unit_declarations(header)
    if units.get("time") not in _MILLISECOND_UNITS:
        raise _DatSchemaError("TIME is not registered in milliseconds")

    requested_depth = _registered_depth_type(header)
    if requested_depth is not None:
        depth_fields = (requested_depth,)
    else:
        depth_fields = _DEPTH_FIELD_PRIORITY
    depth_field = next(
        (
            field
            for field in depth_fields
            if field in fields and units.get(field) in _LENGTH_UNITS
        ),
        None,
    )
    if depth_field is None:
        raise _DatSchemaError("no registered depth field")
    return {"time": fields.index("time"), "depth": fields.index(depth_field)}


def _time_depth_mapping(header: tuple[str, ...], row_width: int) -> dict[str, int]:
    direct = _column_mapping(
        header,
        _TIME_DEPTH_COLUMNS,
        allowed_extras=_TIME_DEPTH_EXTRA_COLUMNS,
        row_width=row_width,
    )
    if direct is not None:
        return direct
    smi = _smi_time_depth_mapping(header, row_width)
    if smi is None:
        raise _DatSchemaError("missing registered depth/time columns")
    return smi


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


def _has_exact_well_tops_schema(header: tuple[str, ...]) -> bool:
    if header.count(_WELL_TOPS_MARKER_LINE) != 1:
        return False
    return sum(_header_tokens(line) == _WELL_TOPS_COLUMNS for line in header) == 1


def supports_well_stratification(
    request: PreviewRequest, header: tuple[str, ...]
) -> bool:
    return (
        request.normalized_format == "dat"
        and _normalized_semantic_type(request) == "well_stratification"
        and _has_exact_well_tops_schema(header)
    )


def _supports_with_header(request: PreviewRequest, predicate) -> bool:
    try:
        header = _read_header(request.path)
        return predicate(request, header)
    except (OSError, UnicodeError, _DatSchemaError):
        return False


def _split_data_line(line: str) -> tuple[str, ...]:
    if '"' not in line and "'" not in line:
        return tuple(line.split())
    try:
        return tuple(shlex.split(line))
    except ValueError as error:
        raise _DatSchemaError(str(error)) from error


def _read_dat_data_lines(path: str) -> tuple[tuple[str, ...], list[str]]:
    """Single pass: collect header comments and raw data lines (no split/parse)."""
    header = []
    header_chars = 0
    data_lines: list[str] = []
    with open(path, "r", encoding="utf-8-sig") as stream:
        for raw_line in stream:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                header_chars = _retain_header_line(header, header_chars, line)
                continue
            data_lines.append(line)
    if not data_lines:
        raise _DatSchemaError("no data rows")
    return tuple(header), data_lines


def _parse_selected_lines(data_lines: list[str], indices: np.ndarray, parse_row) -> list[tuple]:
    selected = []
    row_width = 0
    for index in indices:
        row = _split_data_line(data_lines[int(index)])
        if not row:
            raise _DatSchemaError("row count changed while reading")
        if row_width == 0:
            row_width = len(row)
        elif len(row) != row_width:
            raise _DatSchemaError("inconsistent row width")
        selected.append(parse_row(row))
    return selected


def _scan_dat(path: str) -> tuple[tuple[str, ...], int, int]:
    header = []
    header_chars = 0
    row_count = 0
    row_width = 0
    with open(path, "r", encoding="utf-8-sig") as stream:
        for raw_line in stream:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                header_chars = _retain_header_line(header, header_chars, line)
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


def _iter_rows_with_source(path: str):
    record_id = 0
    with open(path, "r", encoding="utf-8-sig") as stream:
        for source_row, raw_line in enumerate(stream, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            row = _split_data_line(line)
            if row:
                yield record_id, source_row, row
                record_id += 1


def _iter_data_lines_with_source(path: str):
    with open(path, "r", encoding="utf-8-sig") as stream:
        for source_row, raw_line in enumerate(stream, start=1):
            line = raw_line.strip()
            if line and not line.startswith("#"):
                yield source_row, line


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


def _well_head_payload(
    path: str,
    _options: PreviewOptions,
    *,
    resource_id: str = "",
    source_version: str = "",
    source_crs: str = "",
    coordinate_units: str = "",
    comparison_crs: str = "",
) -> XYPreviewPayload:
    header = _read_header(path)
    if not any(_WELL_HEAD_MARKER in line for line in header):
        raise _DatSchemaError("missing well-head marker")
    mapping = _column_mapping(
        header,
        _WELL_HEAD_COLUMNS,
        allowed_extras=_WELL_HEAD_EXTRA_COLUMNS,
    )
    if mapping is None:
        raise _DatSchemaError("missing required Name/X/Y columns")
    declaration_widths = {
        len(tokens)
        for line in header
        if (tokens := _header_tokens(line))
        and set(mapping.values()).issubset(range(len(tokens)))
        and all(
            _normalized_column(token)
            in _WELL_HEAD_EXTRA_COLUMNS.union(
                *(_WELL_HEAD_COLUMNS.values())
            )
            for token in tokens
        )
    }
    if len(declaration_widths) != 1:
        raise _DatSchemaError("ambiguous well-head column width")
    row_width = declaration_widths.pop()

    # Optional UWI column: extras are allowed by ``_column_mapping`` but not
    # returned, so locate a single unambiguous ``uwi`` token among the
    # declared-width header lines.  The marker line can share the declared
    # width, so every width-matching line votes; zero or conflicting votes
    # ⇒ no UWI.
    uwi_votes: set[int] = set()
    for line in header:
        tokens = _header_tokens(line)
        if len(tokens) != row_width or not tokens:
            continue
        matches = [
            index
            for index, token in enumerate(tokens)
            if _normalized_column(token) == "uwi"
        ]
        if len(matches) == 1:
            uwi_votes.add(matches[0])
    uwi_index: int | None = uwi_votes.pop() if len(uwi_votes) == 1 else None

    declared_crs = _source_crs_declaration(header)
    units = _unit_declarations(header)
    declared_x_unit = units.get("x", "")
    declared_y_unit = units.get("y", "")
    if (
        declared_x_unit
        and declared_y_unit
        and declared_x_unit != declared_y_unit
    ):
        raise _DatSchemaError("conflicting X/Y coordinate units")
    declared_units = declared_x_unit or declared_y_unit
    asset_source_crs = source_crs
    asset_coordinate_units = coordinate_units
    source_crs = _merge_declared_metadata(
        asset_source_crs,
        declared_crs,
        name="SourceCRS",
    )
    coordinate_units = _merge_declared_metadata(
        asset_coordinate_units,
        declared_units,
        name="coordinate unit",
    )
    comparison_matches_source = (
        _same_explicit_crs(source_crs, comparison_crs)
        if source_crs and comparison_crs
        else None
    )

    def parse_row(row):
        name = _value_at(row, mapping["name"])
        if not name:
            raise _DatSchemaError("井名为空")
        try:
            x = _finite_float(_value_at(row, mapping["x"]))
        except _DatSchemaError as error:
            raise _DatSchemaError("X 坐标不是有限数值") from error
        try:
            y = _finite_float(_value_at(row, mapping["y"]))
        except _DatSchemaError as error:
            raise _DatSchemaError("Y 坐标不是有限数值") from error
        uwi = _value_at(row, uwi_index).strip() if uwi_index is not None else ""
        return (
            name,
            x,
            y,
            uwi,
        )

    selected = []
    record_ids = []
    source_rows = []
    issues = []
    omitted_issue_count = 0
    row_count = 0
    for source_row, line in _iter_data_lines_with_source(path):
        record_id = row_count
        row_count += 1
        try:
            row = _split_data_line(line)
            if len(row) != row_width:
                raise _DatSchemaError("列数与声明不一致")
            parsed = parse_row(row)
        except _DatSchemaError as error:
            if len(issues) < 20:
                issues.append(PreviewRowIssue(source_row, str(error)))
            else:
                omitted_issue_count += 1
            continue
        selected.append(parsed)
        record_ids.append(record_id)
        source_rows.append(source_row)
        if len(selected) > _MAX_POINTS:
            raise _WellResourceLimitError(
                f"井位数据超过 {_MAX_POINTS:,} 个有效记录的显示上限"
            )
    if row_count == 0:
        raise _DatSchemaError("no data rows")
    if not selected:
        causes = "; ".join(
            f"source row {issue.source_row}: {issue.reason}"
            for issue in issues
        )
        detail = "no renderable well locations"
        if causes:
            detail = f"{detail}; {causes}"
        if omitted_issue_count:
            detail = f"{detail}; {omitted_issue_count} additional rows omitted"
        raise _DatSchemaError(detail)
    return XYPreviewPayload(
        names=tuple(row[0] for row in selected),
        x=np.ascontiguousarray([row[1] for row in selected], dtype=np.float64),
        y=np.ascontiguousarray([row[2] for row in selected], dtype=np.float64),
        resource_id=str(resource_id),
        record_ids=tuple(record_ids),
        source_rows=tuple(source_rows),
        source_version=str(source_version),
        source_crs=str(source_crs),
        coordinate_units=str(coordinate_units),
        coordinate_status=SourceCoordinateStatus(
            source_crs_provenance=_metadata_provenance(
                asset_source_crs,
                declared_crs,
                missing="undeclared",
            ),
            coordinate_units_provenance=_metadata_provenance(
                asset_coordinate_units,
                declared_units,
                missing="unknown",
            ),
            comparison_crs=str(comparison_crs),
            comparison_matches_source=comparison_matches_source,
        ),
        diagnostics=XYPreviewDiagnostics(
            total_records=row_count,
            valid_records=len(selected),
            issues=tuple(issues),
            omitted_issue_count=omitted_issue_count,
        ),
        uwis=(
            tuple(row[3] for row in selected) if uwi_index is not None else ()
        ),
    )


def _time_depth_payload(path: str, options: PreviewOptions) -> TimeDepthPreviewPayload:
    header, data_lines = _read_dat_data_lines(path)
    first_row = _split_data_line(data_lines[0])
    if not first_row:
        raise _DatSchemaError("no data rows")
    mapping = _time_depth_mapping(header, len(first_row))

    def parse_row(row):
        return (
            _finite_float(_value_at(row, mapping["depth"])),
            _finite_float(_value_at(row, mapping["time"])),
        )

    indices = representative_indices(len(data_lines), _sample_limit(options))
    selected = _parse_selected_lines(data_lines, indices, parse_row)
    depth = np.asarray([row[0] for row in selected], dtype=np.float64)
    time_ms = np.asarray([row[1] for row in selected], dtype=np.float64)
    order = np.argsort(depth, kind="stable")
    return TimeDepthPreviewPayload(
        depth=np.ascontiguousarray(depth[order]),
        time_ms=np.ascontiguousarray(time_ms[order]),
    )


def _surface_payload(path: str, options: PreviewOptions) -> SurfacePreviewPayload:
    header, data_lines = _read_dat_data_lines(path)
    if not any(_HORIZON_MARKER in line for line in header):
        raise _DatSchemaError("missing horizon marker")
    first_row = _split_data_line(data_lines[0])
    if not first_row:
        raise _DatSchemaError("no data rows")
    mapping = _horizon_field_mapping(header, len(first_row))

    def parse_row(row):
        return (
            _finite_float(_value_at(row, mapping["x"])),
            _finite_float(_value_at(row, mapping["y"])),
            _finite_float(_value_at(row, mapping["z"])),
        )

    source_indices = representative_indices(len(data_lines), _sample_limit(options))
    selected = _parse_selected_lines(data_lines, source_indices, parse_row)
    source_x = np.asarray([row[0] for row in selected], dtype=np.float64)
    source_y = np.asarray([row[1] for row in selected], dtype=np.float64)
    source_z = np.asarray([row[2] for row in selected], dtype=np.float64)
    xy = np.column_stack((source_x, source_y))
    unique_xy = np.unique(xy, axis=0)
    if (
        len(source_x) < 3
        or len(unique_xy) != len(source_x)
        or len(np.unique(source_x)) < 2
        or len(np.unique(source_y)) < 2
        or np.linalg.matrix_rank(unique_xy - unique_xy.mean(axis=0)) < 2
    ):
        raise _DatSchemaError("insufficient independent horizon geometry")
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
    level_min = float(finite_z.min())
    level_max = float(finite_z.max())
    if level_min == level_max:
        epsilon = max(abs(level_min) * 1e-6, 1e-6)
        level_min -= epsilon
        level_max += epsilon
    levels_array = np.linspace(level_min, level_max, num=10)
    return SurfacePreviewPayload(
        grid_x=np.ascontiguousarray(grid_x, dtype=np.float64),
        grid_y=np.ascontiguousarray(grid_y, dtype=np.float64),
        grid_z=np.ascontiguousarray(grid_z, dtype=np.float64),
        levels=tuple(float(level) for level in levels_array),
    )


def _iter_valid_well_tops(path: str):
    for row in _iter_rows(path):
        if len(row) != len(_WELL_TOPS_COLUMNS):
            continue
        well_name, formation_name = row[0], row[1]
        if not well_name or not formation_name:
            continue
        try:
            depth_m = float(row[2])
        except ValueError:
            continue
        if not math.isfinite(depth_m):
            continue
        yield FormationTop(well_name, formation_name, depth_m)


def _formation_chains(
    tops: tuple[FormationTop, ...],
) -> tuple[tuple[int, ...], ...]:
    wells = tuple(sorted({top.well_name for top in tops}))
    indices_by_well: dict[str, list[int]] = {well: [] for well in wells}
    for index, top in enumerate(tops):
        indices_by_well[top.well_name].append(index)

    positions_by_formation: dict[str, list[tuple[int, int]]] = {}
    for well_index, well_name in enumerate(wells):
        seen_in_well = set()
        for top_index in indices_by_well[well_name]:
            formation = tops[top_index].formation_name
            if formation in seen_in_well:
                continue
            seen_in_well.add(formation)
            positions_by_formation.setdefault(formation, []).append(
                (well_index, top_index)
            )

    runs = []
    for formation, positions in positions_by_formation.items():
        run = [positions[0]]
        for position in positions[1:]:
            if position[0] == run[-1][0] + 1:
                run.append(position)
                continue
            if len(run) >= 2:
                runs.append((formation, run[0][0], tuple(item[1] for item in run)))
            run = [position]
        if len(run) >= 2:
            runs.append((formation, run[0][0], tuple(item[1] for item in run)))

    # Connection efficiency (k - 1) / k increases monotonically with run length.
    runs.sort(key=lambda item: (-len(item[2]), item[0], item[1]))
    return tuple(item[2] for item in runs)


def _topology_aware_indices(
    tops: tuple[FormationTop, ...], limit: int
) -> tuple[int, ...]:
    if len(tops) <= limit:
        return tuple(range(len(tops)))
    if limit < 2:
        return tuple(int(index) for index in representative_indices(len(tops), limit))

    selected: set[int] = set()
    remaining_budget = limit
    for chain in _formation_chains(tops):
        if remaining_budget < 2:
            break
        selected_count = min(len(chain), remaining_budget)
        selected.update(chain[:selected_count])
        remaining_budget -= selected_count

    if remaining_budget:
        remaining = [index for index in range(len(tops)) if index not in selected]
        sampled_positions = representative_indices(len(remaining), remaining_budget)
        selected.update(remaining[int(position)] for position in sampled_positions)
    return tuple(sorted(selected))


def _well_stratification_payload(
    path: str, options: PreviewOptions
) -> tuple[FormationTop, ...]:
    header = _read_header(path)
    if not _has_exact_well_tops_schema(header):
        raise _DatSchemaError("missing exact SMI WellTops schema")
    tops = tuple(_iter_valid_well_tops(path))
    if not tops:
        raise _DatSchemaError("no valid well-top rows")
    indices = _topology_aware_indices(tops, _sample_limit(options))
    return tuple(tops[index] for index in indices)


class XYScatterBackend:
    kind = PreviewKind.XY_SCATTER

    def supports(self, request: PreviewRequest) -> bool:
        return _supports_with_header(request, supports_well_head)

    def capabilities(self, request: PreviewRequest) -> PreviewCapabilities:
        return PreviewCapabilities(
            self.kind,
            ("zoom", "pan", "hover", "point_select"),
        )

    def prepare(self, request: PreviewRequest, options: PreviewOptions) -> PreparedPreview:
        try:
            payload = _well_head_payload(
                request.path,
                options,
                resource_id=request.resource_id,
                source_version=request.source_version,
                source_crs=request.source_crs,
                coordinate_units=request.coordinate_units,
                comparison_crs=request.comparison_crs,
            )
        except (OSError, UnicodeError, _DatSchemaError) as error:
            if isinstance(error, _WellResourceLimitError):
                raise GeoVizError(
                    ErrorCode.RESOURCE_LIMIT,
                    str(error),
                ) from error
            raise _prepare_error(error) from error
        diagnostics = payload.diagnostics
        warnings = []
        if diagnostics.skipped_count:
            warnings.append(
                f"{diagnostics.skipped_count} 行已跳过；"
                f"有效 {diagnostics.valid_records}/"
                f"{diagnostics.total_records}"
            )
        if not payload.source_crs:
            warnings.append("SourceCRS 未声明")
        elif payload.coordinate_status.comparison_mismatch:
            warnings.append(
                f"SourceCRS {payload.source_crs} 与参考 CRS "
                f"{payload.coordinate_status.comparison_crs} 不同（未转换）"
            )
        if not payload.coordinate_units:
            warnings.append("坐标单位未知")
        return PreparedPreview(
            kind=self.kind,
            title=request.label or Path(request.path).stem,
            payload=payload,
            summary_rows=(
                ("有效井数", str(len(payload.names))),
                ("源记录", str(diagnostics.total_records)),
            ),
            warning=" · ".join(warnings),
            estimated_bytes=payload.x.nbytes
            + payload.y.nbytes
            + sum(len(name.encode("utf-8")) for name in payload.names)
            + sys.getsizeof(payload.record_ids)
            + sum(sys.getsizeof(record_id) for record_id in payload.record_ids)
            + sys.getsizeof(payload.source_rows)
            + sum(sys.getsizeof(row) for row in payload.source_rows)
            + sys.getsizeof(payload.diagnostics)
            + sys.getsizeof(payload.diagnostics.issues)
            + sum(
                sys.getsizeof(issue.source_row)
                + len(issue.reason.encode("utf-8"))
                for issue in payload.diagnostics.issues
            )
            + len(payload.resource_id.encode("utf-8"))
            + len(payload.source_version.encode("utf-8"))
            + len(payload.source_crs.encode("utf-8"))
            + len(payload.coordinate_units.encode("utf-8"))
            + sum(
                len(value.encode("utf-8"))
                for value in (
                    payload.coordinate_status.source_crs_provenance,
                    payload.coordinate_status.coordinate_units_provenance,
                    payload.coordinate_status.comparison_crs,
                )
            ),
        )

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        return PlotWidget(parent)

    def render(self, widget: QWidget, preview: PreparedPreview) -> None:
        if not isinstance(widget, PlotWidget) or not isinstance(preview.payload, XYPreviewPayload):
            raise GeoVizError(ErrorCode.RENDER_ERROR, "无法渲染井位散点数据")
        widget.clear()
        unit_suffix = (
            f" ({preview.payload.coordinate_units})"
            if preview.payload.coordinate_units
            else ""
        )
        widget.set_axis_labels(f"X{unit_suffix}", f"Y{unit_suffix}")
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


class WellStratificationBackend:
    kind = PreviewKind.FORMATION_TOPS

    def supports(self, request: PreviewRequest) -> bool:
        return _supports_with_header(request, supports_well_stratification)

    def capabilities(self, request: PreviewRequest) -> PreviewCapabilities:
        return PreviewCapabilities(self.kind, ("zoom", "pan", "hover"))

    def prepare(self, request: PreviewRequest, options: PreviewOptions) -> PreparedPreview:
        try:
            payload = _well_stratification_payload(request.path, options)
        except (OSError, UnicodeError, _DatSchemaError) as error:
            raise _prepare_error(error) from error
        estimated_bytes = sum(
            len(top.well_name.encode("utf-8"))
            + len(top.formation_name.encode("utf-8"))
            + len(top.color.encode("utf-8"))
            + 8
            for top in payload
        )
        return PreparedPreview(
            kind=self.kind,
            title=request.label or Path(request.path).stem,
            payload=payload,
            summary_rows=(
                ("层位点", str(len(payload))),
                ("井数", str(len({top.well_name for top in payload}))),
            ),
            estimated_bytes=estimated_bytes,
        )

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        return FormationTopsPreviewWidget(parent)

    def render(self, widget: QWidget, preview: PreparedPreview) -> None:
        if not isinstance(widget, FormationTopsPreviewWidget) or not (
            isinstance(preview.payload, tuple)
            and all(isinstance(top, FormationTop) for top in preview.payload)
        ):
            raise GeoVizError(ErrorCode.RENDER_ERROR, "无法渲染井分层数据")
        widget.set_tops(preview.payload)

    def release(self, widget: QWidget) -> None:
        if not isinstance(widget, FormationTopsPreviewWidget):
            raise GeoVizError(ErrorCode.RENDER_ERROR, "无法释放井分层画布")
        widget.clear()


__all__ = [
    "HorizonSurfaceBackend",
    "SurfacePreviewPayload",
    "TimeDepthBackend",
    "TimeDepthPreviewPayload",
    "WellStratificationBackend",
    "XYPreviewPayload",
    "XYScatterBackend",
    "representative_indices",
    "supports_horizon",
    "supports_time_depth",
    "supports_well_head",
    "supports_well_stratification",
]
