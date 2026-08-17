from __future__ import annotations

import csv
from dataclasses import dataclass, field

import numpy as np

try:
    from geoviz_well_tie.calibration import WellTieCalibration
except ImportError:  # optional extra: well-tie
    WellTieCalibration = None  # type: ignore[misc, assignment]


@dataclass
class CheckshotTable:
    well_name: str
    depths_m: np.ndarray
    twt_ms: np.ndarray
    _calibration: object = field(init=False, repr=False)

    def __post_init__(self):
        if WellTieCalibration is None:
            self._calibration = None
        else:
            self._calibration = WellTieCalibration(self.depths_m, self.twt_ms)

    @property
    def calibration(self):
        return self._calibration

    def interpolate_twt(self, depth: float | np.ndarray) -> float | np.ndarray:
        if self._calibration is None:
            return np.interp(depth, self.depths_m, self.twt_ms)
        return self._calibration.depth_to_twt(depth)

    def interpolate_depth(self, twt: float | np.ndarray) -> float | np.ndarray:
        if self._calibration is None:
            return np.interp(twt, self.twt_ms, self.depths_m)
        return self._calibration.twt_to_depth(twt)


class SeismicTie:
    def __init__(self):
        self._tables: dict[str, CheckshotTable] = {}

    def load_csv(self, path: str, well_name: str | None = None) -> None:
        by_well: dict[str, tuple[list[float], list[float]]] = {}
        has_well_col = False

        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row or row[0].startswith("#"):
                    continue
                cells = [cell.strip() for cell in row]
                header = [cell.lower() for cell in cells]
                if header[0] in ("depth_m", "depth", "md"):
                    has_well_col = any("well" in cell for cell in header)
                    continue
                try:
                    if len(cells) < 2:
                        continue
                    d = float(cells[0])
                    t = float(cells[1])
                    if has_well_col and len(cells) >= 3 and cells[2]:
                        w = cells[2]
                    else:
                        w = well_name or "default"
                except (ValueError, IndexError):
                    continue
                depths, twts = by_well.setdefault(w, ([], []))
                depths.append(d)
                twts.append(t)

        for name, (depths, twts) in by_well.items():
            order = np.argsort(depths)
            self._tables[name] = CheckshotTable(
                well_name=name,
                depths_m=np.array(depths)[order],
                twt_ms=np.array(twts)[order],
            )

    def depth_to_twt(self, well: str, depth: float) -> float | None:
        table = self._tables.get(well)
        if table is None:
            return None
        return table.interpolate_twt(depth)

    def twt_to_depth(self, well: str, twt: float) -> float | None:
        table = self._tables.get(well)
        if table is None:
            return None
        return table.interpolate_depth(twt)

    def has_well(self, well: str) -> bool:
        return well in self._tables

    def table_for_well(self, well: str) -> CheckshotTable | None:
        return self._tables.get(well)

    def well_names(self) -> list[str]:
        return list(self._tables.keys())

    def clear(self) -> None:
        self._tables.clear()
