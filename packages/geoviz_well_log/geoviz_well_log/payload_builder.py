import copy
import math
from typing import Callable

from .models import WellLogData, WellIntervals, IntervalItem
from .pattern_map import PATTERN_MAP

# Predefined curve display metadata
CURVE_META = {
    "AC": {"color": "#1d4ed8", "style": "dashed", "range": "40 - 80"},
    "GR": {"color": "#15803d", "style": "solid", "range": "0 - 150"},
    "RT": {"color": "#b91c1c", "style": "solid", "range": "0.1 - 1000"},
    "RXO": {"color": "#ea580c", "style": "dashed", "range": "0.1 - 1000"},
}


def _get_pattern_id(name: str) -> str:
    if not name:
        return ""
    for k in sorted(PATTERN_MAP.keys(), key=len, reverse=True):
        if k in name:
            return PATTERN_MAP[k]
    return ""


def build_curve_track(
    data: WellLogData,
    curve_names: list[str],
    label: str | None = None,
    width: int = 15,
) -> dict | None:
    curves = [c for c in data.curves if c.name in curve_names]
    if not curves:
        return None
    series = []
    for curve in curves:
        meta = CURVE_META.get(curve.name, {
            "color": curve.color, "style": "solid", "range": ""
        })
        points = [
            [d, (v if not math.isnan(v) else None)]
            for d, v in zip(curve.depth, curve.values)
        ]
        series.append({
            "name": curve.name,
            "color": meta["color"],
            "lineStyle": meta["style"],
            "rangeLabel": meta["range"],
            "data": points,
        })
    return {
        "type": "CurveTrack",
        "name": label or curves[0].name,
        "width": width,
        "series": series,
    }


def build_interval_track(
    items: list[IntervalItem],
    name: str,
    width: int = 8,
    color: str = "#ffffff",
    parent: str | None = None,
    vertical: bool = False,
    apply_pattern: bool = False,
) -> dict | None:
    if not items:
        return None
    return {
        "type": "IntervalTrack",
        "name": name,
        "width": width,
        "parentGroup": parent,
        "textOrientation": "vertical" if vertical else "horizontal",
        "data": [
            {
                "top": i.top,
                "bottom": i.bottom,
                "name": i.name,
                "color": color,
                "lithology": _get_pattern_id(i.name) if apply_pattern else "",
            }
            for i in items
        ],
    }


def build_depth_track(width: int = 6) -> dict:
    return {"type": "DepthTrack", "name": "深度\n(m)", "width": width}


def build_lithology_track(
    data: WellLogData,
    width: int = 9,
    color: str = "#cbd5e0",
) -> dict | None:
    l_data = []
    if hasattr(data, "lithology") and data.lithology:
        l_data.extend(data.lithology)
    if data.intervals and data.intervals.lithology:
        l_data.extend(data.intervals.lithology)
    if not l_data:
        return None
    return {
        "type": "LithologyTrack",
        "name": "岩性",
        "width": width,
        "data": [
            {
                "top": i.top,
                "bottom": i.bottom,
                "lithology": _get_pattern_id(i.name),
                "name": i.name,
                "color": color,
            }
            for i in l_data
        ],
    }


def build_merged_curve_track(
    track_pool: dict[str, dict],
    curve_names: list[str],
    width: int = 14,
) -> dict:
    palette = ["#1d4ed8", "#dc2626", "#15803d", "#ea580c", "#8b5cf6"]
    series = []
    for idx, name in enumerate(curve_names):
        t = track_pool.get(name)
        if t and "series" in t:
            for s in copy.deepcopy(t["series"]):
                s["color"] = palette[idx % len(palette)]
                series.append(s)
    return {
        "type": "CurveTrack",
        "name": "/".join(curve_names),
        "width": width,
        "series": series,
    }


