import json
import math
from .models import WellLogData, CurveData, WellIntervals, IntervalItem

def build_default_payload(data: WellLogData, offset: float = 0.0) -> dict:
    """
    Build a standard ECharts payload from WellLogData.
    This provides a 'sensible default' layout for quick embedding.
    """
    tracks = []
    
    # 1. Depth Track
    tracks.append({
        "type": "DepthTrack", 
        "name": "深度", 
        "width": 6, 
        "depthOffset": offset
    })

    # 2. Add all curves as individual tracks by default
    for curve in data.curves:
        curve_points = [[d + offset, (v if v == v else None)] for d, v in zip(curve.depth, curve.values)]
        tracks.append({
            "type": "CurveTrack",
            "name": curve.name,
            "width": 14,
            "series": [{
                "name": curve.name,
                "color": curve.color,
                "lineStyle": curve.line_style,
                "rangeLabel": f"{curve.display_range[0]} - {curve.display_range[1]}",
                "data": curve_points
            }]
        })

    # 3. Add Lithology if present
    if data.intervals and data.intervals.lithology:
        litho_data = []
        for item in data.intervals.lithology:
            # Simple pattern inference
            pattern = ""
            if "砂" in item.name: pattern = "sandstone"
            elif "泥" in item.name: pattern = "mudstone"
            elif "灰" in item.name: pattern = "limestone"
            elif "白云" in item.name: pattern = "dolomite"
            elif "页" in item.name: pattern = "shale"
            
            litho_data.append({
                "top": item.top + offset,
                "bottom": item.bottom + offset,
                "name": item.name,
                "lithology": pattern,
                "color": "#ffffff" # Default
            })
        
        tracks.append({
            "type": "LithologyTrack",
            "name": "岩性",
            "width": 12,
            "data": litho_data
        })

    return {
        "metadata": {
            "wellName": data.well_name,
            "topDepth": data.top_depth + offset,
            "bottomDepth": data.bottom_depth + offset,
            "depthOffset": offset
        },
        "tracks": tracks
    }
