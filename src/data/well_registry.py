import json
from pathlib import Path

from src.data.loaders import load_well_log_from_excel

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def _build_well_registry():
    registry = {}
    
    # Defaults/Hardcoded preferences
    registry["HZ25-10-1"] = (load_well_log_from_excel, _DATA_DIR / "HZ25-10-1-laolong.xls")
    registry["老龙1"] = (load_well_log_from_excel, _DATA_DIR / "老龙1井-野外剖面数据整理 .xls")
    
    coords_file = _DATA_DIR / "well_coordinates.json"
    if coords_file.exists():
        try:
            with open(coords_file, "r", encoding="utf-8") as f:
                coords_data = json.load(f)
            short_names = [w["well_name"] for w in coords_data.get("wells", [])]
        except Exception:
            short_names = []
    else:
        short_names = []

    all_files = list(_DATA_DIR.glob("*.xlsx")) + list(_DATA_DIR.glob("*.xls"))
    
    for w_name in short_names:
        if w_name in registry:
            continue
            
        for f in all_files:
            if w_name.upper() in f.name.upper():
                registry[w_name] = (load_well_log_from_excel, f)
                break
                
    return registry


_WELL_REGISTRY: dict[str, tuple] = _build_well_registry()


def get_well_data(well_name: str):
    """Return (loader_fn, xls_path, config) or None."""
    from src.renderers.well_log.configs.laolong1 import laolong1_config

    entry = _WELL_REGISTRY.get(well_name)
    if entry is None:
        return None
    loader_fn, xls_path = entry
    return loader_fn, xls_path, laolong1_config


def available_wells() -> set[str]:
    return set(_WELL_REGISTRY.keys())

