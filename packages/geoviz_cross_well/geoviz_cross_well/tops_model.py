from __future__ import annotations

import csv
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal

_FORMATION_PALETTE = [
    "#d97706",  # amber
    "#dc2626",  # red
    "#059669",  # emerald
    "#7c3aed",  # violet
    "#db2777",  # pink
    "#0891b2",  # cyan
    "#65a30d",  # lime
    "#ea580c",  # orange
    "#4f46e5",  # indigo
    "#0d9488",  # teal
]


def _assign_color(formation_name: str, existing: dict[str, str]) -> str:
    if formation_name in existing:
        return existing[formation_name]
    used = set(existing.values())
    for c in _FORMATION_PALETTE:
        if c not in used:
            return c
    idx = len(existing) % len(_FORMATION_PALETTE)
    return _FORMATION_PALETTE[idx]


@dataclass
class FormationTop:
    well_name: str
    formation_name: str
    depth_m: float
    color: str = ""

    def __post_init__(self):
        if not self.color:
            self.color = _FORMATION_PALETTE[sum(ord(c) for c in self.formation_name) % len(_FORMATION_PALETTE)]


class FormationTopsModel(QObject):
    tops_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tops: dict[str, list[FormationTop]] = {}
        self._color_map: dict[str, str] = {}

    def load_csv(self, path: str) -> None:
        self._tops.clear()
        self._color_map.clear()
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row or row[0].startswith("#"):
                    continue
                if len(row) < 3:
                    continue
                # Skip header row if present
                try:
                    depth = float(row[2].strip())
                except ValueError:
                    continue
                well = row[0].strip()
                name = row[1].strip()
                color = _assign_color(name, self._color_map)
                self._color_map.setdefault(name, color)
                top = FormationTop(well_name=well, formation_name=name, depth_m=depth, color=color)
                self._tops.setdefault(well, []).append(top)
        for well in self._tops:
            self._tops[well].sort(key=lambda t: t.depth_m)
        self.tops_changed.emit()

    def save_csv(self, path: str) -> None:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for well in sorted(self._tops):
                for top in self._tops[well]:
                    writer.writerow([top.well_name, top.formation_name, top.depth_m])

    def tops_for_well(self, well: str) -> list[FormationTop]:
        return list(self._tops.get(well, []))

    def all_tops(self) -> list[FormationTop]:
        result = []
        for well in sorted(self._tops):
            result.extend(self._tops[well])
        return result

    def add_top(self, top: FormationTop) -> None:
        color = _assign_color(top.formation_name, self._color_map)
        self._color_map.setdefault(top.formation_name, color)
        top.color = color
        self._tops.setdefault(top.well_name, []).append(top)
        self._tops[top.well_name].sort(key=lambda t: t.depth_m)
        self.tops_changed.emit()

    def delete_top(self, well: str, formation: str) -> None:
        if well not in self._tops:
            return
        self._tops[well] = [t for t in self._tops[well] if t.formation_name != formation]
        if not self._tops[well]:
            del self._tops[well]
        self.tops_changed.emit()

    def formation_names(self) -> list[str]:
        seen = set()
        result = []
        for well in self._tops:
            for t in self._tops[well]:
                if t.formation_name not in seen:
                    seen.add(t.formation_name)
                    result.append(t.formation_name)
        return result

    def well_names(self) -> list[str]:
        return sorted(self._tops.keys())

    def clear(self) -> None:
        self._tops.clear()
        self._color_map.clear()
        self.tops_changed.emit()
