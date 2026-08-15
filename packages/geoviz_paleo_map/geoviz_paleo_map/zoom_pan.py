"""ZoomPanHandler — drag pan + cursor-anchored wheel zoom for PaleoMap."""
from __future__ import annotations

from geoviz_common.zoom_pan import BaseZoomPanHandler

from geoviz_paleo_map.viewport import PaleoMapViewport


class ZoomPanHandler(BaseZoomPanHandler):
    """Mutates a PaleoMapViewport based on mouse drag and wheel events."""

    def __init__(self, viewport: PaleoMapViewport,
                 min_zoom: float = 0.1, max_zoom: float = 10.0):
        super().__init__(viewport, min_zoom, max_zoom)
