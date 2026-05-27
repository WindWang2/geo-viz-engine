"""MapPage — native QPainter-based geographic map for well coordinates."""
import json
from pathlib import Path

from PySide6.QtWidgets import QVBoxLayout, QWidget

from geoviz_map import MapCanvas, ReferenceLabel, WellMarker

from src.data.cache import DataCache
from src.data.well_registry import available_wells
from src.utils.paths import get_data_dir

DATA_DIR = get_data_dir()
WELL_COORDS_FILE = DATA_DIR / "well_coordinates.json"
WORLD_GEOJSON_FILE = DATA_DIR / "world.json"
CHINA_GEOJSON_FILE = DATA_DIR / "china_provinces.json"


REFERENCE_LABELS: list[ReferenceLabel] = [
    ReferenceLabel(name="北京 (Beijing)", lng=116.4074, lat=39.9042, kind="capital"),
    ReferenceLabel(name="上海 (Shanghai)", lng=121.4737, lat=31.2304, kind="city"),
    ReferenceLabel(name="广州 (Guangzhou)", lng=113.2644, lat=23.1292, kind="city"),
    ReferenceLabel(name="深圳 (Shenzhen)", lng=114.0579, lat=22.5431, kind="city"),
    ReferenceLabel(name="香港 (Hong Kong)", lng=114.1694, lat=22.3193, kind="city"),
    ReferenceLabel(name="澳门 (Macau)", lng=113.5439, lat=22.1987, kind="city"),
    ReferenceLabel(name="惠州 (Huizhou)", lng=114.4158, lat=23.1109, kind="city"),
    ReferenceLabel(name="珠海 (Zhuhai)", lng=113.5767, lat=22.2707, kind="city"),
    ReferenceLabel(name="汕头 (Shantou)", lng=116.7084, lat=23.3718, kind="city"),
    ReferenceLabel(name="湛江 (Zhanjiang)", lng=110.3649, lat=21.2749, kind="city"),
    ReferenceLabel(name="海口 (Haikou)", lng=110.3308, lat=20.0221, kind="city"),
    ReferenceLabel(name="福州 (Fuzhou)", lng=119.3063, lat=26.0753, kind="city"),
    ReferenceLabel(name="台北 (Taipei)", lng=121.5654, lat=25.0330, kind="city"),
    ReferenceLabel(name="南宁 (Nanning)", lng=108.3200, lat=22.8240, kind="city"),
    ReferenceLabel(name="南海 (South China Sea)", lng=115.5, lat=20.2, kind="sea"),
]


def _load_json(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return {"type": "FeatureCollection", "features": []}


def _coords_to_markers(coords, data_wells: set[str]) -> list[WellMarker]:
    return [
        WellMarker(
            name=w.name,
            lng=w.longitude,
            lat=w.latitude,
            color="#ef4444" if w.name in data_wells else "#6b7280",
            has_data=w.name in data_wells,
        )
        for w in coords
    ]


class MapPage(QWidget):
    def __init__(self, cache: DataCache, well_click_callback=None):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        coords = cache.get_well_coordinates(WELL_COORDS_FILE)
        data_wells = available_wells()
        wells = _coords_to_markers(coords, data_wells)
        world = _load_json(WORLD_GEOJSON_FILE)
        china = _load_json(CHINA_GEOJSON_FILE)

        self.map_canvas = MapCanvas(
            wells=wells,
            world_geojson=world,
            china_geojson=china,
            reference_labels=REFERENCE_LABELS,
            initial_zoom=7.5,
        )
        if well_click_callback is not None:
            self.map_canvas.well_clicked.connect(well_click_callback)
        layout.addWidget(self.map_canvas)
