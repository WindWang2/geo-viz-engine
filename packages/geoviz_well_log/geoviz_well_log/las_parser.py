"""Industry-standard LAS 2.0 / 3.0 file parser."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import numpy as np

@dataclass
class LASParseResult:
    well_name: str = "UNKNOWN"
    depth_name: str = "DEPT"
    depth: np.ndarray = field(default_factory=lambda: np.array([]))
    curves: Dict[str, np.ndarray] = field(default_factory=dict)
    units: Dict[str, str] = field(default_factory=dict)
    descriptions: Dict[str, str] = field(default_factory=dict)

def parse_las_text(text: str) -> LASParseResult:
    """Parse LAS format string and return clean LASParseResult."""
    lines = text.splitlines()

    current_section: Optional[str] = None
    well_name = "UNKNOWN"
    null_value = -999.25

    curve_names: List[str] = []
    curve_units: Dict[str, str] = {}
    curve_descs: Dict[str, str] = {}
    data_rows: List[List[float]] = []

    for line in lines:
        line_str = line.strip()
        if not line_str or line_str.startswith("#"):
            continue

        if line_str.startswith("~"):
            sec_header = line_str[1:].strip().upper()
            if sec_header.startswith("V"):
                current_section = "VERSION"
            elif sec_header.startswith("W"):
                current_section = "WELL"
            elif sec_header.startswith("C"):
                current_section = "CURVE"
            elif sec_header.startswith("A"):
                current_section = "ASCII"
            else:
                current_section = sec_header
            continue

        if current_section == "WELL":
            if "." in line_str and ":" in line_str:
                left, right = line_str.split(":", 1)
                item_name, item_val = left.split(".", 1)
                item_name = item_name.strip().upper()
                item_val = item_val.strip()
                if item_name == "WELL" and item_val:
                    well_name = item_val
                elif item_name == "NULL":
                    try:
                        null_value = float(item_val)
                    except ValueError:
                        pass

        elif current_section == "CURVE":
            if "." in line_str:
                parts = line_str.split(":", 1)
                desc = parts[1].strip() if len(parts) > 1 else ""
                left_part = parts[0]
                name, unit = left_part.split(".", 1)
                name = name.strip()
                unit = unit.strip()
                if name:
                    curve_names.append(name)
                    curve_units[name] = unit
                    curve_descs[name] = desc

        elif current_section == "ASCII":
            tokens = line_str.split()
            try:
                vals = [float(t) for t in tokens]
                if len(vals) == len(curve_names):
                    data_rows.append(vals)
            except ValueError:
                continue

    if not data_rows or not curve_names:
        return LASParseResult(well_name=well_name)

    data_arr = np.array(data_rows, dtype=np.float64)

    # Detect depth curve
    depth_idx = 0
    depth_name = curve_names[0]
    for i, c_name in enumerate(curve_names):
        if c_name.upper() in ["DEPT", "DEPTH"]:
            depth_idx = i
            depth_name = c_name
            break

    depth = data_arr[:, depth_idx]

    curves: Dict[str, np.ndarray] = {}
    for i, c_name in enumerate(curve_names):
        if i == depth_idx:
            continue
        vals = data_arr[:, i].copy()
        # Clean NULL values
        vals[np.isclose(vals, null_value, atol=1e-3)] = np.nan
        vals[vals == -9999.0] = np.nan
        curves[c_name] = vals

    return LASParseResult(
        well_name=well_name,
        depth_name=depth_name,
        depth=depth,
        curves=curves,
        units=curve_units,
        descriptions=curve_descs,
    )

def parse_las_file(filepath: str) -> LASParseResult:
    """Parse LAS file from disk filepath."""
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    return parse_las_text(content)
