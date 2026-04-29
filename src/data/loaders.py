import json
from pathlib import Path

from src.data.models import WellCoordinates, WellLogData


def load_well_coordinates(path: Path) -> list[WellCoordinates]:
    if not path.exists():
        return []
    with open(path) as f:
        raw = json.load(f)
    return [WellCoordinates(**w) for w in raw]


def load_well_log_from_excel(path: Path) -> WellLogData:
    raise NotImplementedError("Excel well log loading not yet implemented")
