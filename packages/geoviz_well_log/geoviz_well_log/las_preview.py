"""Bounded, two-pass LAS loading for local well-log previews."""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass
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
    wrapped: bool = False
    delimiter: str = "SPACE"

    @property
    def non_depth_curves(self) -> tuple[LASCurveHeader, ...]:
        return tuple(curve for curve in self.curves if curve.index != self.depth_index)


def _section_from_line(line: str) -> str:
    section = line[1:].strip().upper()
    if section.startswith("V"):
        return "VERSION"
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


def _delimiter_name(value: str) -> str:
    token = (value.split() or ["SPACE"])[0].strip("'\"").upper()
    if token in {",", "COMMA"}:
        return "COMMA"
    if token in {"\\T", "TAB"}:
        return "TAB"
    return "SPACE"


def _data_tokens(line: str, delimiter: str) -> list[str]:
    if delimiter == "COMMA":
        return [token.strip() for token in line.split(",")]
    if delimiter == "TAB":
        return [token.strip() for token in line.split("\t")]
    return line.split()


def _logical_rows(
    tokens: list[str],
    pending: list[str],
    column_count: int,
    wrapped: bool,
) -> tuple[list[str], ...]:
    if not wrapped:
        return (tokens,)
    pending.extend(tokens)
    rows: list[list[str]] = []
    while len(pending) >= column_count:
        rows.append(pending[:column_count])
        del pending[:column_count]
    return tuple(rows)


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


def inspect_las_file(path: str, header_only: bool = False) -> LASPreviewHeader:
    """Read LAS metadata and count valid depth rows without retaining ASCII data.

    Args:
        path: Path to the LAS file.
        header_only: If True, stop parsing at the ``~A`` section boundary and
            return ``row_count=0`` without scanning the ASCII data. Use when
            the caller only needs header metadata (curve names, null value,
            depth index) and will parse the data separately — avoids a full
            O(n_rows) Python-level scan that blocks the GUI thread on large
            files (303ms on a 50k-row file).
    """

    section = ""
    well_name = ""
    null_value = -999.25
    curves: list[LASCurveHeader] = []
    row_count = 0
    depth_index = 0
    wrapped = False
    delimiter = "SPACE"
    pending_tokens: list[str] = []

    with open(path, "r", encoding="utf-8", errors="replace") as stream:
        for raw_line in stream:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("~"):
                section = _section_from_line(line)
                if section == "ASCII":
                    depth_index = _find_depth_index(curves)
                    if header_only:
                        break  # header parse complete; skip the data-row scan
                continue

            if section == "VERSION":
                item = _well_item(line)
                if item is None:
                    continue
                mnemonic, value = item
                if mnemonic == "WRAP":
                    wrapped = value.split()[0].upper() in {"YES", "Y", "TRUE", "1"}
                elif mnemonic == "DLM":
                    delimiter = _delimiter_name(value)
            elif section == "WELL":
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
                tokens = _data_tokens(line, delimiter)
                for row in _logical_rows(
                    tokens,
                    pending_tokens,
                    len(curves),
                    wrapped,
                ):
                    if _valid_depth(
                        row,
                        len(curves),
                        depth_index,
                        null_value,
                    ) is not None:
                        row_count += 1

    if not curves:
        raise ValueError("LAS contains no curve headers")

    return LASPreviewHeader(
        well_name=well_name,
        null_value=null_value,
        depth_index=_find_depth_index(curves),
        curves=tuple(curves),
        row_count=row_count,
        wrapped=wrapped,
        delimiter=delimiter,
    )


def _selected_value(tokens: list[str], index: int, null_value: float) -> float:
    try:
        value = float(tokens[index])
    except (IndexError, ValueError):
        return math.nan
    if not math.isfinite(value) or _is_null(value, null_value):
        return math.nan
    return value


def _iter_valid_rows(
    path: str, header: LASPreviewHeader
) -> Iterator[tuple[float, list[str]]]:
    """Yield ``(depth, raw tokens)`` for every valid ASCII row in file order."""
    section = ""
    pending: list[str] = []
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

            tokens = _data_tokens(line, header.delimiter)
            for row in _logical_rows(
                tokens,
                pending,
                len(header.curves),
                header.wrapped,
            ):
                depth = _valid_depth(
                    row,
                    len(header.curves),
                    header.depth_index,
                    header.null_value,
                )
                if depth is None:
                    continue
                yield depth, row


