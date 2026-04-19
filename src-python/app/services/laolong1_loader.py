"""Load and parse 老龙1井 XLS data into WellLogData model."""
from __future__ import annotations

import os
from typing import Optional

import pandas as pd

from app.models.well_log import (
    CurveData,
    FaciesData,
    IntervalItem,
    WellIntervals,
    WellLogData,
)

_XLS_PATH = os.path.join(
    os.environ.get("LAOLONG1_DATA_DIR", "/mnt/c/Users/wangj.KEVIN/Downloads/可视化引擎-示例数据"),
    "老龙1井-野外剖面数据整理 .xls",
)

_cache: Optional[WellLogData] = None


def _parse_intervals(df: pd.DataFrame, name_col: str = "层号", text_col: str = "文本") -> list[IntervalItem]:
    items: list[IntervalItem] = []
    for _, row in df.iterrows():
        name = row.get(name_col)
        if pd.isna(name):
            name = row.get(text_col)
        if pd.isna(name):
            name = row.get("岩性")
        if pd.isna(name) or pd.isna(row.get("顶深")) or pd.isna(row.get("底深")):
            continue
        items.append(IntervalItem(
            top=float(row["顶深"]),
            bottom=float(row["底深"]),
            name=str(name).strip(),
        ))
    return items


def _parse_curve_sheet(df: pd.DataFrame, depth_col: str, curve_cols: list[str],
                       units: dict[str, str], colors: dict[str, str],
                       display_ranges: dict[str, tuple[float, float]],
                       line_styles: dict[str, str] | None = None) -> list[CurveData]:
    curves: list[CurveData] = []
    for col in curve_cols:
        if col not in df.columns:
            continue
        vals = pd.to_numeric(df[col], errors="coerce").dropna()
        depths = pd.to_numeric(df[depth_col], errors="coerce")
        valid = vals.index.intersection(depths.index)
        if len(valid) == 0:
            continue
        data_vals = vals.loc[valid].tolist()
        depth_vals = depths.loc[valid].tolist()
        lo, hi = display_ranges.get(col, (float(min(data_vals)), float(max(data_vals))))
        curves.append(CurveData(
            name=col,
            unit=units.get(col, ""),
            data=data_vals,
            depth=depth_vals,
            min_value=float(min(data_vals)),
            max_value=float(max(data_vals)),
            display_range=(lo, hi),
            color=colors.get(col, "#000000"),
            line_style=(line_styles or {}).get(col, "solid"),
        ))
    return curves


