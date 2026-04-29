import json
from pathlib import Path

from src.data.models import WellCoordinates, WellLogData


def load_well_coordinates(path: Path) -> list[WellCoordinates]:
    if not path.exists():
        return []
    with open(path) as f:
        raw = json.load(f)
    # Support both flat list format and {"wells": [...]} dict format
    if isinstance(raw, dict):
        items = raw.get("wells", [])
    else:
        items = raw
    result = []
    for w in items:
        # Map well_name -> name if needed
        if "well_name" in w and "name" not in w:
            w = {**w, "name": w["well_name"]}
        result.append(WellCoordinates(**w))
    return result


def load_well_log_from_excel(path: Path) -> WellLogData:
    raise NotImplementedError("Excel well log loading not yet implemented")
