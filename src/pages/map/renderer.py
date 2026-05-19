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
<script src="{maplibre_js}"></script>
<link href="{maplibre_css}" rel="stylesheet" />
<style>
  body {{ margin: 0; padding: 0; }}
  #map {{ position: absolute; top: 0; bottom: 0; width: 100%; height: 100%; }}
</style>
</head>
<body>
<div id="map"></div>
<script>
  const wells = {wells_json};
  const guangdong = {guangdong_json};
  const center_lat = {center_lat};
  const center_lng = {center_lng};

  function notifyWellClicked(name) {{
    // Encode well name as query param to avoid host-encoding issues with CJK
    window.location.href = 'well://click?name=' + encodeURIComponent(name);
  }}

  const map = new maplibregl.Map({{
    container: 'map',
    style: {{
      "version": 8,
      "sources": {{}},
      "layers": [
        {{
          "id": "background",
          "type": "background",
          "paint": {{
            "background-color": "#bae6fd" // Sleek, modern ocean blue
          }}
        }}
      ]
    }},
    center: [center_lng, center_lat],
    zoom: 7.5
  }});

  map.on('load', () => {{
    // Add local detailed landmass (Guangdong)
    map.addSource('guangdong', {{
      type: 'geojson',
      data: guangdong
    }});
    map.addLayer({{
      id: 'guangdong-fill',
      type: 'fill',
      source: 'guangdong',
      paint: {{
        'fill-color': '#f8fafc', // Beautiful ivory/light gray landmass
        'fill-opacity': 1.0
      }}
    }});
    map.addLayer({{
      id: 'guangdong-borders',
      type: 'line',
      source: 'guangdong',
      paint: {{
        'line-color': '#cbd5e1', // Soft gray boundaries
        'line-width': 1.0
      }}
    }});

    // Add wells as highly customizable, offline-friendly HTML Markers
    wells.features.forEach(feature => {
      const coords = feature.geometry.coordinates;
      const name = feature.properties.name;
      const hasData = feature.properties.has_data;
      const color = feature.properties.color;

      const el = document.createElement('div');
      el.className = 'well-marker';
      el.style.display = 'flex';
      el.style.flexDirection = 'column';
      el.style.alignItems = 'center';
      el.style.cursor = 'pointer';

      // 12px Circle/dot
      const dot = document.createElement('div');
      dot.style.width = '14px';
      dot.style.height = '14px';
      dot.style.borderRadius = '50%';
      dot.style.backgroundColor = color;
      dot.style.border = '2px solid #ffffff';
      dot.style.boxShadow = '0 2px 4px rgba(0,0,0,0.15)';
      dot.style.transition = 'transform 0.2s ease';
      el.appendChild(dot);

      // Label text
      const label = document.createElement('div');
      label.innerText = name;
      label.style.marginTop = '4px';
      label.style.fontSize = '12px';
      label.style.fontWeight = 'bold';
      label.style.fontFamily = 'system-ui, -apple-system, sans-serif';
      label.style.color = hasData ? '#0f172a' : '#64748b';
      label.style.textShadow = '1.5px 1.5px 0px #ffffff, -1.5px -1.5px 0px #ffffff, 1.5px -1.5px 0px #ffffff, -1.5px 1.5px 0px #ffffff'; // Crisp white halo
      label.style.whiteSpace = 'nowrap';
      el.appendChild(label);

      // Micro-animations on hover
      el.addEventListener('mouseenter', () => {
        dot.style.transform = 'scale(1.2)';
      });
      el.addEventListener('mouseleave', () => {
        dot.style.transform = 'scale(1.0)';
      });

      // Click callback
      el.addEventListener('click', () => {
        notifyWellClicked(name);
      });

      new maplibregl.Marker({ element: el })
        .setLngLat(coords)
        .addTo(map);
    });
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

        # Load local Guangdong Province GeoJSON for fully offline rendering
        data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data"))
        guangdong_path = os.path.join(data_dir, "guangdong.json")
        try:
            with open(guangdong_path, "r", encoding="utf-8") as f:
                guangdong_geojson = f.read()
        except Exception:
            guangdong_geojson = '{"type": "FeatureCollection", "features": []}'

        # Load local MapLibre assets for fully offline rendering
        assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "assets"))
        maplibre_js = QUrl.fromLocalFile(os.path.join(assets_dir, "maplibre-gl.js")).toString()
        maplibre_css = QUrl.fromLocalFile(os.path.join(assets_dir, "maplibre-gl.css")).toString()

        geojson = build_geojson(wells, data_wells)
        center_lat = sum(w.latitude for w in wells) / len(wells) if wells else 38
        center_lng = sum(w.longitude for w in wells) / len(wells) if wells else 117
        html = MAPLIBRE_HTML.format(
            wells_json=geojson, guangdong_json=guangdong_geojson,
            maplibre_js=maplibre_js, maplibre_css=maplibre_css,
            center_lat=center_lat, center_lng=center_lng,
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
