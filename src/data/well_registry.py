"""Well registry backed by WellCatalog (dynamic, not import-time frozen)."""
from __future__ import annotations

from pathlib import Path

from src.data.catalog import WellCatalog

_catalog: WellCatalog | None = None


def _get_catalog() -> WellCatalog:
    global _catalog
    if _catalog is None:
        _catalog = WellCatalog()
    return _catalog


def set_catalog(catalog: WellCatalog) -> None:
    """Inject shared catalog instance (called from MainWindow / DataCache)."""
    global _catalog
    _catalog = catalog


def get_well_data(well_name: str):
    """Return (loader_fn, xls_path, config) or None."""
    from geoviz_well_log.configs.laolong1 import laolong1_config

    entry = _get_catalog().get_loader_entry(well_name)
    if entry is None:
        return None
    loader_fn, xls_path = entry
    return loader_fn, xls_path, laolong1_config


def get_well_file(well_name: str) -> Path | None:
    return _get_catalog().get_well_file(well_name)


def available_wells() -> set[str]:
    return set(_get_catalog().list_well_names())


def list_wells() -> list[str]:
    return _get_catalog().list_well_names()


def refresh_registry() -> None:
    _get_catalog().invalidate()
    _get_catalog()._rebuild_registry()