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
<style>
__MAPLIBRE_CSS__
  body { margin: 0; padding: 0; }
  #map { position: absolute; top: 0; bottom: 0; width: 100%; height: 100%; }
</style>
<script>
__MAPLIBRE_JS__
</script>
</head>
<body>
<div id="map"></div>
<script>
  const wells = __WELLS_JSON__;
  const world = __WORLD_JSON__;
  const guangdong = __GUANGDONG_JSON__;
  const center_lat = __CENTER_LAT__;
  const center_lng = __CENTER_LNG__;

  function notifyWellClicked(name) {
    // Encode well name as query param to avoid host-encoding issues with CJK
    window.location.href = 'well://click?name=' + encodeURIComponent(name);
  }

  const map = new maplibregl.Map({
    container: 'map',
    style: {
      "version": 8,
      "sources": {},
      "layers": [
        {
          "id": "background",
          "type": "background",
          "paint": {
            "background-color": "#bae6fd" // Sleek, modern ocean blue
          }
        }
      ]
    },
    center: [center_lng, center_lat],
    zoom: 7.5
  });

  map.on('load', () => {
    // 1. Add global world landmass
    map.addSource('world', {
      type: 'geojson',
      data: world
    });
    map.addLayer({
      id: 'world-fill',
      type: 'fill',
      source: 'world',
      paint: {
        'fill-color': '#f8fafc', // Beautiful ivory/light gray landmass
        'fill-opacity': 1.0
      }
    });
    map.addLayer({
      id: 'world-borders',
      type: 'line',
      source: 'world',
      paint: {
        'line-color': '#cbd5e1', // Soft gray boundaries
        'line-width': 0.8
      }
    });

    // 2. Add local detailed landmass (Guangdong) for regional focus
    map.addSource('guangdong', {
      type: 'geojson',
      data: guangdong
    });
    map.addLayer({
      id: 'guangdong-fill',
      type: 'fill',
      source: 'guangdong',
      paint: {
        'fill-color': '#f1f5f9', // Slightly darker warm gray for regional emphasis
        'fill-opacity': 0.6
      }
    });
    map.addLayer({
      id: 'guangdong-borders',
      type: 'line',
      source: 'guangdong',
      paint: {
        'line-color': '#94a3b8', // Gray boundaries
        'line-width': 1.2
      }
    });

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

    // 3. Add key Chinese geographical reference labels for orientation
    const referenceLabels = [
      { name: "北京 (Beijing)", coords: [116.4074, 39.9042], type: "capital" },
      { name: "上海 (Shanghai)", coords: [121.4737, 31.2304], type: "city" },
      { name: "广州 (Guangzhou)", coords: [113.2644, 23.1292], type: "city" },
      { name: "深圳 (Shenzhen)", coords: [114.0579, 22.5431], type: "city" },
      { name: "香港 (Hong Kong)", coords: [114.1694, 22.3193], type: "city" },
      { name: "澳门 (Macau)", coords: [113.5439, 22.1987], type: "city" },
      { name: "惠州 (Huizhou)", coords: [114.4158, 23.1109], type: "city" },
      { name: "珠海 (Zhuhai)", coords: [113.5767, 22.2707], type: "city" },
      { name: "汕头 (Shantou)", coords: [116.7084, 23.3718], type: "city" },
      { name: "湛江 (Zhanjiang)", coords: [110.3649, 21.2749], type: "city" },
      { name: "海口 (Haikou)", coords: [110.3308, 20.0221], type: "city" },
      { name: "福州 (Fuzhou)", coords: [119.3063, 26.0753], type: "city" },
      { name: "台北 (Taipei)", coords: [121.5654, 25.0330], type: "city" },
      { name: "南宁 (Nanning)", coords: [108.3200, 22.8240], type: "city" },
      { name: "南海 (South China Sea)", coords: [115.5, 20.2], type: "sea" }
    ];

    referenceLabels.forEach(label => {
      const el = document.createElement('div');
      el.style.display = 'flex';
      el.style.alignItems = 'center';
      el.style.pointerEvents = 'none';

      if (label.type === "sea") {
        const text = document.createElement('div');
        text.innerText = label.name;
        text.style.fontSize = '13px';
        text.style.fontWeight = 'bold';
        text.style.fontStyle = 'italic';
        text.style.fontFamily = 'system-ui, -apple-system, sans-serif';
        text.style.color = '#0284c7';
        text.style.textShadow = '1.5px 1.5px 0px #ffffff, -1.5px -1.5px 0px #ffffff';
        el.appendChild(text);
      } else {
        const dot = document.createElement('div');
        dot.style.width = '6px';
        dot.style.height = '6px';
        dot.style.borderRadius = '50%';
        dot.style.backgroundColor = label.type === "capital" ? '#ef4444' : '#94a3b8';
        dot.style.marginRight = '5px';
        dot.style.border = '1px solid #ffffff';
        dot.style.boxShadow = '0 1px 2px rgba(0,0,0,0.15)';
        el.appendChild(dot);

        const text = document.createElement('div');
        text.innerText = label.name;
        text.style.fontSize = '11px';
        text.style.fontWeight = label.type === "capital" ? 'bold' : 'normal';
        text.style.fontFamily = 'system-ui, -apple-system, sans-serif';
        text.style.color = '#475569';
        text.style.textShadow = '1.5px 1.5px 0px #ffffff, -1.5px -1.5px 0px #ffffff';
        el.appendChild(text);
      }

      new maplibregl.Marker({ element: el })
        .setLngLat(label.coords)
        .addTo(map);
    });
  });
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

        # Resolve paths
        data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data"))
        guangdong_path = os.path.join(data_dir, "guangdong.json")
        world_path = os.path.join(data_dir, "world.json")
        assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "assets"))
        maplibre_js_path = os.path.join(assets_dir, "maplibre-gl.js")
        maplibre_css_path = os.path.join(assets_dir, "maplibre-gl.css")

        # Load local Guangdong GeoJSON
        try:
            with open(guangdong_path, "r", encoding="utf-8") as f:
                guangdong_geojson = f.read()
        except Exception:
            guangdong_geojson = '{"type": "FeatureCollection", "features": []}'

        # Load local World Countries GeoJSON
        try:
            with open(world_path, "r", encoding="utf-8") as f:
                world_geojson = f.read()
        except Exception:
            world_geojson = '{"type": "FeatureCollection", "features": []}'

        # Load local JS & CSS library contents to inline for bulletproof offline execution
        try:
            with open(maplibre_js_path, "r", encoding="utf-8") as f:
                maplibre_js = f.read()
        except Exception:
            maplibre_js = ""

        try:
            with open(maplibre_css_path, "r", encoding="utf-8") as f:
                maplibre_css = f.read()
        except Exception:
            maplibre_css = ""

        geojson = build_geojson(wells, data_wells)
        center_lat = sum(w.latitude for w in wells) / len(wells) if wells else 38
        center_lng = sum(w.longitude for w in wells) / len(wells) if wells else 117

        # Replace placeholders safely (string.replace is curly-brace immune)
        html = MAPLIBRE_HTML
        html = html.replace("__MAPLIBRE_JS__", maplibre_js)
        html = html.replace("__MAPLIBRE_CSS__", maplibre_css)
        html = html.replace("__WELLS_JSON__", geojson)
        html = html.replace("__WORLD_JSON__", world_geojson)
        html = html.replace("__GUANGDONG_JSON__", guangdong_geojson)
        html = html.replace("__CENTER_LAT__", str(center_lat))
        html = html.replace("__CENTER_LNG__", str(center_lng))

        # Write HTML to a temp file and load via file:// so that custom-scheme
        # navigation (well://) is not blocked by Chromium's data: URL security policy.
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8"
        )
        tmp.write(html)
        tmp.close()
        self._tmp_html = tmp.name
        self.load(QUrl.fromLocalFile(tmp.name))

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
