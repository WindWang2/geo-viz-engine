"""Industry-standard LAS 2.0 / 3.0 file parser (compatibility API).

The parsing logic lives in :mod:`geoviz_well_log.las_preview`; this module
keeps the legacy ``LASParseResult`` surface so existing callers behave
identically. NULL tolerance (``abs_tol=1e-6``), invalid-depth row dropping
and WRAP/DLM handling are shared with the preview readers.
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

import numpy as np

from .las_preview import inspect_las_file, read_full_ascii


@dataclass
class LASParseResult:
    well_name: str = "UNKNOWN"
    depth_name: str = "DEPT"
    depth: np.ndarray = field(default_factory=lambda: np.array([]))
    curves: Dict[str, np.ndarray] = field(default_factory=dict)
    units: Dict[str, str] = field(default_factory=dict)
    descriptions: Dict[str, str] = field(default_factory=dict)

def _parse_file(filepath: str) -> LASParseResult:
    """Full LAS read on top of the preview readers, legacy field layout."""
    try:
        header = inspect_las_file(filepath)
    except ValueError:
        # No curve headers: preserve the legacy non-raising behaviour.
        return LASParseResult()
    depth, values = read_full_ascii(filepath, header)
    depth_name = header.curves[header.depth_index].mnemonic
    curves: Dict[str, np.ndarray] = {}
    units: Dict[str, str] = {}
    descriptions: Dict[str, str] = {}
    for curve in header.curves:
        if curve.index == header.depth_index:
            continue
        curves[curve.mnemonic] = values[curve.index]
        units[curve.mnemonic] = curve.unit
        descriptions[curve.mnemonic] = curve.description
    return LASParseResult(
        well_name=header.well_name or "UNKNOWN",
        depth_name=depth_name,
        depth=depth,
        curves=curves,
        units=units,
        descriptions=descriptions,
    )

def parse_las_text(text: str) -> LASParseResult:
    """Parse LAS format string and return clean LASParseResult."""
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".las", delete=False
    ) as tmp:
        tmp.write(text)
        tmp_path = tmp.name
    try:
        return _parse_file(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

def parse_las_file(filepath: str) -> LASParseResult:
    """Parse LAS file from disk filepath."""
    return _parse_file(filepath)
