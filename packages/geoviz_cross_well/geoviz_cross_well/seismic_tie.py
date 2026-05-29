from __future__ import annotations

import csv
from dataclasses import dataclass

import numpy as np


@dataclass
class CheckshotTable:
    well_name: str
    depths_m: np.ndarray
    twt_ms: np.ndarray

    def interpolate_twt(self, depth: float) -> float:
        return float(np.interp(depth, self.depths_m, self.twt_ms))

    def interpolate_depth(self, twt: float) -> float:
        return float(np.interp(twt, self.twt_ms, self.depths_m))


class SeismicTie:
    def __init__(self):
        self._tables: dict[str, CheckshotTable] = {}

    def load_csv(self, path: str, well_name: str | None = None) -> None:
        depths = []
        twts = []
        detected_well: str | None = None
        has_well_col = False

        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row or row[0].startswith("#"):
                    continue
                if row[0].strip().lower() in ("depth_m", "depth", "md"):
                    if len(row) >= 3 and row[2].strip().lower() in ("twt_ms", "twt"):
                        has_well_col = len(row) >= 4 and "well" in row[-1].lower()
                    continue
                try:
                    if len(row) >= 3 and has_well_col:
                        d = float(row[0].strip())
                        t = float(row[1].strip())
                        w = row[2].strip()
                    elif len(row) >= 2:
                        d = float(row[0].strip())
                        t = float(row[1].strip())
                        w = well_name or "default"
                    else:
                        continue
                except (ValueError, IndexError):
                    continue
                depths.append(d)
                twts.append(t)
                detected_well = w

        if not depths:
            return

        name = detected_well or well_name or "default"
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
