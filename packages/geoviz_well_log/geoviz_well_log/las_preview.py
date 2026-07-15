"""Bounded, two-pass LAS loading for local well-log previews."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path

import numpy as np

from .models import CurveData, WellLogData


@dataclass(frozen=True)
class LASCurveHeader:
    index: int
    mnemonic: str
    unit: str
    description: str


@dataclass(frozen=True)
class LASPreviewHeader:
    well_name: str
    null_value: float
    depth_index: int
    curves: tuple[LASCurveHeader, ...]
    row_count: int

    @property
    def non_depth_curves(self) -> tuple[LASCurveHeader, ...]:
        return tuple(curve for curve in self.curves if curve.index != self.depth_index)


def _section_from_line(line: str) -> str:
    section = line[1:].strip().upper()
    if section.startswith("W"):
        return "WELL"
    if section.startswith("C"):
        return "CURVE"
    if section.startswith("A"):
        return "ASCII"
    return section


def _well_item(line: str) -> tuple[str, str] | None:
    left = line.split(":", 1)[0]
    if "." not in left:
        return None
    mnemonic, value = left.split(".", 1)
    return mnemonic.strip().upper(), value.strip()


def _curve_header(line: str, index: int) -> LASCurveHeader | None:
    definition, _, description = line.partition(":")
    if "." not in definition:
        return None
    mnemonic, unit = definition.split(".", 1)
    mnemonic = mnemonic.strip()
    if not mnemonic:
        return None
    return LASCurveHeader(index, mnemonic, unit.strip(), description.strip())


def _find_depth_index(curves: tuple[LASCurveHeader, ...] | list[LASCurveHeader]) -> int:
    for curve in curves:
        if curve.mnemonic.upper() in {"DEPT", "DEPTH"}:
            return curve.index
    return curves[0].index if curves else 0


def _is_null(value: float, null_value: float) -> bool:
    return math.isclose(value, null_value, rel_tol=0.0, abs_tol=1e-6)


def _valid_depth(tokens: list[str], column_count: int, depth_index: int, null_value: float) -> float | None:
    if len(tokens) < column_count:
        return None
    try:
        depth = float(tokens[depth_index])
    except (IndexError, ValueError):
        return None
    if not math.isfinite(depth) or _is_null(depth, null_value):
        return None
    return depth


def inspect_las_file(path: str) -> LASPreviewHeader:
    """Read LAS metadata and count valid depth rows without retaining ASCII data."""

    section = ""
    well_name = ""
    null_value = -999.25
    curves: list[LASCurveHeader] = []
    row_count = 0
    depth_index = 0

    with open(path, "r", encoding="utf-8", errors="replace") as stream:
        for raw_line in stream:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("~"):
                section = _section_from_line(line)
                if section == "ASCII":
                    depth_index = _find_depth_index(curves)
                continue

            if section == "WELL":
                item = _well_item(line)
                if item is None:
                    continue
                mnemonic, value = item
                if mnemonic == "WELL":
                    well_name = value
                elif mnemonic == "NULL":
                    try:
                        null_value = float(value.split()[0])
                    except (IndexError, ValueError):
                        pass
            elif section == "CURVE":
                curve = _curve_header(line, len(curves))
                if curve is not None:
                    curves.append(curve)
            elif section == "ASCII" and curves:
                tokens = line.split()
                if _valid_depth(tokens, len(curves), depth_index, null_value) is not None:
                    row_count += 1

    if not curves:
        raise ValueError("LAS contains no curve headers")

    return LASPreviewHeader(
        well_name=well_name,
        null_value=null_value,
        depth_index=_find_depth_index(curves),
        curves=tuple(curves),
        row_count=row_count,
    )


def _selected_value(tokens: list[str], index: int, null_value: float) -> float:
    try:
        value = float(tokens[index])
    except (IndexError, ValueError):
        return math.nan
    if not math.isfinite(value) or _is_null(value, null_value):
        return math.nan
    return value


def read_sampled_ascii(
    path: str,
    header: LASPreviewHeader,
    selected: tuple[LASCurveHeader, ...],
    stride: int,
    max_samples: int = 2_000,
) -> tuple[np.ndarray, dict[int, np.ndarray]]:
    """Read only depth and selected curve columns into bounded arrays."""

    if stride < 1:
        raise ValueError("LAS sample stride must be positive")
    if max_samples < 2:
        raise ValueError("LAS preview requires at least two samples")

    selected_indices = {curve.index for curve in selected}
    known_indices = {curve.index for curve in header.curves}
    if not selected_indices <= known_indices or header.depth_index in selected_indices:
        raise ValueError("LAS selected curves are invalid")

    sampled_depths: list[float] = []
    sampled_values: dict[int, list[float]] = {curve.index: [] for curve in selected}
    section = ""
    valid_index = 0
    last_valid_index = -1
    last_depth = math.nan
    last_values: dict[int, float] = {}
    last_sampled_index = -1

    with open(path, "r", encoding="utf-8", errors="replace") as stream:
        for raw_line in stream:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("~"):
                section = _section_from_line(line)
                continue
            if section != "ASCII":
                continue

            tokens = line.split()
            depth = _valid_depth(tokens, len(header.curves), header.depth_index, header.null_value)
            if depth is None:
                continue

            row_values = {
                curve.index: _selected_value(tokens, curve.index, header.null_value)
                for curve in selected
            }
            last_valid_index = valid_index
            last_depth = depth
            last_values = row_values

            if valid_index % stride == 0 and len(sampled_depths) < max_samples:
                sampled_depths.append(depth)
                for curve in selected:
                    sampled_values[curve.index].append(row_values[curve.index])
                last_sampled_index = valid_index
            valid_index += 1

    if last_valid_index >= 0 and last_sampled_index != last_valid_index:
        if len(sampled_depths) < max_samples:
            sampled_depths.append(last_depth)
            for curve in selected:
                sampled_values[curve.index].append(last_values[curve.index])
        else:
            sampled_depths[-1] = last_depth
            for curve in selected:
                sampled_values[curve.index][-1] = last_values[curve.index]

    depth_array = np.asarray(sampled_depths, dtype=np.float64)
    value_arrays = {
        index: np.asarray(values, dtype=np.float64)
        for index, values in sampled_values.items()
    }
    return depth_array, value_arrays


def curve_data_from_arrays(
    header: LASCurveHeader,
    depth: np.ndarray,
    values: np.ndarray,
) -> CurveData:
    finite = values[np.isfinite(values)]
    display_range = (
        (float(np.min(finite)), float(np.max(finite)))
        if finite.size
        else (0.0, 100.0)
    )
    return CurveData(
        name=header.mnemonic,
        unit=header.unit,
        depth=depth.tolist(),
        values=values.tolist(),
        display_range=display_range,
    )


def load_las_preview(
    path: str,
    *,
    max_curves: int = 12,
    max_samples: int = 2_000,
) -> WellLogData:
    if max_curves < 0:
        raise ValueError("LAS curve limit cannot be negative")
    if max_samples < 2:
        raise ValueError("LAS preview requires at least two samples")

    header = inspect_las_file(path)
    selected = header.non_depth_curves[:max_curves]
    stride = max(1, math.ceil(header.row_count / max_samples))
    depth, values = read_sampled_ascii(path, header, selected, stride, max_samples)
    if depth.size < 2:
        raise ValueError("LAS contains fewer than two depth rows")
    curves = [
        curve_data_from_arrays(item, depth, values[item.index])
        for item in selected
    ]
    return WellLogData(
        well_name=header.well_name or Path(path).stem,
        top_depth=float(np.nanmin(depth)),
        bottom_depth=float(np.nanmax(depth)),
        curves=curves,
    )


__all__ = [
    "LASCurveHeader",
    "LASPreviewHeader",
    "curve_data_from_arrays",
    "inspect_las_file",
    "load_las_preview",
    "read_sampled_ascii",
]
