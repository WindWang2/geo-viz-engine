from __future__ import annotations

from .models import FaciesData, IntervalItem, WellLogData
from .renderer import (
    BaseTrack,
    CurveTrack,
    DepthTrack,
    FaciesTrack,
    IntervalTrack,
    LithologyTrack,
    SystemsTractTrack,
)

_LOG_SCALE_CURVES = {"RT", "RXO"}


def build_qpainter_tracks(data: WellLogData) -> list[BaseTrack]:
    """Convert WellLogData into QPainter track objects for WellLogCanvas.

    Creates tracks only for non-empty data sections.
    Order: depth -> curves -> interval columns -> lithology -> facies -> systems tract.
    """
    tracks: list[BaseTrack] = []

    # 1. Depth track (always)
    tracks.append(DepthTrack(top_depth=data.top_depth, bottom_depth=data.bottom_depth))

    # 2. Curve tracks
    for curve in data.curves:
        is_log = curve.name.upper() in _LOG_SCALE_CURVES
        tracks.append(CurveTrack(
            curves=[curve],
            label=f"{curve.name} ({curve.unit})" if curve.unit else curve.name,
            width=150,
            log_scale=is_log,
        ))

    # 3. Interval tracks from WellIntervals
    if data.intervals is not None:
        iv = data.intervals
        for field_name, label in [
            ("system", "System"),
            ("series", "Series"),
            ("formation", "Formation"),
            ("member", "Member"),
            ("lithology_desc", "Description"),
            ("sequence", "Sequence"),
        ]:
            items = getattr(iv, field_name, None)
            if items:
                tracks.append(IntervalTrack(intervals=items, label=label, width=80))

    # 4. Lithology track
    if data.lithology:
        tracks.append(LithologyTrack(intervals=data.lithology, width=80))

    # 5. Facies track (from intervals.facies if present, else from data.facies)
    facies_data = None
    if data.intervals is not None and data.intervals.facies:
        fd = data.intervals.facies
        if fd.phase or fd.sub_phase or fd.micro_phase:
            facies_data = fd
    if facies_data is None and data.facies:
        phase = [IntervalItem(top=f.top, bottom=f.bottom, name=f.facies) for f in data.facies]
        facies_data = FaciesData(phase=phase)

    if facies_data is not None:
        tracks.append(FaciesTrack(facies_data=facies_data, label="Facies", width=80))

    # 6. Systems tract track
    if data.intervals is not None and data.intervals.systems_tract:
        tracks.append(SystemsTractTrack(intervals=data.intervals.systems_tract, width=60))

    return tracks
