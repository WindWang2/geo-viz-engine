"""Unified well catalog: coordinates JSON, file registry, and import tracking."""
from __future__ import annotations

import json
from pathlib import Path

from src.data.loaders import load_well_coordinates, load_well_log_from_excel
from src.data.models import WellCoordinates
from src.utils.paths import get_data_dir


def save_well_coordinates(path: Path, wells: list[WellCoordinates]) -> None:
    """Persist well coordinates to JSON (well_name / latitude / longitude)."""
    data = {
        "wells": [
            {
                "well_name": w.name,
                "latitude": w.latitude,
                "longitude": w.longitude,
            }
            for w in wells
        ]
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class WellCatalog:
    """Single source of truth for well coordinates, data files, and imports."""

    def __init__(self, data_dir: Path | None = None):
        self._data_dir = data_dir or get_data_dir()
        self._coords_path = self._data_dir / "well_coordinates.json"
        self._imported_files_path = self._data_dir / "imported_files.json"
        self._coords: list[WellCoordinates] | None = None
        self._registry: dict[str, Path] = {}
        self._imported_files: list[str] = self._load_imported_files()
        self._rebuild_registry()

    @property
    def coords_path(self) -> Path:
        return self._coords_path

    def get_coordinates(self) -> list[WellCoordinates]:
        if self._coords is None:
            self._coords = load_well_coordinates(self._coords_path)
        return list(self._coords)

    def invalidate(self) -> None:
        self._coords = None

    def _rebuild_registry(self) -> None:
        registry: dict[str, Path] = {}
        coords_names = {w.name for w in self.get_coordinates()}
        # 演示井仅当对应文件存在且在坐标 JSON 中有记录时才注册
        demo_wells = (
            ("HZ25-10-1", "HZ25-10-1-laolong.xlsx"),
            ("老龙1", "老龙1井-野外剖面数据整理 .xlsx"),
        )
        for well_name, file_name in demo_wells:
            f = self._data_dir / file_name
            if well_name in coords_names and f.exists():
                registry[well_name] = f

        # Well-file binding (#576): plain substring containment matched
        # 'HZ21-1-1' against 'HZ21-1-18-….xlsx' (both wells ship in the
        # coordinates JSON), and the winner depended on glob order — wrong
        # well-log data displayed under a well name, nondeterministically.
        # A file binds to a well only when the well name appears as a WHOLE
        # TOKEN (bounded by non-alphanumeric characters); among token
        # matches the LONGEST well name wins so the most specific file is
        # chosen deterministically.
        def _token_match(well_name: str, file_name: str) -> bool:
            import re

            pattern = re.compile(
                r"(?<![0-9A-Za-z])" + re.escape(well_name.upper()) + r"(?![0-9A-Za-z])"
            )
            return pattern.search(file_name.upper()) is not None

        files = sorted(
            list(self._data_dir.glob("*.xlsx")) + list(self._data_dir.glob("*.xls")),
            key=lambda p: p.name,
        )
        for w in sorted(self.get_coordinates(), key=lambda w: len(w.name), reverse=True):
            if w.name in registry:
                continue
            for f in files:
                if _token_match(w.name, f.name):
                    registry[w.name] = f
                    break

        for path_str in self._imported_files:
            p = Path(path_str)
            if not p.exists():
                continue
            stem = p.stem
            if stem not in registry:
                registry[stem] = p

        # register_well_file() 的显式登记在重建后以覆盖语义保留：显式
        # 注册表达用户意图（导入、xls→xlsx 原地转换 #566），不能被目录
        # 扫描的启发式结果静默回滚；此前 setdefault 使转换在下一次
        # get_well_file() 重建时失效。
        for name, p in self._registry.items():
            registry[name] = p

        self._registry = {k: v for k, v in registry.items() if v.exists()}

    def get_well_file(self, well_name: str) -> Path | None:
        self._rebuild_registry()
        return self._registry.get(well_name)

    def register_well_file(self, well_name: str, path: Path | str) -> None:
        self._registry[well_name] = Path(path)

    def register_imported_file(self, path: str) -> None:
        if path not in self._imported_files:
            self._imported_files.append(path)
            self._save_imported_files()
        self._rebuild_registry()

    def imported_files(self) -> list[str]:
        return list(self._imported_files)

    def _load_imported_files(self) -> list[str]:
        """读取 data_dir 下持久化的导入文件清单（启动时恢复）。"""
        if not self._imported_files_path.exists():
            return []
        try:
            with open(self._imported_files_path, encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, ValueError):
            return []
        if not isinstance(raw, list):
            return []
        return [str(item) for item in raw if item]

    def _save_imported_files(self) -> None:
        """将导入文件清单持久化到 data_dir 下的 JSON 文件。"""
        try:
            self._imported_files_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._imported_files_path, "w", encoding="utf-8") as f:
                json.dump(self._imported_files, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def rename_well(self, old_name: str, new_name: str) -> None:
        wells = self.get_coordinates()
        for w in wells:
            if w.name == old_name:
                w.name = new_name
                break
        self._coords = wells
        if old_name in self._registry:
            self._registry[new_name] = self._registry.pop(old_name)
        save_well_coordinates(self._coords_path, wells)

    def remove_well(self, name: str) -> None:
        wells = [w for w in self.get_coordinates() if w.name != name]
        self._coords = wells
        self._registry.pop(name, None)
        save_well_coordinates(self._coords_path, wells)

    def add_or_update_well(
        self,
        name: str,
        latitude: float,
        longitude: float,
        file_path: str | Path | None = None,
    ) -> None:
        wells = self.get_coordinates()
        found = False
        for w in wells:
            if w.name == name:
                w.latitude = latitude
                w.longitude = longitude
                found = True
                break
        if not found:
            wells.append(WellCoordinates(name=name, latitude=latitude, longitude=longitude))
        self._coords = wells
        save_well_coordinates(self._coords_path, wells)
        if file_path:
            self.register_well_file(name, file_path)

    def apply_project_wells(self, project_wells: list) -> None:
        """Merge wells from a loaded .gvz project into the catalog."""
        for pw in project_wells:
            self.add_or_update_well(pw.name, pw.latitude, pw.longitude, pw.file_path)
        self._rebuild_registry()

    def list_well_names(self) -> list[str]:
        self._rebuild_registry()
        names = {w.name for w in self.get_coordinates()}
        names.update(self._registry.keys())
        return sorted(names)

    def get_loader_entry(self, well_name: str):
        """Return (loader_fn, path) or None, dispatched by file format.

        #577 residual: LAS imports register real parsed wells, but this
        entry unconditionally returned the Excel loader — clicking an
        imported LAS well dispatched Excel parsing on a .las path.
        """
        path = self.get_well_file(well_name)
        if path is None:
            return None
        if path.suffix.lower() == ".las":
            from src.data.loaders import load_well_log_from_las

            return load_well_log_from_las, path
        return load_well_log_from_excel, path