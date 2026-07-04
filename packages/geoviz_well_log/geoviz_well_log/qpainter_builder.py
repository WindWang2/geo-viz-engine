from __future__ import annotations

from .models import FaciesData, IntervalItem, LithologyInterval, WellLogData, CurveData, LineStyle
from .renderer import (
    BaseTrack,
    CurveTrack,
    DepthTrack,
    FaciesTrack,
    IntervalTrack,
    LithologyTrack,
    SystemsTractTrack,
)

# ECharts CURVE_META colors
CURVE_META = {
    "AC":  {"color": "#1d4ed8", "style": "dashed"},
    "GR":  {"color": "#15803d", "style": "solid"},
    "RT":  {"color": "#b91c1c", "style": "solid"},
    "RXO": {"color": "#ea580c", "style": "dashed"},
}

# Merge groups matching ECharts layout
_MERGE_GROUPS = [
    (["AC", "GR"], "AC/GR"),
    (["RT", "RXO"], "RT/RXO"),
]

_LOG_SCALE_CURVES = {"RT", "RXO"}

# Map track labels to ECharts-style display names
_LABEL_TO_DISPLAY = {
    "深度": "深度 (m)",
    "AC/GR": "AC/GR",
    "RT/RXO": "RT/RXO",
    "系": "系",
    "统": "统",
    "组": "组",
    "岩性": "岩性",
    "岩性描述": "岩性描述",
    "沉积相": "沉积相",
    "体系域": "体系域",
    "层序": "层序",
}


def _apply_curve_meta(curve: CurveData) -> CurveData:
    meta = CURVE_META.get(curve.name, {})
    if not meta:
        return curve
    return CurveData(
        name=curve.name,
        depth=curve.depth,
        values=curve.values,
        display_range=curve.display_range,
        color=meta.get("color", curve.color),
        line_style="dashed" if meta.get("style") == "dashed" else "solid",
    )


def _intervals_to_lithology(items: list[IntervalItem]) -> list[LithologyInterval]:
    """Convert IntervalItem list to LithologyInterval for SVG pattern fills."""
    return [
        LithologyInterval(top=i.top, bottom=i.bottom, lithology=i.name, description=i.name)
        for i in items
    ]


def build_qpainter_tracks(data: WellLogData, merge_groups: list[tuple[list[str], str]] | None = None) -> list[BaseTrack]:
    """Convert WellLogData into QPainter track objects for WellLogCanvas.

    Creates tracks only for non-empty data sections.
    Curves are merged according to merge_groups for ECharts visual parity.
    Order: depth -> curves -> interval columns -> lithology -> facies -> systems tract.
    """
    if merge_groups is None:
        merge_groups = _MERGE_GROUPS

    tracks: list[BaseTrack] = []

    # 1. Depth track (always)
    tracks.append(DepthTrack(top_depth=data.top_depth, bottom_depth=data.bottom_depth, width=60, label="深度"))

    # 2. Curve tracks — merge according to merge_groups
    curve_map = {c.name: c for c in data.curves}
    used: set[str] = set()

    for names, label in merge_groups:

        available = [curve_map[n] for n in names if n in curve_map]
        if not available:
            continue
        styled = [_apply_curve_meta(c) for c in available]
        for c in available:
            used.add(c.name)
        log = any(c.name in _LOG_SCALE_CURVES for c in styled)
        ct = CurveTrack(curves=styled, label=label, width=140, log_scale=log)
        tracks.append(ct)

    # Remaining ungrouped curves (one per track)
    for c in data.curves:
        if c.name not in used:
            styled = _apply_curve_meta(c)
            log = c.name in _LOG_SCALE_CURVES
            ct = CurveTrack(curves=[styled], label=c.name, width=140, log_scale=log)
            tracks.append(ct)

    # 3. Stratigraphy intervals with group_name
    if data.intervals:
        interval_fields = [
            ("system", "系", 50, "地层系统"),
            ("series", "统", 50, "地层系统"),
            ("formation", "组", 50, "地层系统"),
        ]
        for field, label, width, group in interval_fields:
            items = getattr(data.intervals, field, None)
            if items:
                tracks.append(IntervalTrack(
                    intervals=items, label=label, width=width, group_name=group
                ))

    # 4. Lithology — try LithologyInterval list first, then intervals.lithology
    litho_intervals: list[LithologyInterval] = []
    if data.lithology:
        litho_intervals = data.lithology
    elif data.intervals and data.intervals.lithology:
        litho_intervals = _intervals_to_lithology(data.intervals.lithology)
    if litho_intervals:
        tracks.append(LithologyTrack(intervals=litho_intervals, label="岩性", width=80))

    # 5. Facies with group_name
    if data.intervals and data.intervals.facies:
        f = data.intervals.facies
        has_data = any([f.phase, f.sub_phase, f.micro_phase])
        if has_data:
            tracks.append(FaciesTrack(facies_data=f, width=80, nested=True, group_name="沉积相", label="沉积相"))

    # 6. Systems tract
    if data.intervals and data.intervals.systems_tract:
        tracks.append(SystemsTractTrack(intervals=data.intervals.systems_tract, width=60))

    # 7. Sequence
    if data.intervals and data.intervals.sequence:
        tracks.append(IntervalTrack(intervals=data.intervals.sequence, label="层序", width=50))

    # 8. Lithology description
    if data.intervals and data.intervals.lithology_desc:
        tracks.append(IntervalTrack(
            intervals=data.intervals.lithology_desc, label="岩性描述", width=150
        ))

    # Set depth range on all tracks
    for t in tracks:
        t.set_depth_range(data.top_depth, data.bottom_depth)

    return tracks
