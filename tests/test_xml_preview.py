"""#728: XML interval sheets must not treat a missing column index (-1) as r[-1]."""
from __future__ import annotations

from pathlib import Path

from geoviz_well_log.xml_preview import load_xml_preview


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
                parts.append(f"<Cell><Data>{cell}</Data></Cell>")
            parts.append("</Row>")
        parts.append("</Table></Worksheet>")
    parts.append("</Workbook>")
    return "".join(parts)


def _curve_sheet() -> list[list[str]]:
    return [
        ["深度", "GR"],
        ["100", "40"],
        ["110", "50"],
        ["120", "60"],
    ]


def test_lithology_sheet_without_top_header_does_not_use_last_column(tmp_path: Path):
    xml = _ss_workbook(
        {
            "测井曲线": _curve_sheet(),
            "岩性": [
                ["底深", "岩性", "厚度"],
                ["110", "砂岩", "50"],
            ],
        }
    )
    path = tmp_path / "no_top.xml"
    path.write_text(xml, encoding="utf-8")

    data = load_xml_preview(str(path))
    assert data.lithology == []


def test_lithology_sheet_with_canonical_headers_still_parses(tmp_path: Path):
    xml = _ss_workbook(
        {
            "测井曲线": _curve_sheet(),
            "岩性": [
                ["顶深", "底深", "岩性"],
                ["100", "110", "砂岩"],
            ],
        }
    )
    path = tmp_path / "ok_top.xml"
    path.write_text(xml, encoding="utf-8")

    data = load_xml_preview(str(path))
    assert len(data.lithology) == 1
    assert data.lithology[0].top == 100.0
    assert data.lithology[0].bottom == 110.0
    assert data.lithology[0].lithology == "砂岩"


def test_horizon_sheet_without_top_header_does_not_use_last_column(tmp_path: Path):
    xml = _ss_workbook(
        {
            "测井曲线": _curve_sheet(),
            "标准层": [
                ["层名", "备注"],
                ["T6", "999"],
            ],
        }
    )
    path = tmp_path / "no_horizon_top.xml"
    path.write_text(xml, encoding="utf-8")

    data = load_xml_preview(str(path))
    seq = data.intervals.sequence if data.intervals else []
    assert seq == []


def test_witsml_uses_declared_well_name_instead_of_filename(tmp_path: Path):
    path = tmp_path / "regional_delivery.xml"
    path.write_text(
        """<WITSMLComposite xmlns="http://www.witsml.org/schemas/1series">
  <log>
    <nameWell>XML-REF-01</nameWell>
    <logCurveInfo><mnemonic>DEPT</mnemonic></logCurveInfo>
    <logCurveInfo><mnemonic>GR</mnemonic></logCurveInfo>
    <logData><data>1000,40</data><data>1001,41</data></logData>
  </log>
</WITSMLComposite>""",
        encoding="utf-8",
    )

    data = load_xml_preview(str(path))

    assert data.well_name == "XML-REF-01"
