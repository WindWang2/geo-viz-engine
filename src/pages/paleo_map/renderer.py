import base64
import html as html_module
import json
import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from src.utils.constants import PATTERN_MAP


ECHARTS_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="{echarts_url}"></script>
<style>
  body {{ margin: 0; padding: 0; background: #f7fafc; overflow: hidden; font-family: sans-serif; }}
  #map {{ position: absolute; top: 40px; bottom: 0; width: 100%; }}
  #loading {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: #334155; font-size: 16px; display: none; }}
  #map-title {{ position: absolute; top: 8px; left: 50%; transform: translateX(-50%); font-size: 16px; font-weight: bold; color: #1a202c; z-index: 10; white-space: nowrap; background: rgba(255,255,255,0.85); padding: 4px 12px; border-radius: 4px; }}
  #legend {{ position: absolute; bottom: 12px; right: 12px; background: rgba(255,255,255,0.95); border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px; font-size: 12px; z-index: 10; max-height: 80vh; overflow-y: auto; }}
  #legend h4 {{ margin: 0 0 6px 0; font-size: 13px; color: #334155; }}
  .legend-item {{ display: flex; align-items: center; gap: 6px; margin-bottom: 3px; }}
  .legend-swatch {{ width: 18px; height: 12px; border: 1px solid #aaa; flex-shrink: 0; }}
  .legend-line {{ width: 18px; height: 0; flex-shrink: 0; }}
  .legend-circle {{ width: 10px; height: 10px; border-radius: 50%; border: 1.5px solid #fff; flex-shrink: 0; }}
  #north-arrow {{ position: absolute; top: 52px; right: 16px; z-index: 10; }}
  #scale-bar {{ position: absolute; bottom: 16px; left: 16px; z-index: 10; }}
</style>
</head>
<body>
<div id="map-title">{map_title}</div>
<div id="map"></div>
<div id="loading">加载中...</div>
<div id="north-arrow">
  <svg width="30" height="40" viewBox="0 0 30 40">
    <polygon points="15,0 10,18 20,18" fill="#334155"/>
    <text x="15" y="30" text-anchor="middle" fill="#334155" font-size="12" font-weight="bold">N</text>
  </svg>
</div>
<div id="scale-bar">
  <svg width="120" height="24" viewBox="0 0 120 24">
    <line x1="0" y1="4" x2="80" y2="4" stroke="#334155" stroke-width="2"/>
    <line x1="0" y1="0" x2="0" y2="8" stroke="#334155" stroke-width="2"/>
    <line x1="80" y1="0" x2="80" y2="8" stroke="#334155" stroke-width="2"/>
    <text x="40" y="20" text-anchor="middle" fill="#334155" font-size="10" id="scale-text"></text>
  </svg>
</div>
<div id="legend"></div>
<script>
  const svgPatterns = {svg_patterns_json};
  const faciesColors = {facies_colors_json};
  const geojsonUrl = "{geojson_url}";
  const showLabels = {show_labels};

  function escapeHtml(str) {{
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
  }}

  function luminance(hex) {{
    const r = parseInt(hex.slice(1,3), 16) / 255;
    const g = parseInt(hex.slice(3,5), 16) / 255;
    const b = parseInt(hex.slice(5,7), 16) / 255;
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }}

  function contrastColor(hex) {{
    return luminance(hex) > 0.5 ? '#2d3748' : '#f7fafc';
  }}

  function matchFacies(faciesName) {{
    const keys = Object.keys(svgPatterns).sort((a,b) => b.length - a.length);
    for (let k of keys) {{
      if (faciesName.includes(k)) return k;
    }}
    return null;
  }}

  function matchColor(faciesName) {{
    const keys = Object.keys(faciesColors).sort((a,b) => b.length - a.length);
    for (let k of keys) {{
      if (faciesName.includes(k)) return faciesColors[k];
    }}
    return '#d9d4c8';
  }}

  function boundaryStyle(boundaryType) {{
    switch(boundaryType) {{
      case 'confirmed': return {{ borderColor: '#555555', borderWidth: 1.5, borderType: 'solid' }};
      case 'inferred': return {{ borderColor: '#555555', borderWidth: 1.5, borderType: [6, 3] }};
      case 'fault': return {{ borderColor: '#e53e3e', borderWidth: 2.0, borderType: 'solid' }};
      default: return {{ borderColor: '#555555', borderWidth: 1.0, borderType: 'solid' }};
    }}
  }}

  function makeCompositePattern(baseColor, patternImg) {{
    const canvas = document.createElement('canvas');
    canvas.width = 20; canvas.height = 20;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = baseColor;
    ctx.fillRect(0, 0, 20, 20);
    ctx.globalAlpha = 0.6;
    ctx.drawImage(patternImg, 0, 0, 20, 20);
    ctx.globalAlpha = 1.0;
    return {{ image: canvas, repeat: 'repeat' }};
  }}

  function updateScaleBar(geoJson) {{
    let minLon = Infinity, maxLon = -Infinity, minLat = Infinity, maxLat = -Infinity;
    const features = geoJson.features || (geoJson.type === 'Feature' ? [geoJson] : []);
    features.forEach(f => {{
      if (!f.geometry || !f.geometry.coordinates) return;
      const coords = f.geometry.type === 'Polygon' ? f.geometry.coordinates[0] :
                     f.geometry.type === 'MultiPolygon' ? f.geometry.coordinates.flat(2) : [];
      coords.forEach(c => {{
        if (Array.isArray(c) && c.length >= 2) {{
          minLon = Math.min(minLon, c[0]); maxLon = Math.max(maxLon, c[0]);
          minLat = Math.min(minLat, c[1]); maxLat = Math.max(maxLat, c[1]);
        }}
      }});
    }});
    if (minLon === Infinity) return;
    const midLat = (minLat + maxLat) / 2;
    const degToKm = 111.32 * Math.cos(midLat * Math.PI / 180);
    const extentKm = (maxLon - minLon) * degToKm;
    const niceSteps = [1,2,5,10,20,50,100,200,500,1000,2000,5000];
    let scaleKm = niceSteps[0];
    for (const s of niceSteps) {{
      if (s < extentKm * 0.3) scaleKm = s;
    }}
    document.getElementById('scale-text').textContent = scaleKm >= 1 ? scaleKm + ' km' : (scaleKm * 1000) + ' m';
  }}

  function preloadPatterns() {{
    const promises = Object.entries(svgPatterns).map(([key, base64]) => {{
      return new Promise(resolve => {{
        const img = new Image();
        img.onload = () => resolve([key, img]);
        img.onerror = () => resolve([key, null]);
        img.src = base64;
      }});
    }});
    return Promise.all(promises).then(entries => {{
      const images = {{}};
      entries.forEach(([k, v]) => {{ if (v) images[k] = v; }});
      return images;
    }});
  }}

  window.onload = function() {{
    if (typeof echarts === 'undefined') {{
      document.getElementById('loading').style.display = 'block';
      document.getElementById('loading').innerHTML = 'Error: ECharts failed to load';
      return;
    }}

    const chart = echarts.init(document.getElementById('map'), null, {{ renderer: 'canvas' }});
    window.chart = chart;

    if (geojsonUrl) {{
      document.getElementById('loading').style.display = 'block';
      preloadPatterns().then(patternImages => {{
        window.patternImages = patternImages;
        return fetch(geojsonUrl).then(res => {{
          if (!res.ok) throw new Error('Fetch failed: ' + res.status);
          return res.json();
        }}).then(geoJson => {{
          document.getElementById('loading').style.display = 'none';
          if (!geoJson || (!geoJson.features && geoJson.type !== 'Feature')) {{
            throw new Error('Invalid GeoJSON');
          }}

          updateScaleBar(geoJson);
          echarts.registerMap('paleo', geoJson);
          const features = geoJson.features || (geoJson.type === 'Feature' ? [geoJson] : []);

          const seenFacies = new Set();
          const regions = features.map(feature => {{
            const props = feature.properties || {{}};
            const faciesName = props.facies || props.name || '';
            const boundaryType = props.boundary_type || null;

            const matchedPattern = matchFacies(faciesName);
            const baseColor = matchColor(faciesName);
            seenFacies.add(faciesName);

            const region = {{
              name: props.name || faciesName,
              itemStyle: {{
                areaColor: baseColor,
                ...boundaryStyle(boundaryType)
              }}
            }};

            if (matchedPattern && patternImages[matchedPattern]) {{
              region.itemStyle.areaColor = makeCompositePattern(baseColor, patternImages[matchedPattern]);
            }}

            if (showLabels) {{
              region.label = {{
                show: true,
                formatter: '{{b}}',
                fontSize: 12,
                fontWeight: 'bold',
                color: contrastColor(baseColor)
              }};
            }}

            return region;
          }});

          const wells = {wells_json};

          const option = {{
            tooltip: {{ trigger: 'item', formatter: '{{b}}' }},
            geo: {{
              map: 'paleo',
              roam: true,
              itemStyle: {{
                areaColor: '#e2e8f0',
                borderColor: '#cbd5e1',
                borderWidth: 0.5
              }},
              emphasis: {{ itemStyle: {{ areaColor: '#edf2f7' }} }},
              regions: regions
            }},
            series: [
              {{
                type: 'map',
                map: 'paleo',
                geoIndex: 0,
                data: regions
              }}
            ]
          }};

          if (wells.length > 0) {{
            option.series.push({{
              type: 'scatter',
              coordinateSystem: 'geo',
              data: wells.map(w => ({{
                name: w.name,
                value: [w.longitude, w.latitude],
                itemStyle: {{ color: '#e53e3e', borderColor: '#fff', borderWidth: 2 }}
              }})),
              symbolSize: 8,
              label: {{ show: true, formatter: '{{b}}', position: 'right', fontSize: 10, color: '#e53e3e' }}
            }});
          }}

          chart.setOption(option);
          buildLegend(seenFacies, patternImages);
        }});
      }})
      .catch(err => {{
        document.getElementById('loading').style.display = 'block';
        document.getElementById('loading').innerHTML = 'Error: ' + err.message;
      }});
    }}

    function buildLegend(seenFacies, patternImages) {{
      const legendDiv = document.getElementById('legend');
      let html = '<h4>图例</h4>';
      seenFacies.forEach(faciesName => {{
        const color = matchColor(faciesName);
        const matched = matchFacies(faciesName);
        let swatchStyle = `background: ${{color}};`;
        if (matched && patternImages[matched]) {{
          const canvas = document.createElement('canvas');
          canvas.width = 18; canvas.height = 12;
          const ctx = canvas.getContext('2d');
          ctx.fillStyle = color;
          ctx.fillRect(0, 0, 18, 12);
          ctx.globalAlpha = 0.6;
          ctx.drawImage(patternImages[matched], 0, 0, 18, 12);
          swatchStyle = `background: url(${{canvas.toDataURL()}}); background-size: 18px 12px;`;
        }}
        html += `<div class="legend-item"><div class="legend-swatch" style="${{swatchStyle}}"></div><span>${{escapeHtml(faciesName)}}</span></div>`;
      }});
      html += '<div style="border-top:1px solid #e2e8f0;margin:6px 0;padding-top:6px;">';
      html += '<div class="legend-item"><div class="legend-line" style="border-top:2px solid #555;"></div><span>实测界线</span></div>';
      html += '<div class="legend-item"><div class="legend-line" style="border-top:2px dashed #555;"></div><span>推测界线</span></div>';
      html += '<div class="legend-item"><div class="legend-line" style="border-top:2px solid #e53e3e;"></div><span>断层</span></div>';
      html += '<div class="legend-item"><div class="legend-circle" style="background:#e53e3e;"></div><span>井位</span></div>';
      html += '</div>';
      legendDiv.innerHTML = html;
    }}
  }};

  window.addEventListener('resize', () => {{
    if (window.chart) window.chart.resize();
  }});
</script>
</body>
</html>"""


class PaleoMapRenderer(QWebEngineView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        self._tmp_html = None
        self._show_labels = True
        self._map_title = ""
        self.load_geojson(None)

    def _get_svg_base64_dict(self):
        svg_dict = {}
        patterns_dir = Path(__file__).parent.parent / "patterns"
        for facies_keyword, pattern_name in PATTERN_MAP.items():
            svg_filename = pattern_name.replace("-", "_") + ".svg"
            svg_path = patterns_dir / svg_filename
            if svg_path.exists():
                with open(svg_path, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode("utf-8")
                    svg_dict[facies_keyword] = f"data:image/svg+xml;base64,{encoded}"
        return svg_dict

    def _get_wells_json(self):
        try:
            wells_path = Path(__file__).parent.parent.parent / "data" / "well_coordinates.json"
            if not wells_path.exists():
                return "[]"
            with open(wells_path, encoding="utf-8") as f:
                data = json.load(f)
            wells = data.get("wells", [])
            return json.dumps([{"name": w["well_name"], "longitude": w["longitude"], "latitude": w["latitude"]} for w in wells])
        except (json.JSONDecodeError, KeyError, OSError):
            return "[]"

    def load_geojson(self, file_path: str | None, period_name: str = "",
                     show_labels: bool = True, map_title: str = ""):
        self._show_labels = show_labels
        self._map_title = html_module.escape(
            map_title or (period_name + "岩相古地理图" if period_name else "")
        )

        svg_patterns_json = json.dumps(self._get_svg_base64_dict()).replace("</script>", r"<\/script>")
        from src.utils.constants import FACIES_COLORS
        facies_colors_json = json.dumps(FACIES_COLORS).replace("</script>", r"<\/script>")

        echarts_js = Path(__file__).parent.parent / "resources" / "js" / "echarts.min.js"
        echarts_url = QUrl.fromLocalFile(str(echarts_js)).toString()

        geojson_url = ""
        if file_path and os.path.exists(file_path):
            geojson_url = QUrl.fromLocalFile(os.path.abspath(file_path)).toString()

        html = ECHARTS_HTML_TEMPLATE.format(
            svg_patterns_json=svg_patterns_json,
            facies_colors_json=facies_colors_json,
            echarts_url=echarts_url,
            geojson_url=geojson_url,
            show_labels="true" if show_labels else "false",
            map_title=self._map_title,
            wells_json=self._get_wells_json().replace("</script>", r"<\/script>"),
        )

        self._cleanup_tmp()
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8")
        tmp.write(html)
        tmp.close()
        self._tmp_html = tmp.name
        self.load(QUrl.fromLocalFile(tmp.name))

    def _cleanup_tmp(self):
        if self._tmp_html and os.path.exists(self._tmp_html):
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
