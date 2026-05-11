import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtCore import QTimer
from src.renderers.paleo_map_renderer import PaleoMapRenderer

class CustomPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, msg, line, sourceID):
        print(f"JS: {msg}")

app = QApplication(sys.argv)
renderer = PaleoMapRenderer()
page = CustomPage()
renderer.setPage(page)
renderer.settings().setAttribute(renderer.settings().WebAttribute.LocalContentCanAccessRemoteUrls, True)
renderer.settings().setAttribute(renderer.settings().WebAttribute.LocalContentCanAccessFileUrls, True)

# Set the JS to stringify geoJson
import src.renderers.paleo_map_renderer as r
r.ECHARTS_HTML_TEMPLATE = r.ECHARTS_HTML_TEMPLATE.replace('console.log("Parsed GeoJSON:", geoJson);', 'console.log("Parsed GeoJSON Stringified:", JSON.stringify(geoJson));')

renderer.load_geojson(os.path.abspath("sample_paleo.geojson"))
renderer.show()

QTimer.singleShot(2000, app.quit)
sys.exit(app.exec())
