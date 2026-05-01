from pathlib import Path

from PySide6.QtWidgets import QWidget, QVBoxLayout

from src.data.cache import DataCache
from src.renderers.map_renderer import MapRenderer
from src.pages.well_log_page import _WELL_DATA

DATA_DIR = Path(__file__).parent.parent.parent / "data"
WELL_COORDS_FILE = DATA_DIR / "well_coordinates.json"


class MapPage(QWidget):
    def __init__(self, cache: DataCache, well_click_callback=None):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        wells = cache.get_well_coordinates(WELL_COORDS_FILE)
        data_wells = set(_WELL_DATA.keys())
        self.map_renderer = MapRenderer(wells, well_click_callback, data_wells)
        layout.addWidget(self.map_renderer)
