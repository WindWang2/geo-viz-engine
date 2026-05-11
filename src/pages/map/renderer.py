import json
import tempfile
import os
from urllib.parse import parse_qs

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView


MAPLIBRE_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet" />
<style>
  body {{ margin: 0; padding: 0; }}
  #map {{ position: absolute; top: 0; bottom: 0; width: 100%; height: 100%; }}
</style>
</head>
<body>
<div id="map"></div>
<script>
  const wells = {wells_json};
  const center_lat = {center_lat};
  const center_lng = {center_lng};

  function notifyWellClicked(name) {{
    // Encode well name as query param to avoid host-encoding issues with CJK
    window.location.href = 'well://click?name=' + encodeURIComponent(name);
  }}

  const map = new maplibregl.Map({{
    container: 'map',
    style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
    center: [center_lng, center_lat],
    zoom: 7
  }});

  map.on('load', () => {{
    map.addSource('wells', {{
      type: 'geojson',
      data: wells
    }});
    map.addLayer({{
      id: 'well-stars',
      type: 'circle',
      source: 'wells',
      paint: {{
        'circle-radius': 8,
        'circle-color': ['get', 'color'],
        'circle-stroke-width': 1.5,
        'circle-stroke-color': '#fff'
      }}
    }});
    map.addLayer({{
      id: 'well-labels',
      type: 'symbol',
      source: 'wells',
      layout: {{
        'text-field': ['get', 'name'],
        'text-size': 12,
        'text-offset': [0, 1.5],
        'text-anchor': 'top',
        'text-allow-overlap': false
      }},
      paint: {{
        'text-color': ['case', ['get', 'has_data'], '#e2e8f0', '#6b7280'],
        'text-halo-color': '#1a202c',
        'text-halo-width': 1
      }}
    }});

    map.on('click', 'well-stars', (e) => {{
      notifyWellClicked(e.features[0].properties.name);
    }});
    map.on('click', 'well-labels', (e) => {{
      notifyWellClicked(e.features[0].properties.name);
    }});

    map.on('mouseenter', 'well-stars', () => {{ map.getCanvas().style.cursor = 'pointer'; }});
    map.on('mouseleave', 'well-stars', () => {{ map.getCanvas().style.cursor = ''; }});
    map.on('mouseenter', 'well-labels', () => {{ map.getCanvas().style.cursor = 'pointer'; }});
    map.on('mouseleave', 'well-labels', () => {{ map.getCanvas().style.cursor = ''; }});
  }});
</script>
</body>
</html>"""


def build_geojson(wells: list, data_wells: set[str] | None = None) -> str:
    data_wells = data_wells or set()
    features = []
    for w in wells:
        has_data = w.name in data_wells
        features.append({
            "type": "Feature",
            "properties": {
                "name": w.name,
                "color": "#ef4444" if has_data else "#6b7280",
                "has_data": has_data,
            },
            "geometry": {"type": "Point", "coordinates": [w.longitude, w.latitude]},
        })
    raw = json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False)
    # Prevent </script> injection when embedded in HTML
    return raw.replace("</", "<\\/")


class _MapPage(QWebEnginePage):
    def __init__(self, well_click_callback, parent=None):
        super().__init__(parent)
        self._callback = well_click_callback
        # Allow file:// page to load CDN scripts (maplibre-gl)
        self.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )

    def acceptNavigationRequest(self, url: QUrl, nav_type, is_main_frame: bool) -> bool:
        scheme = url.scheme()
        if scheme == "well":
            params = parse_qs(url.query())
            names = params.get("name", [])
            if names and self._callback:
                self._callback(names[0])
            return False  # Block navigation — we handled it
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


class MapRenderer(QWebEngineView):
    def __init__(self, wells: list, well_click_callback=None,
                 data_wells: set[str] | None = None):
        super().__init__()
        self.setPage(_MapPage(well_click_callback, self))

        geojson = build_geojson(wells, data_wells)
        center_lat = sum(w.latitude for w in wells) / len(wells) if wells else 38
        center_lng = sum(w.longitude for w in wells) / len(wells) if wells else 117
        html = MAPLIBRE_HTML.format(
            wells_json=geojson, center_lat=center_lat, center_lng=center_lng,
        )

        # Write HTML to a temp file and load via file:// so that custom-scheme
        # navigation (well://) is not blocked by Chromium's data: URL security policy.
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8"
        )
        tmp.write(html)
        tmp.close()
        self._tmp_html = tmp.name
        self.load(QUrl.fromLocalFile(tmp.name))

    def _cleanup_tmp(self):
        if hasattr(self, "_tmp_html") and self._tmp_html:
            try:
                os.unlink(self._tmp_html)
            except OSError:
                pass
            self._tmp_html = None

    def closeEvent(self, event):
        self._cleanup_tmp()
        super().closeEvent(event)

    def __del__(self):
        self._cleanup_tmp()
