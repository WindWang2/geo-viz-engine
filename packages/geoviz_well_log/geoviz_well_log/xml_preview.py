"""Bounded loading of XML well logs (WITSML & SpreadsheetML) for local well-log previews."""

from __future__ import annotations

import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import numpy as np

from .models import CurveData, FaciesInterval, IntervalItem, LithologyInterval, WellIntervals, WellLogData


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
    try:
        import lxml.etree as ET
    except ImportError:
        import xml.etree.ElementTree as ET

    tree = ET.parse(str(path_obj))
    root = tree.getroot()

    headers: list[str] = []
    rows: list[list[str]] = []
    well_name = path_obj.stem

    def _local_tag(elem) -> str:
        t = elem.tag
        return t.rsplit("}", 1)[-1] if "}" in t else t

    # Fast direct child iteration for all worksheets
    sheets_data: dict[str, list[list[str]]] = {}
    for child in root:
        if _local_tag(child) == "Worksheet":
            s_name = child.attrib.get(
                "{urn:schemas-microsoft-com:office:spreadsheet}Name",
                child.attrib.get("ss:Name", "Sheet"),
            )
            s_rows: list[list[str]] = []
            for w_child in child:
                if _local_tag(w_child) == "Table":
                    for r_elem in w_child:
                        if _local_tag(r_elem) == "Row":
                            r_vals: list[str] = []
                            for c_elem in r_elem:
                                if _local_tag(c_elem) == "Cell":
                                    txt = ""
                                    for d_elem in c_elem:
                                        if _local_tag(d_elem) == "Data":
                                            txt = (d_elem.text or "").strip()
                                            break
                                    if not txt and c_elem.text:
                                        txt = c_elem.text.strip()
                                    r_vals.append(txt)
                            if r_vals:
                                s_rows.append(r_vals)
            if s_rows:
                sheets_data[s_name] = s_rows

    # Pick 测井曲线 sheet or first sheet for curve data
    curve_sheet_rows: list[list[str]] = []
    for s_name, s_rows in sheets_data.items():
        if "测井曲线" in s_name:
            curve_sheet_rows = s_rows
            break
    if not curve_sheet_rows and sheets_data:
        curve_sheet_rows = next(iter(sheets_data.values()))

    if curve_sheet_rows and len(curve_sheet_rows) > 1:
        headers = [str(h).strip() for h in curve_sheet_rows[0] if str(h).strip()]
        raw_rows = curve_sheet_rows[1:]
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
    facies_list: list[FaciesInterval] = []
    text_desc_list: list[IntervalItem] = []
    horizon_list: list[IntervalItem] = []

    for w_name, w_rows in sheets_data.items():
        if len(w_rows) > 1:
                w_h = [x.strip() for x in w_rows[0]]
                top_i = next((i for i, c in enumerate(w_h) if c in ("顶深", "顶TVD", "深度", "Top")), -1)
                bot_i = next((i for i, c in enumerate(w_h) if c in ("底深", "底TVD", "Bottom")), -1)

                # 1. Lithology (岩性)
                if "岩性" in w_name:
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

                # 2. Stratigraphy & Facies (地层单位、砂层组、沉积相)
                if any(k in w_name for k in ("地层", "砂层", "层序", "分层", "相")):
                    form_i = next((i for i, c in enumerate(w_h) if c in ("层号", "层名", "组", "统")), -1)
                    facies_i = next((i for i, c in enumerate(w_h) if "相" in c), -1)
                    for r in w_rows[1:]:
                        if top_i < len(r) and bot_i < len(r):
                            try:
                                t_val = float(r[top_i])
                                b_val = float(r[bot_i]) if bot_i < len(r) and r[bot_i] else t_val + 1.0
                                if t_val < b_val:
                                    if form_i >= 0 and form_i < len(r) and r[form_i].strip():
                                        formation_list.append(IntervalItem(top=t_val, bottom=b_val, name=r[form_i].strip()))
                                    if facies_i >= 0 and facies_i < len(r) and r[facies_i].strip():
                                        facies_list.append(FaciesInterval(top=t_val, bottom=b_val, facies=r[facies_i].strip()))
                            except ValueError:
                                pass

                # 3. Core & Text annotations / photo descriptions / Facies (取心、文本道)
                if any(k in w_name for k in ("文本", "取心", "说明", "备注")):
                    txt_i = next((i for i, c in enumerate(w_h) if c in ("文本", "描述", "说明", "进尺", "心长")), -1)
                    track_i = next((i for i, c in enumerate(w_h) if c in ("道名", "类型")), -1)
                    for r in w_rows[1:]:
                        if top_i < len(r):
                            try:
                                t_val = float(r[top_i])
                                b_val = float(r[bot_i]) if bot_i >= 0 and bot_i < len(r) and r[bot_i] else t_val + 2.0
                                track_name = r[track_i].strip() if track_i >= 0 and track_i < len(r) else ""
                                val = r[txt_i].strip() if txt_i >= 0 and txt_i < len(r) else ""
                                if not val and track_i >= 0 and track_i < len(r) and track_i != txt_i:
                                    val = r[track_i].strip()

                                if val and t_val < b_val:
                                    if "相" in track_name:
                                        facies_list.append(FaciesInterval(top=t_val, bottom=b_val, facies=val))
                                    else:
                                        text_desc_list.append(IntervalItem(top=t_val, bottom=b_val, name=val))
                            except ValueError:
                                pass

                # 4. Standard Horizon Markers (标准层道)
                if "标准层" in w_name:
                    name_i = next((i for i, c in enumerate(w_h) if c in ("层名", "标准层", "文本")), -1)
                    if name_i >= 0:
                        for r in w_rows[1:]:
                            if top_i < len(r) and name_i < len(r):
                                try:
                                    t_val = float(r[top_i])
                                    n_val = r[name_i].strip()
                                    if n_val:
                                        horizon_list.append(IntervalItem(top=t_val, bottom=t_val + 1.0, name=n_val))
                                except ValueError:
                                    pass

    intervals = WellIntervals(
        formation=formation_list if formation_list else [],
        sequence=horizon_list if horizon_list else [],
        lithology_desc=text_desc_list if text_desc_list else [],
    )

    return WellLogData(
        well_name=well_name,
        top_depth=top_depth,
        bottom_depth=bottom_depth,
        curves=curves,
        lithology=lithology_list,
        facies=facies_list,
        intervals=intervals,
    )


__all__ = ["load_xml_preview"]
