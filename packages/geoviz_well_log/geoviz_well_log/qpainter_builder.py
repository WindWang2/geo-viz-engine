from __future__ import annotations

from .models import FaciesData, IntervalItem, LithologyInterval, WellLogData, CurveData, LineStyle
from .renderer import (
    BaseTrack,
    CurveTrack,
    DepthTrack,
    FaciesTrack,
    IntervalTrack,
    LithologyTrack,
    MarkerTrack,
    SystemsTractTrack,
)
from .tracks.image_track import ImageTrack, CorePhotoSegment

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
    style = meta.get("style")
    line_style = "dashed" if style == "dashed" else curve.line_style
    return CurveData(
        name=curve.name,
        unit=curve.unit,
        depth=curve.depth,
        values=curve.values,
        display_range=curve.display_range,
        color=meta.get("color", curve.color),
        line_style=line_style,
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

    # 2. Stratigraphy intervals with group_name (系, 统, 组) — placed right after Depth
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

    # 3. Lithology — try LithologyInterval list first, then intervals.lithology
    litho_intervals: list[LithologyInterval] = []
    if data.lithology:
        litho_intervals = data.lithology
    elif data.intervals and data.intervals.lithology:
        litho_intervals = _intervals_to_lithology(data.intervals.lithology)
    if litho_intervals:
        tracks.append(LithologyTrack(intervals=litho_intervals, label="岩性", width=80))

    # 4. Facies with group_name
    if data.facies:
        facies_items = [IntervalItem(top=f.top, bottom=f.bottom, name=f.facies) for f in data.facies]
        tracks.append(IntervalTrack(intervals=facies_items, label="沉积相", width=80))
    elif data.intervals and data.intervals.facies:
        f = data.intervals.facies
        has_data = any([f.phase, f.sub_phase, f.micro_phase])
        if has_data:
            tracks.append(FaciesTrack(facies_data=f, width=80, nested=True, group_name="沉积相", label="沉积相"))

    # 5. Systems tract
    if data.intervals and data.intervals.systems_tract:
        tracks.append(SystemsTractTrack(intervals=data.intervals.systems_tract, width=60))

    # 6. Sequence
    if data.intervals and data.intervals.sequence:
        tracks.append(IntervalTrack(intervals=data.intervals.sequence, label="层序", width=50))

    # 7. Core photo & text description track (照片/文本描述)
    if data.intervals and data.intervals.lithology_desc:
        image_track = ImageTrack(name="照片/文本描述", width=180)
        for item in data.intervals.lithology_desc:
            photo = CorePhotoSegment(
                depth_top=item.top,
                depth_bottom=item.bottom,
                title=item.name,
            )
            image_track.add_core_photo(photo)
        tracks.append(image_track)

    # 8. Curve tracks — merge according to merge_groups. Duplicate
    # mnemonics must ALL render (#584): a name-keyed dict kept only the
    # last column, and name-based `used` bookkeeping then hid every other
    # duplicate from the ungrouped pass as well.
    curve_map: dict[str, list] = {}
    for c in data.curves:
        curve_map.setdefault(c.name, []).append(c)
    used: set[int] = set()  # id() of consumed curve objects

    for names, label in merge_groups:
        available = [c for n in names for c in curve_map.get(n, [])]
        if not available:
            continue
        styled = [_apply_curve_meta(c) for c in available]
        used.update(id(c) for c in available)
        log = any(c.name in _LOG_SCALE_CURVES for c in styled)
        ct = CurveTrack(curves=styled, label=label, width=140, log_scale=log)
        tracks.append(ct)

    # Remaining ungrouped curves (one per track)
    for c in data.curves:
        if id(c) not in used:
            styled = _apply_curve_meta(c)
            log = c.name in _LOG_SCALE_CURVES
            ct = CurveTrack(curves=[styled], label=c.name, width=140, log_scale=log)
            tracks.append(ct)

    # 9. Formation-top markers overlay — consumed from duck-typed
    #    ``data.markers`` (workbench WellLogDataWithMarkers). The track is a
    #    zero-width full-canvas overlay, so it never changes the layout and no
    #    track is produced when there are no markers.
    markers = getattr(data, "markers", None) or []
    if markers:
        tracks.append(MarkerTrack(markers=markers))

    # Set depth range on all tracks
    for t in tracks:
        t.set_depth_range(data.top_depth, data.bottom_depth)

    return tracks
