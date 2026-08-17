"""#702: XML→Excel must discover any 测井曲线-* sheet, not one hardcoded well."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.convert_xml_to_laolong import convert_to_laolong_xls


SS_NS = "urn:schemas-microsoft-com:office:spreadsheet"


def _ss_workbook(sheets: dict[str, list[list[str]]]) -> str:
    parts = [
        '<?xml version="1.0"?>',
        f'<Workbook xmlns:ss="{SS_NS}">',
    ]
    for name, rows in sheets.items():
        parts.append(f'<Worksheet ss:Name="{name}"><Table>')
        for row in rows:
            parts.append("<Row>")
            for cell in row:
                parts.append(f"<ss:Cell><ss:Data>{cell}</ss:Data></ss:Cell>")
            parts.append("</Row>")
        parts.append("</Table></Worksheet>")
    parts.append("</Workbook>")
    return "".join(parts)


def test_convert_discovers_curve_sheet_by_prefix(tmp_path: Path):
    xml = _ss_workbook(
        {
            "测井曲线-OTHER井": [
                ["深度", "GR"],
                ["100", "40"],
                ["110", "50"],
            ],
        }
    )
    src = tmp_path / "other.xml"
    src.write_text(xml, encoding="utf-8")
    out = tmp_path / "other.xlsx"

    convert_to_laolong_xls(str(src), str(out))
    assert out.exists()

    import pandas as pd

    sheets = pd.read_excel(out, sheet_name=None)
    assert "GR" in sheets
    gr = sheets["GR"]
    assert list(gr.columns)[:2] == ["深度", "GR"]
    assert float(gr["深度"].min()) == 100.0
    assert float(gr["GR"].iloc[0]) == 40.0


def test_convert_missing_curve_sheet_raises_clear_error(tmp_path: Path):
    xml = _ss_workbook({"备注": [["说明"], ["无曲线"]]})
    src = tmp_path / "empty.xml"
    src.write_text(xml, encoding="utf-8")
    out = tmp_path / "empty.xlsx"

    with pytest.raises(ValueError, match="测井曲线"):
        convert_to_laolong_xls(str(src), str(out))