def load_laolong1(xls_path: str | None = None) -> WellLogData:
    global _cache
    if _cache is not None:
        return _cache

    path = xls_path or _XLS_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(f"老龙1井 XLS not found: {path}")

    xls = pd.ExcelFile(path)

    # --- Curves ---
    # AC + GR
    df_ac = pd.read_excel(xls, sheet_name="AC、GR")
    ac_gr = _parse_curve_sheet(
        df_ac, depth_col="深度", curve_cols=["AC", "GR"],
        units={"AC": "us/ft", "GR": "API"},
        colors={"AC": "#0000CC", "GR": "#00AA00"},
        display_ranges={"AC": (40.0, 80.0), "GR": (0.0, 150.0)},
        line_styles={"AC": "dashed", "GR": "solid"},
    )

    # RT + RXO
    df_rt = pd.read_excel(xls, sheet_name="RT、RXO")
    rt_rxo = _parse_curve_sheet(
        df_rt, depth_col="深度", curve_cols=["RT", "RXO"],
        units={"RT": "ohm.m", "RXO": "ohm.m"},
        colors={"RT": "#AA0000", "RXO": "#CC6600"},
        display_ranges={"RT": (0.1, 1000.0), "RXO": (0.1, 500.0)},
        line_styles={"RT": "solid", "RXO": "dashed"},
    )

    # SH + PERM + PHIE
    df_por = pd.read_excel(xls, sheet_name="POR、SH、PERM")
    sh_perm_phie = _parse_curve_sheet(
        df_por, depth_col="#DEPTH", curve_cols=["SH", "PERM", "PHIE"],
        units={"SH": "v/v", "PERM": "mD", "PHIE": "v/v"},
        colors={"SH": "#8B4513", "PERM": "#4B0082", "PHIE": "#008080"},
        display_ranges={"SH": (0.0, 0.5), "PERM": (0.0, 10.0), "PHIE": (0.0, 0.15)},
        line_styles={"SH": "solid", "PERM": "dashed", "PHIE": "dotted"},
    )

    all_curves = ac_gr + rt_rxo + sh_perm_phie

    # Depth range from curves
    all_depths = [d for c in all_curves for d in c.depth]
    depth_start = min(all_depths) if all_depths else 2515.0
    depth_end = max(all_depths) if all_depths else 2610.0
    depth_step = 0.125

    # --- Intervals ---
    # 地层系统
    df_strat = pd.read_excel(xls, sheet_name="地层系统")
    strat_groups: list[list[IntervalItem]] = []
    current: list[IntervalItem] = []
    for _, row in df_strat.iterrows():
        name = row.get("层号")
        top_val = row.get("顶深")
        bot_val = row.get("底深")
        # Skip NaN separator rows
        if pd.isna(name) or pd.isna(top_val):
            if current:
                strat_groups.append(current)
                current = []
            continue
        name_str = str(name).strip()
        # Skip repeated header rows and non-data rows
        if name_str in ("层号", "顶深") or str(top_val).strip() in ("顶深", "底深"):
            if current:
                strat_groups.append(current)
                current = []
            continue
        try:
            current.append(IntervalItem(top=float(top_val), bottom=float(bot_val), name=name_str))
        except (ValueError, TypeError):
            if current:
                strat_groups.append(current)
                current = []
            continue
    if current:
        strat_groups.append(current)

    series = strat_groups[0] if len(strat_groups) > 0 else []
    system = strat_groups[1] if len(strat_groups) > 1 else []
    formation = strat_groups[2] if len(strat_groups) > 2 else []
    member = formation  # no separate member data

    # 岩性剖面
    df_litho = pd.read_excel(xls, sheet_name="岩性剖面")
    litho_intervals = _parse_intervals(df_litho, name_col="岩性", text_col="岩性")

    # 岩性描述
    df_litho_desc = pd.read_excel(xls, sheet_name="岩性描述")
    litho_desc = _parse_intervals(df_litho_desc, name_col="文本", text_col="文本")

    # 微相 / 亚相 / 相 — extend to cover full depth range
    df_micro = pd.read_excel(xls, sheet_name="微相")
    micro_phase = _parse_intervals(df_micro, text_col="文本")
    if micro_phase:
        micro_phase[0] = IntervalItem(top=depth_start, bottom=micro_phase[0].bottom, name=micro_phase[0].name)
        micro_phase[-1] = IntervalItem(top=micro_phase[-1].top, bottom=depth_end, name=micro_phase[-1].name)

    df_sub = pd.read_excel(xls, sheet_name="亚相")
    sub_phase = _parse_intervals(df_sub, text_col="文本")
    if sub_phase:
        sub_phase[0] = IntervalItem(top=depth_start, bottom=sub_phase[0].bottom, name=sub_phase[0].name)
        sub_phase[-1] = IntervalItem(top=sub_phase[-1].top, bottom=depth_end, name=sub_phase[-1].name)

    df_phase = pd.read_excel(xls, sheet_name="相")
    phase = _parse_intervals(df_phase, text_col="文本")
    if phase:
        phase[0] = IntervalItem(top=depth_start, bottom=phase[0].bottom, name=phase[0].name)
        phase[-1] = IntervalItem(top=phase[-1].top, bottom=depth_end, name=phase[-1].name)

    # 层序 — extend to cover full depth range
    df_seq = pd.read_excel(xls, sheet_name="层序")
    seq_rows = df_seq.dropna(subset=["顶深", "底深"])
    systems_tract: list[IntervalItem] = []
    sequence: list[IntervalItem] = []
    in_second_group = False
    for _, row in seq_rows.iterrows():
        text = str(row.get("文本", "")).strip()
        if text == "文本" or not text or text == "nan":
            in_second_group = True
            continue
        item = IntervalItem(top=float(row["顶深"]), bottom=float(row["底深"]), name=text)
        if in_second_group:
            sequence.append(item)
        else:
            systems_tract.append(item)
    if systems_tract:
        systems_tract[0] = IntervalItem(top=depth_start, bottom=systems_tract[0].bottom, name=systems_tract[0].name)
        systems_tract[-1] = IntervalItem(top=systems_tract[-1].top, bottom=depth_end, name=systems_tract[-1].name)
    if sequence:
        sequence[0] = IntervalItem(top=depth_start, bottom=sequence[0].bottom, name=sequence[0].name)
        sequence[-1] = IntervalItem(top=sequence[-1].top, bottom=depth_end, name=sequence[-1].name)

    intervals = WellIntervals(
        series=series,
        system=system,
        formation=formation,
        member=member,
        lithology=litho_intervals if litho_intervals else litho_desc,
        systems_tract=systems_tract,
        sequence=sequence,
        facies=FaciesData(phase=phase, sub_phase=sub_phase, micro_phase=micro_phase),
    )

    _cache = WellLogData(
        well_id="LAOLONG-1",
        well_name="老龙1井",
        depth_start=depth_start,
        depth_end=depth_end,
        depth_step=depth_step,
        location=None,
        longitude=None,
        latitude=None,
        curves=all_curves,
        intervals=intervals,
    )
    return _cache
