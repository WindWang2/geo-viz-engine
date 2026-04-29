import json

from PySide6.QtCore import QUrl, Slot, QObject
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView


class MapBridge(QObject):
    """Bridge for JS→Python communication via WebChannel."""

    def __init__(self):
        super().__init__()
        self._callback = None

    def set_well_click_callback(self, callback):
        self._callback = callback

    @Slot(str)
    def onWellClicked(self, well_name: str):
        if self._callback:
            self._callback(well_name)


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
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
  const wells = {wells_json};
  const center_lat = {center_lat};
  const center_lng = {center_lng};

  new QWebChannel(qt.webChannelTransport, function(channel) {{
    window.bridge = channel.objects.bridge;
  }});

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
        'circle-radius': 6,
        'circle-color': ['get', 'color'],
        'circle-stroke-width': 1,
        'circle-stroke-color': '#fff'
      }}
    }});

    map.on('click', 'well-stars', (e) => {{
      const name = e.features[0].properties.name;
      if (window.bridge) window.bridge.onWellClicked(name);
    }});

    map.on('mouseenter', 'well-stars', () => {{
      map.getCanvas().style.cursor = 'pointer';
    }});
    map.on('mouseleave', 'well-stars', () => {{
      map.getCanvas().style.cursor = '';
    }});
  }});
</script>
</body>
</html>"""


def build_geojson(wells: list) -> str:
    features = []
    for w in wells:
        features.append({
            "type": "Feature",
            "properties": {"name": w.name, "color": "#ef4444"},
            "geometry": {"type": "Point", "coordinates": [w.longitude, w.latitude]},
        })
    return json.dumps({"type": "FeatureCollection", "features": features})


class MapRenderer(QWebEngineView):
    def __init__(self, wells: list, well_click_callback=None):
        super().__init__()
        self._bridge = MapBridge()
        if well_click_callback:
            self._bridge.set_well_click_callback(well_click_callback)

        channel = QWebChannel()
        channel.registerObject("bridge", self._bridge)
        self.page().setWebChannel(channel)

        geojson = build_geojson(wells)
        center_lat = sum(w.latitude for w in wells) / len(wells) if wells else 38
        center_lng = sum(w.longitude for w in wells) / len(wells) if wells else 117
        html = MAPLIBRE_HTML.format(wells_json=geojson, center_lat=center_lat, center_lng=center_lng)
        self.setHtml(html)
