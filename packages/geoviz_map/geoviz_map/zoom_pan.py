"""ZoomPanHandler — mouse drag pan + cursor-anchored wheel zoom."""
from __future__ import annotations

from geoviz_common.zoom_pan import BaseZoomPanHandler

from geoviz_map.viewport import MapViewport


class ZoomPanHandler(BaseZoomPanHandler):
    """Stateless wrt Qt events — call from widget event handlers."""

    def __init__(self, viewport: MapViewport, min_zoom: float = 2.0,
                 max_zoom: float = 18.0):
        super().__init__(viewport, min_zoom, max_zoom)
