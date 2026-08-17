"""#566 / #572 regressions: xls→xlsx registry update and XML sidecar matching."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


# --- #572: XML sidecar association -----------------------------------------


def _write_sidecar(path: Path, phase_name: str) -> None:
    """Professional-XML sidecar with one 沉积相 row in the 文本道 sheet.

    parse_xml_facies reads (skipping the header row): vals[1]=道类型,
    vals[3]=顶深, vals[6]=底深, vals[9]=名称.
    """
    def _row(cells: list[tuple[str, str]]) -> str:
        joined = "".join(
            f'<Cell><Data ss:Type="{typ}">{val}</Data></Cell>' for typ, val in cells
        )
        return f"<Row>{joined}</Row>"

    header = _row([("String", f"h{i}") for i in range(10)])
    data = _row(
        [
            ("Number", "0"),          # 0
            ("String", "沉积相"),      # 1 道类型
            ("String", "x"),          # 2
            ("Number", "1000.0"),     # 3 顶深
            ("String", "x"),          # 4
            ("String", "x"),          # 5
            ("Number", "1100.0"),     # 6 底深
            ("String", "x"),          # 7
            ("String", "x"),          # 8
            ("String", phase_name),   # 9 名称
        ]
    )
    path.write_text(
        f"""<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
 <Worksheet ss:Name="文本道">
  <Table>
   {header}
   {data}
  </Table>
 </Worksheet>
</Workbook>""",
        encoding="utf-8",
    )


def _write_bare_workbook(path: Path) -> None:
    """Workbook with no recognized sheets: empty phase forces sidecar merge."""
    pd.DataFrame({"列1": [1, 2], "列2": [3, 4]}).to_excel(path, index=False)


def _phase_names(data) -> list[str]:
    return [iv.name for iv in data.intervals.facies.phase]


def test_sidecar_picked_by_well_identity_not_shortest_name(tmp_path):
    """#572: wellA must never receive wellB's facies via filename length."""
    from src.data.loaders import load_well_log_laolong1

    # wellB's sidecar has the SHORTER name — the old bug picked it for A.
    _write_bare_workbook(tmp_path / "wellA.xlsx")
    _write_bare_workbook(tmp_path / "wellB.xlsx")
    _write_sidecar(tmp_path / "wellB.xml", "B的相")
    _write_sidecar(tmp_path / "wellA.xml", "A的相")

    data_a = load_well_log_laolong1(tmp_path / "wellA.xlsx", "wellA")
    assert _phase_names(data_a) == ["A的相"]

    data_b = load_well_log_laolong1(tmp_path / "wellB.xlsx", "wellB")
    assert _phase_names(data_b) == ["B的相"]


def test_sidecar_ambiguous_and_missing_cases_skip_merge(tmp_path):
    from src.data.loaders import load_well_log_laolong1

    # No sidecar at all → no merge, no error.
    _write_bare_workbook(tmp_path / "wellC.xlsx")
    data = load_well_log_laolong1(tmp_path / "wellC.xlsx", "wellC")
    assert _phase_names(data) == []

    # Two candidate sidecars whose stems both contain the well name → skip.
    _write_sidecar(tmp_path / "wellC.xml", "C1")
    _write_sidecar(tmp_path / "wellC-旧.xml", "C2")
    data = load_well_log_laolong1(tmp_path / "wellC.xlsx", "wellC")
    assert _phase_names(data) == []

    # Unrelated sidecars in the same directory never leak in.
    _write_bare_workbook(tmp_path / "wellD.xlsx")
    _write_sidecar(tmp_path / "wellE.xml", "E的相")
    data = load_well_log_laolong1(tmp_path / "wellD.xlsx", "wellD")
    assert _phase_names(data) == []


# --- #566: registry update after xls→xlsx conversion ------------------------


def test_update_well_file_points_registry_at_replacement(tmp_path):
    from src.data import well_registry
    from src.data.catalog import WellCatalog

    catalog = WellCatalog()
    (tmp_path / "legacy.xls").write_bytes(b"legacy")   # registry filters on existence
    catalog.register_well_file("legacyWell", tmp_path / "legacy.xls")
    well_registry.set_catalog(catalog)

    assert well_registry.get_well_file("legacyWell") == tmp_path / "legacy.xls"

    converted = tmp_path / "legacy.xlsx"
    converted.write_bytes(b"converted")
    well_registry.update_well_file("legacyWell", converted)

    entry = well_registry.get_well_data("legacyWell")
    assert entry is not None
    loader_fn, path, _config = entry
    assert Path(path) == converted
    assert callable(loader_fn)


def test_update_well_file_unknown_well_raises(tmp_path):
    from src.data import well_registry
    from src.data.catalog import WellCatalog

    well_registry.set_catalog(WellCatalog())
    with pytest.raises(KeyError):
        well_registry.update_well_file("ghost", tmp_path / "ghost.xlsx")


def test_well_registry_has_no_private_dict_registry():
    """#566 contract: the module-level _WELL_REGISTRY is gone for good."""
    from src.data import well_registry

    assert not hasattr(well_registry, "_WELL_REGISTRY")
    assert callable(getattr(well_registry, "update_well_file", None))


def test_update_survives_registry_rebuild(tmp_path):
    """#566 (deep layer): an explicit update must not be reverted by the
    heuristic data-dir scan on the next registry rebuild. The scan would
    happily re-bind the well to its stale filename match."""
    import json

    from src.data import well_registry
    from src.data.catalog import WellCatalog

    (tmp_path / "well_coordinates.json").write_text(
        json.dumps(
            {"wells": [{"well_name": "legacyWell", "longitude": 115.0, "latitude": 31.5}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "legacyWell-matched.xls").write_bytes(b"stale scan match")
    converted = tmp_path / "converted.xlsx"
    converted.write_bytes(b"converted")

    catalog = WellCatalog(data_dir=tmp_path)
    well_registry.set_catalog(catalog)
    catalog.register_well_file("legacyWell", converted)

    # Force multiple rebuilds (get_well_file rebuilds on every call).
    for _ in range(3):
        assert well_registry.get_well_file("legacyWell") == converted
    entry = well_registry.get_well_data("legacyWell")
    assert entry is not None and Path(entry[1]) == converted
