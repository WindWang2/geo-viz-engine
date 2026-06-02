from pathlib import Path
from src.data.loaders import load_well_coordinates
from src.data.models import WellCoordinates


class DataCache:
    def __init__(self):
        self._well_coords: list[WellCoordinates] | None = None

    def get_well_coordinates(self, path: Path) -> list[WellCoordinates]:
        if self._well_coords is None:
            self._well_coords = load_well_coordinates(path)
        return self._well_coords

    def invalidate(self):
        self._well_coords = None

    def rename_well(self, old_name: str, new_name: str):
        """Rename a well in the cached coordinate list."""
        if self._well_coords:
            for w in self._well_coords:
                if w.name == old_name:
                    w.name = new_name
                    break

    def remove_well(self, name: str):
        """Remove a well from the cached coordinate list."""
        if self._well_coords:
            self._well_coords = [w for w in self._well_coords if w.name != name]

    def put_file(self, path: str):
        """Register an imported file path in the cache."""
        if not hasattr(self, "_imported_files"):
            self._imported_files: list[str] = []
        if path not in self._imported_files:
            self._imported_files.append(path)

    def imported_files(self) -> list[str]:
        """Return list of imported file paths."""
        if not hasattr(self, "_imported_files"):
            self._imported_files = []
        return list(self._imported_files)
