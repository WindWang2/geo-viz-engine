"""Bounded loading of XML well logs (WITSML & SpreadsheetML) for local well-log previews."""

from __future__ import annotations

import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import numpy as np

from .models import CurveData, IntervalItem, LithologyInterval, WellIntervals, WellLogData


def _clean_tag(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _unit_for_header(h_name: str) -> str:
    h_upper = h_name.upper()
    if h_upper in ("DEPT", "DEPTH", "深度", "TVD", "TVDSS"):
        return "m"
    if "GR" in h_upper:
        return "gAPI"
    if "DT" in h_upper:
        return "us/m"
    if any(k in h_name for k in ("孔隙度", "POR", "PORO")):
        return "%"
    if any(k in h_name for k in ("渗透率", "PERM")):
        return "mD"
    return ""


def load_xml_preview(
    path: str,
    *,
    max_curves: int = 12,
    max_samples: int = 2_000,
) -> WellLogData:
    path_obj = Path(path)
    tree = ET.parse(path_obj)
    root = tree.getroot()

    headers: list[str] = []
    rows: list[list[str]] = []
    well_name = path_obj.stem

    # 1. SpreadsheetML / Excel XML (<Table><Row><Cell><Data>)
    all_rows: list[list[str]] = []
    for elem in root.iter():
        if _clean_tag(elem.tag).lower() == "table":
            for child in elem:
                if _clean_tag(child.tag).lower() == "row":
                    row_vals: list[str] = []
                    for cell in child:
                        if _clean_tag(cell.tag).lower() == "cell":
                            cell_text = ""
                            for data_node in cell:
                                if _clean_tag(data_node.tag).lower() == "data":
                                    cell_text = (data_node.text or "").strip()
                                    break
                            if not cell_text and cell.text:
                                cell_text = cell.text.strip()
                            row_vals.append(cell_text)
                    if row_vals:
                        all_rows.append(row_vals)
            if all_rows:
                break

    if all_rows and len(all_rows) > 1:
        headers = [str(h).strip() for h in all_rows[0] if str(h).strip()]
        raw_rows = all_rows[1:]
        if headers and headers[0] in ("井号", "Well", "WELL_NAME", "WELL"):
            well_names = [r[0] for r in raw_rows if r and r[0]]
            if well_names:
                well_name = well_names[0]
        rows = [r[: len(headers)] for r in raw_rows]

    # 2. WITSML / text lines
    if not rows:
        for elem in root.iter():
            tag = _clean_tag(elem.tag).lower()
            if tag in ("logcurveinfo", "curveinfo", "curve"):
                mnemonic = ""
                for child in elem:
                    ctag = _clean_tag(child.tag).lower()
                    if ctag in ("mnemonic", "mnem", "name"):
                        mnemonic = (child.text or "").strip()
                if mnemonic:
                    headers.append(mnemonic)

        for elem in root.iter():
            tag = _clean_tag(elem.tag).lower()
            if tag in ("logdata",):
                lines: list[str] = []
                if elem.text:
                    lines.extend(elem.text.strip().splitlines())
                for child in elem:
                    if _clean_tag(child.tag).lower() in ("data", "row", "line") and child.text:
                        lines.extend(child.text.strip().splitlines())
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = [p.strip() for p in re.split(r"[\s,;]+", line)]
                    if parts:
                        rows.append(parts)
                if rows:
                    break

    if not rows:
        raise ValueError(f"无法解析 XML 测井数据: {path_obj.name}")

    # Find depth column
    depth_idx = -1
    for idx, h in enumerate(headers):
        if h.upper() in ("DEPT", "DEPTH", "深度", "TVD", "TVDSS"):
            depth_idx = idx
            break
    if depth_idx == -1 and len(headers) > 1:
        for idx in range(len(headers)):
            vals = []
            for r in rows[:10]:
                if idx < len(r):
                    try:
                        vals.append(float(r[idx]))
                    except ValueError:
                        pass
            if len(vals) >= 5:
                depth_idx = idx
                break
    if depth_idx == -1:
        depth_idx = 0

    depths: list[float] = []
    curve_val_lists: dict[int, list[float]] = {}

    selected_indices = [
        i for i in range(len(headers))
        if i != depth_idx and headers[i] not in ("井号", "Well", "WELL_NAME")
    ][:max_curves]

    for i in selected_indices:
        curve_val_lists[i] = []

    stride = max(1, math.ceil(len(rows) / max_samples))

    for r_idx, r in enumerate(rows):
        if r_idx % stride != 0 and r_idx != len(rows) - 1:
            continue
        if depth_idx >= len(r):
            continue
        try:
            d_val = float(r[depth_idx])
            if math.isnan(d_val) or d_val <= -9000:
                continue
        except ValueError:
            continue

        depths.append(d_val)
        for i in selected_indices:
            v_val = float("nan")
            if i < len(r):
                try:
                    f = float(r[i])
                    if f > -9000:
                        v_val = f
                except ValueError:
                    pass
            curve_val_lists[i].append(v_val)

    if len(depths) < 2:
        raise ValueError("XML 测井数据采样点小于 2")

    depth_arr = np.asarray(depths, dtype=np.float64)
    top_depth = float(np.nanmin(depth_arr))
    bottom_depth = float(np.nanmax(depth_arr))

    color_palette = [
        "#1d4ed8", "#15803d", "#7c3aed", "#c2410c",
        "#0284c7", "#b91c1c", "#4d7c0f", "#6d28d9",
    ]

    curves: list[CurveData] = []
    for idx_in_sel, col_idx in enumerate(selected_indices):
        h_name = headers[col_idx] if col_idx < len(headers) else f"Curve_{col_idx}"
        val_arr = np.asarray(curve_val_lists[col_idx], dtype=np.float64)
        finite = val_arr[np.isfinite(val_arr)]
        if finite.size:
            vmin, vmax = float(np.min(finite)), float(np.max(finite))
            if math.isclose(vmin, vmax):
                vmax = vmin + 1.0
        else:
            vmin, vmax = 0.0, 100.0

        color = color_palette[idx_in_sel % len(color_palette)]
        unit = _unit_for_header(h_name)

        curves.append(
            CurveData(
                name=h_name,
                unit=unit,
                depth=depth_arr.tolist(),
                values=val_arr.tolist(),
                display_range=(vmin, vmax),
                color=color,
            )
        )

    lithology_list: list[LithologyInterval] = []
    formation_list: list[IntervalItem] = []

    for worksheet_elem in root.iter():
        if _clean_tag(worksheet_elem.tag).lower() == "worksheet":
            w_name = worksheet_elem.attrib.get(
                "{urn:schemas-microsoft-com:office:spreadsheet}Name",
                worksheet_elem.attrib.get("ss:Name", ""),
            )
            w_rows: list[list[str]] = []
            for table in worksheet_elem.iter():
                if _clean_tag(table.tag).lower() == "table":
                    for row in table.iter():
                        if _clean_tag(row.tag).lower() == "row":
                            row_vals: list[str] = []
                            for cell in row.iter():
                                if _clean_tag(cell.tag).lower() == "cell":
                                    txt = ""
                                    for d in cell.iter():
                                        if _clean_tag(d.tag).lower() == "data":
                                            txt = (d.text or "").strip()
                                            break
                                    if not txt and cell.text:
                                        txt = cell.text.strip()
                                    row_vals.append(txt)
                            if row_vals:
                                w_rows.append(row_vals)

            if "岩性" in w_name and len(w_rows) > 1:
                w_h = [x.strip() for x in w_rows[0]]
                top_i = next((i for i, c in enumerate(w_h) if c in ("顶深", "顶TVD", "Top")), -1)
                bot_i = next((i for i, c in enumerate(w_h) if c in ("底深", "底TVD", "Bottom")), -1)
                name_i = next((i for i, c in enumerate(w_h) if "岩性" in c), -1)
                for r in w_rows[1:]:
                    if top_i < len(r) and bot_i < len(r) and name_i < len(r):
                        try:
                            t_val, b_val, n_val = float(r[top_i]), float(r[bot_i]), r[name_i].strip()
                            if n_val and t_val < b_val:
                                lithology_list.append(
                                    LithologyInterval(
                                        top=t_val,
                                        bottom=b_val,
                                        lithology=n_val,
                                        description=n_val,
                                    )
                                )
                        except ValueError:
                            pass

            if any(k in w_name for k in ("地层", "砂层", "层序", "分层")) and len(w_rows) > 1:
                w_h = [x.strip() for x in w_rows[0]]
                top_i = next((i for i, c in enumerate(w_h) if c in ("顶深", "顶TVD", "Top")), -1)
                bot_i = next((i for i, c in enumerate(w_h) if c in ("底深", "底TVD", "Bottom")), -1)
                name_i = next((i for i, c in enumerate(w_h) if c in ("层号", "层名", "相类型", "相")), -1)
                for r in w_rows[1:]:
                    if top_i < len(r) and bot_i < len(r) and name_i < len(r):
                        try:
                            t_val, b_val, n_val = float(r[top_i]), float(r[bot_i]), r[name_i].strip()
                            if n_val and t_val < b_val:
                                formation_list.append(
                                    IntervalItem(top=t_val, bottom=b_val, name=n_val)
                                )
                        except ValueError:
                            pass

    intervals = WellIntervals(formation=formation_list) if formation_list else None

    return WellLogData(
        well_name=well_name,
        top_depth=top_depth,
        bottom_depth=bottom_depth,
        curves=curves,
        lithology=lithology_list,
        intervals=intervals,
    )


__all__ = ["load_xml_preview"]
