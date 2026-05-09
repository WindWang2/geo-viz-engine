import base64
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
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
  body {{ margin: 0; padding: 0; background: #1a202c; overflow: hidden; }}
  #map {{ position: absolute; top: 0; bottom: 0; width: 100%; height: 100%; }}
  #loading {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: white; font-family: sans-serif; font-size: 16px; display: none; }}
</style>
</head>
<body>
<div id="map"></div>
<div id="loading">加载中... (Loading)</div>
<script>
  const svgPatterns = {svg_patterns_json};
  const geojsonUrl = "{geojson_url}";

  const chart = echarts.init(document.getElementById('map'));
  
  // Create HTMLImageElements for patterns
  const patternImages = {{}};
  for (const [key, base64] of Object.entries(svgPatterns)) {{
      const img = new Image();
      img.src = base64;
      patternImages[key] = img;
  }}

  if (geojsonUrl) {{
      document.getElementById('loading').style.display = 'block';
      fetch(geojsonUrl)
          .then(res => res.json())
          .then(geoJson => {{
              document.getElementById('loading').style.display = 'none';
              echarts.registerMap('paleo', geoJson);

              // Extract facies to assign pattern
              const regions = geoJson.features.map(feature => {{
                  const faciesName = feature.properties.facies || feature.properties.name || '';
                  
                  // Match logic: same as python get_pattern
                  let matchedPattern = '';
                  const keys = Object.keys(patternImages).sort((a,b) => b.length - a.length);
                  for (let k of keys) {{
                      if (faciesName.includes(k)) {{
                          matchedPattern = k;
                          break;
                      }}
                  }}

                  if (matchedPattern) {{
                      return {{
                          name: feature.properties.name || faciesName,
                          itemStyle: {{
                              areaColor: {{
                                  image: patternImages[matchedPattern],
                                  repeat: 'repeat'
                              }}
                          }}
                      }};
                  }} else {{
                      return {{ name: feature.properties.name || faciesName }};
                  }}
              }});

              const option = {{
                  tooltip: {{
                      trigger: 'item',
                      formatter: '{{b}}'
                  }},
                  toolbox: {{
                      show: false
                  }},
                  series: [
                      {{
                          type: 'map',
                          map: 'paleo',
                          roam: true,
                          itemStyle: {{
                              borderColor: '#cbd5e0',
                              borderWidth: 1,
                              areaColor: '#2d3748' // Default color
                          }},
                          emphasis: {{
                              itemStyle: {{
                                  areaColor: '#4a5568'
                              }}
                          }},
                          data: regions
                      }}
                  ]
              }};

              chart.setOption(option);
          }})
          .catch(err => {{
              document.getElementById('loading').innerHTML = '加载失败 (Error Loading JSON)';
              console.error(err);
          }});
  }}
  
  window.addEventListener('resize', () => chart.resize());
</script>
</body>
</html>"""


class PaleoMapRenderer(QWebEngineView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)

        self._tmp_html = None
        
        # Load initially empty
        self.load_geojson(None)

    def _get_svg_base64_dict(self):
        """Loads all SVGs referenced in PATTERN_MAP and converts to base64 dict."""
        svg_dict = {}
        patterns_dir = Path(__file__).parent.parent / "patterns"
        
        # Map original facies keywords to the pattern
        for facies_keyword, pattern_name in PATTERN_MAP.items():
            svg_path = patterns_dir / f"{pattern_name}.svg"
            if svg_path.exists():
                with open(svg_path, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode('utf-8')
                    svg_dict[facies_keyword] = f"data:image/svg+xml;base64,{encoded}"
        return svg_dict

    def load_geojson(self, file_path: str | None):
        svg_patterns_json = json.dumps(self._get_svg_base64_dict())
        
        geojson_url = ""
        if file_path and os.path.exists(file_path):
            geojson_url = QUrl.fromLocalFile(os.path.abspath(file_path)).toString()

        html = ECHARTS_HTML_TEMPLATE.format(
            svg_patterns_json=svg_patterns_json,
            geojson_url=geojson_url
        )

        self._cleanup_tmp()
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8"
        )
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
