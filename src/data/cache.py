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
