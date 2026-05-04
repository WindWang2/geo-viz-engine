from pathlib import Path

from PySide6.QtWidgets import QWidget, QVBoxLayout

from src.data.cache import DataCache
from src.data.well_registry import available_wells
from src.renderers.map_renderer import MapRenderer

DATA_DIR = Path(__file__).parent.parent.parent / "data"
WELL_COORDS_FILE = DATA_DIR / "well_coordinates.json"


class MapPage(QWidget):
    def __init__(self, cache: DataCache, well_click_callback=None):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        wells = cache.get_well_coordinates(WELL_COORDS_FILE)
        data_wells = available_wells()
        self.map_renderer = MapRenderer(wells, well_click_callback, data_wells)
        layout.addWidget(self.map_renderer)
