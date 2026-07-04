from pathlib import Path

from src.data.catalog import WellCatalog
from src.data.models import WellCoordinates
from src.data import well_registry


class DataCache:
    """Application data cache — delegates well/catalog state to WellCatalog."""

    def __init__(self):
        self._catalog = WellCatalog()
        well_registry.set_catalog(self._catalog)

    @property
    def catalog(self) -> WellCatalog:
        return self._catalog

    def get_well_coordinates(self, path: Path) -> list[WellCoordinates]:
        return self._catalog.get_coordinates()

    def invalidate(self):
        self._catalog.invalidate()

    def rename_well(self, old_name: str, new_name: str):
        self._catalog.rename_well(old_name, new_name)
        well_registry.refresh_registry()

    def remove_well(self, name: str):
        self._catalog.remove_well(name)
        well_registry.refresh_registry()

    def put_file(self, path: str):
        self._catalog.register_imported_file(path)
        well_registry.refresh_registry()

    def imported_files(self) -> list[str]:
        return self._catalog.imported_files()