def _minmax_indices(reference: np.ndarray, max_samples: int) -> np.ndarray:
    """Return up to ``max_samples`` row indices that keep curve extremes.

    Rows are split into ``max_samples // 2`` equal bins; each bin emits its
    min and max rows in index order (a bin whose min and max coincide emits
    a single row), so peaks and spikes survive downsampling. NaN (null)
    values rank as the maximum so data gaps stay visible, while the true
    minimum ignores them.
    """
    n = reference.size
    if n <= max_samples:
        return np.arange(n, dtype=np.intp)

    bin_count = max_samples // 2
    step = math.ceil(n / bin_count)
    n_bins = math.ceil(n / step)
    # NaN outranks every finite value so argmin/argmax select gap rows.
    ranked = np.where(np.isnan(reference), np.inf, reference)

    parts: list[np.ndarray] = []
    full_count = (n_bins - 1) * step
    if n_bins > 1:
        full = ranked[:full_count].reshape(n_bins - 1, step)
        col_min = np.argmin(full, axis=1)
        col_max = np.argmax(full, axis=1)
        row_offsets = np.arange(n_bins - 1) * step
        idx_min = row_offsets + col_min
        idx_max = row_offsets + col_max
        # Emit min then max, in index order within each bin (avoid zigzag).
        min_first = idx_min <= idx_max
        first = np.where(min_first, idx_min, idx_max)
        second = np.where(min_first, idx_max, idx_min)
        out = np.empty((n_bins - 1) * 2, dtype=np.intp)
        out[0::2] = first
        out[1::2] = second
        parts.append(out)

    if full_count < n:
        chunk = ranked[full_count:]
        lo = full_count + int(np.argmin(chunk))
        hi = full_count + int(np.argmax(chunk))
        lo, hi = (lo, hi) if lo <= hi else (hi, lo)
        parts.append(np.asarray([lo, hi], dtype=np.intp))

    return np.concatenate(parts) if parts else np.empty(0, dtype=np.intp)


def read_sampled_ascii(
    path: str,
    header: LASPreviewHeader,
    selected: tuple[LASCurveHeader, ...],
    stride: int,
    max_samples: int = 2_000,
) -> tuple[np.ndarray, dict[int, np.ndarray]]:
    """Read only depth and selected curve columns into bounded arrays.

    Sampling uses min-max binning instead of a uniform ``stride`` so curve
    spikes and null gaps survive downsampling; ``stride`` is validated but
    kept only for API compatibility. ``max_samples`` bounds the output.
    """

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

    indices: np.ndarray | None = None
    if header.row_count > max_samples:
        # Bounded read: pass one collects the reference column that drives
        # the bin extrema (first selected curve, depth when none selected).
        reference_index = selected[0].index if selected else header.depth_index
        reference: list[float] = []
        for _depth, tokens in _iter_valid_rows(path, header):
            reference.append(
                _selected_value(tokens, reference_index, header.null_value)
            )
        indices = _minmax_indices(np.asarray(reference, dtype=np.float64), max_samples)
        n = len(reference)
        if n > 0 and indices[-1] != n - 1:
            # Keep the deepest valid row so bottom depth never truncates.
            if indices.size < max_samples:
                indices = np.append(indices, n - 1)
            else:
                indices[-1] = n - 1

    target_pos = 0
    for row_index, (depth, tokens) in enumerate(_iter_valid_rows(path, header)):
        if indices is not None and row_index != indices[target_pos]:
            continue
        sampled_depths.append(depth)
        for curve in selected:
            sampled_values[curve.index].append(
                _selected_value(tokens, curve.index, header.null_value)
            )
        if indices is not None:
            target_pos += 1
            if target_pos == indices.size:
                break

    depth_array = np.asarray(sampled_depths, dtype=np.float64)
    value_arrays = {
        index: np.asarray(values, dtype=np.float64)
        for index, values in sampled_values.items()
    }
    return depth_array, value_arrays


def read_full_ascii(
    path: str,
    header: LASPreviewHeader,
) -> tuple[np.ndarray, dict[int, np.ndarray]]:
    """Read every valid ASCII row (no downsampling) into depth + value arrays.

    Returns the complete dataset; prefer :func:`read_sampled_ascii` for
    previews of large files. Used by the legacy
    :mod:`geoviz_well_log.las_parser` compatibility API.
    """
    depths: list[float] = []
    values: dict[int, list[float]] = {curve.index: [] for curve in header.curves}
    for depth, tokens in _iter_valid_rows(path, header):
        depths.append(depth)
        for curve in header.curves:
            values[curve.index].append(
                _selected_value(tokens, curve.index, header.null_value)
            )
    return (
        np.asarray(depths, dtype=np.float64),
        {index: np.asarray(col, dtype=np.float64) for index, col in values.items()},
    )


