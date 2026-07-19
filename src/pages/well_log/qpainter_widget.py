"""Compatibility import for the historical well-log page widget."""

from geoviz_well_log import WellLogView

QPainterWidget = WellLogView

__all__ = ["QPainterWidget"]
