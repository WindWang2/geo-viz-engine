"""Data models for geoviz_map."""
from typing import Literal

from pydantic import BaseModel


class WellMarker(BaseModel):
    """A single well point on the map."""

    name: str
    lng: float
    lat: float
    color: str  # CSS-style hex, e.g. "#ef4444"
    has_data: bool = False


class ReferenceLabel(BaseModel):
    """A non-interactive geographic reference label (city, sea, capital)."""

    name: str
    lng: float
    lat: float
    kind: Literal["city", "capital", "sea"]