def curve_data_from_arrays(
    header: LASCurveHeader,
    depth: np.ndarray,
    values: np.ndarray,
) -> CurveData:
    finite = values[np.isfinite(values)]
    if finite.size >= 2:
        display_range = (float(finite.min()), float(finite.max()))
    else:
        display_range = (0.0, 100.0)
    return CurveData(
        name=header.mnemonic,
        unit=header.unit,
        depth=depth.tolist(),
        values=values.tolist(),
        display_range=display_range,
    )


_las_parser_provider: Callable | None = None


def set_las_parser_provider(provider: Callable | None) -> None:
    """Register or clear a custom LAS C++ parser provider callable.

    The provider signature is (content: str, null_value: float) -> tuple[tuple[str, ...], np.ndarray].
    """
    global _las_parser_provider
    _las_parser_provider = provider


def get_las_parser_provider() -> Callable | None:
    """Return the currently registered LAS C++ parser provider callable or None."""
    return _las_parser_provider


def _load_las_preview_fast(
    path: str,
    provider: Callable,
    max_curves: int,
    max_samples: int,
) -> WellLogData | None:
    header = inspect_las_file(path, header_only=True)
    if header.wrapped or not header.curves:
        return None

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    names, arr = provider(content, header.null_value)

    if not isinstance(arr, np.ndarray) or arr.ndim != 2 or arr.shape[0] < 2:
        return None

    max_index = max(c.index for c in header.curves)
    if arr.shape[1] <= max_index:
        return None

    depth_col = arr[:, header.depth_index]
    valid_mask = np.isfinite(depth_col) & ~np.isclose(depth_col, header.null_value, atol=1e-6)
    if valid_mask.sum() < 2:
        return None

    valid_arr = arr[valid_mask]
    n_valid = valid_arr.shape[0]

    selected = header.non_depth_curves[:max_curves]

    # Min-max binning mirrors the pure-Python path: the first selected curve
    # (depth when none) drives the bin extrema so both paths agree exactly.
    reference_col = selected[0].index if selected else header.depth_index
    reference = valid_arr[:, reference_col].copy()
    null_mask = np.isclose(reference, header.null_value, atol=1e-6) | ~np.isfinite(reference)
    reference[null_mask] = np.nan

    indices = _minmax_indices(reference, max_samples)
    if indices[-1] != n_valid - 1:
        if indices.size < max_samples:
            indices = np.append(indices, n_valid - 1)
        else:
            indices[-1] = n_valid - 1

    sampled_arr = valid_arr[indices]
    depth_array = sampled_arr[:, header.depth_index]

    curves: list[CurveData] = []
    for item in selected:
        vals = sampled_arr[:, item.index].copy()
        null_mask = np.isclose(vals, header.null_value, atol=1e-6) | ~np.isfinite(vals)
        vals[null_mask] = np.nan

        finite = vals[np.isfinite(vals)]
        if finite.size >= 2:
            display_range = (float(finite.min()), float(finite.max()))
        else:
            display_range = (0.0, 100.0)

        curves.append(
            CurveData.model_construct(
                name=item.mnemonic,
                unit=item.unit,
                depth=depth_array.tolist(),
                values=vals.tolist(),
                display_range=display_range,
            )
        )

    well_name = header.well_name or Path(path).stem
    return WellLogData.model_construct(
        well_name=well_name,
        top_depth=float(np.nanmin(depth_array)),
        bottom_depth=float(np.nanmax(depth_array)),
        curves=curves,
    )


def load_las_preview(
    path: str,
    *,
    max_curves: int = 12,
    max_samples: int = 2_000,
    fast: bool = False,
) -> WellLogData:
    if max_curves < 0:
        raise ValueError("LAS curve limit cannot be negative")
    if max_samples < 2:
        raise ValueError("LAS preview requires at least two samples")

    if fast:
        provider = get_las_parser_provider()
        if provider is not None:
            try:
                res = _load_las_preview_fast(
                    path,
                    provider,
                    max_curves=max_curves,
                    max_samples=max_samples,
                )
                if res is not None:
                    return res
            except Exception:
                pass  # Silently fall back to pure-Python path

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
    "get_las_parser_provider",
    "inspect_las_file",
    "load_las_preview",
    "read_full_ascii",
    "read_sampled_ascii",
    "set_las_parser_provider",
]