def build_systems_tract_track(
    items: list[IntervalItem],
    width: int = 7,
) -> dict | None:
    if not items:
        return None
    def _shape(name: str) -> str:
        upper = name.upper()
        if "TST" in upper:
            return "triangle-up"
        if "HST" in upper:
            return "triangle-down"
        return "rect"

    def _color(name: str) -> str:
        upper = name.upper()
        if "TST" in upper:
            return "#93c5fd"
        if "HST" in upper:
            return "#fde047"
        return "#f8fafc"

    return {
        "type": "IntervalTrack",
        "name": "体系域",
        "width": width,
        "data": [
            {
                "top": i.top,
                "bottom": i.bottom,
                "name": i.name,
                "shape": _shape(i.name),
                "color": _color(i.name),
            }
            for i in items
        ],
    }


def build_tracks_from_data(data: WellLogData) -> dict[str, dict]:
    """Build track pool from WellLogData (legacy format with intervals)."""
    pool: dict[str, dict] = {}
    ivs = data.intervals

    # 1. Stratigraphy
    if ivs:
        for field, label in [("system", "系"), ("series", "统"), ("formation", "组")]:
            t = build_interval_track(
                getattr(ivs, field), label, width=4, parent="地层系统", vertical=True
            )
            if t:
                pool[label] = t

    # 2. Individual curves
    for c_name in ["AC", "GR", "RT", "RXO"]:
        t = build_curve_track(data, [c_name], c_name, width=14)
        if t:
            pool[c_name] = t

    # 3. Depth
    pool["深度"] = build_depth_track()

    # 4. Lithology
    t = build_lithology_track(data)
    if t:
        pool["岩性"] = t

    # 5. Description
    if ivs and ivs.lithology_desc:
        t = build_interval_track(ivs.lithology_desc, "岩性描述", width=22, vertical=False)
        if t:
            pool["岩性描述"] = t

    # 6. Facies
    if ivs and ivs.facies:
        for field, label in [("micro_phase", "微相"), ("sub_phase", "亚相"), ("phase", "相")]:
            t = build_interval_track(
                getattr(ivs.facies, field), label,
                width=8, parent="沉积相", color="#ecfeff", apply_pattern=True,
            )
            if t:
                pool[label] = t

    # 7. Systems tract
    if ivs and ivs.systems_tract:
        t = build_systems_tract_track(ivs.systems_tract)
        if t:
            pool["体系域"] = t

    # 8. Sequence
    if ivs and ivs.sequence:
        t = build_interval_track(ivs.sequence, "层序", width=4, vertical=True)
        if t:
            pool["层序"] = t

    return pool


# --- Default active track names for legacy format ---
LEGACY_DEFAULT_ACTIVE = {
    "系", "统", "组", "地层系统",
    "AC", "GR", "深度", "岩性", "岩性剖面",
    "RT", "RXO", "岩性描述",
    "微相", "亚相", "相", "体系域", "层序",
}

# Default display order for legacy format
LEGACY_DEFAULT_ORDER = [
    "地层系统 (系/统/组)",
    "曲线: AC + GR",
    "深度 (m)",
    "岩性",
    "曲线: RT + RXO",
    "岩性描述",
    "沉积相 (微相/亚相/相)",
    "体系域",
    "层序",
]


def build_legacy_display_items(pool: dict[str, dict]) -> list[str]:
    """Build ordered display item list from track pool (legacy format)."""
    items = []
    if any(k in pool for k in ["系", "统", "组"]):
        items.append("地层系统 (系/统/组)")
    if "AC" in pool and "GR" in pool:
        items.append("曲线: AC + GR")
    elif "AC" in pool:
        items.append("曲线: AC")
    elif "GR" in pool:
        items.append("曲线: GR")
    if "深度" in pool:
        items.append("深度 (m)")
    if "岩性" in pool:
        items.append("岩性")
    if "RT" in pool and "RXO" in pool:
        items.append("曲线: RT + RXO")
    elif "RT" in pool:
        items.append("曲线: RT")
    elif "RXO" in pool:
        items.append("曲线: RXO")
    if "岩性描述" in pool:
        items.append("岩性描述")
    if any(k in pool for k in ["微相", "亚相", "相"]):
        items.append("沉积相 (微相/亚相/相)")
    if "体系域" in pool:
        items.append("体系域")
    if "层序" in pool:
        items.append("层序")
    return items


# --- AI prediction track builders ---

def build_ai_prediction_tracks(
    records: list[dict],
    track_pool: dict[str, dict],
) -> list[str]:
    """Build AI facies + confidence tracks from prediction records.

    Adds 'AI预测相' and 'AI预测置信度' to track_pool.
    Returns list of track names added.
    """
    data_len = len(records)

    # Calculate bottom for each record
    for i in range(data_len):
        if i < data_len - 1:
            records[i]["bottom"] = records[i + 1]["深度"]
        else:
            records[i]["bottom"] = records[i]["深度"] + 0.125

    # Merge contiguous records for facies track
    merged_facies = _merge_contiguous(records, key="预测相")
    track_facies = {
        "type": "IntervalTrack",
        "name": "AI预测相",
        "width": 8,
        "textOrientation": "vertical",
        "data": [
            {
                "top": r["top"],
                "bottom": r["bottom"],
                "name": str(r["预测相"]),
                "color": _get_facies_color(r["预测相"]),
                "lithology": "",
            }
            for r in merged_facies
        ],
    }

    # Confidence track: raw transparent items + merged display items
    conf_data = []
    for r in records:
        conf_data.append({
            "top": r["深度"],
            "bottom": r["bottom"],
            "name": f"{float(r.get('置信度', 0.5)) * 100:.1f}%",
            "color": "transparent",
            "lithology": "",
        })

    merged_conf = _merge_contiguous_by_threshold(
        records, key="置信度", threshold=0.01
    )
    for r in merged_conf:
        conf_data.append({
            "top": r["top"],
            "bottom": r["bottom"],
            "name": "",
            "color": _get_confidence_color(r["置信度"]),
            "lithology": "",
        })

    track_confidence = {
        "type": "IntervalTrack",
        "name": "AI预测置信度",
        "width": 8,
        "textOrientation": "horizontal",
        "data": conf_data,
    }

    track_pool["AI预测相"] = track_facies
    track_pool["AI预测置信度"] = track_confidence
    return ["AI预测相", "AI预测置信度"]


def _merge_contiguous(records: list[dict], key: str) -> list[dict]:
    if not records:
        return []
    result = []
    group_top = records[0]["深度"]
    group_bottom = records[0]["bottom"]
    group_val = records[0][key]
    for r in records[1:]:
        if r[key] == group_val:
            group_bottom = r["bottom"]
        else:
            result.append({"top": group_top, "bottom": group_bottom, key: group_val})
            group_top = r["深度"]
            group_bottom = r["bottom"]
            group_val = r[key]
    result.append({"top": group_top, "bottom": group_bottom, key: group_val})
    return result


def _merge_contiguous_by_threshold(
    records: list[dict], key: str, threshold: float
) -> list[dict]:
    if not records:
        return []
    result = []
    group_top = records[0]["深度"]
    group_bottom = records[0]["bottom"]
    group_val = records[0].get(key, 0.5)
    for r in records[1:]:
        r_val = r.get(key, 0.5)
        if abs(r_val - group_val) <= threshold:
            group_bottom = r["bottom"]
        else:
            result.append({"top": group_top, "bottom": group_bottom, key: group_val})
            group_top = r["深度"]
            group_bottom = r["bottom"]
            group_val = r_val
    result.append({"top": group_top, "bottom": group_bottom, key: group_val})
    return result


def _get_facies_color(facies_name: str) -> str:
    colors = {
        "1": "#2563eb", "2": "#3b82f6", "3": "#60a5fa",
        "砂岩": "#fef08a", "泥岩": "#94a3b8", "灰岩": "#fca5a5",
    }
    return colors.get(str(facies_name), "#cbd5e1")


def _get_confidence_color(val: float) -> str:
    try:
        val = max(0.0, min(1.0, float(val)))
    except (ValueError, TypeError):
        val = 0.5
    if val < 0.25:
        r, g, b = 0, int(val * 4.0 * 255), 255
    elif val < 0.5:
        r, g, b = 0, 255, int((0.5 - val) * 4.0 * 255)
    elif val < 0.75:
        r, g, b = int((val - 0.5) * 4.0 * 255), 255, 0
    else:
        r, g, b = 255, int((1.0 - val) * 4.0 * 255), 0
    return f"#{r:02x}{g:02x}{b:02x}"
