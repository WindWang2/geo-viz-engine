import sys
import tempfile
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtCore import QUrl

app = QApplication(sys.argv)

html = """<!DOCTYPE html>
<html>
<body>
<script>
fetch('file://%s').then(r => r.text()).then(t => console.log("FETCH_SUCCESS:", t.substring(0,20))).catch(e => console.error("FETCH_ERROR:", e));
</script>
</body>
</html>
""" % os.path.abspath("sample_paleo.geojson")

tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w")
tmp.write(html)
tmp.close()

view = QWebEngineView()
view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
view.load(QUrl.fromLocalFile(tmp.name))
view.show()

# Run for a brief moment then exit
import threading
def finish():
    import time
    time.sleep(1)
    app.quit()
threading.Thread(target=finish).start()

sys.exit(app.exec())
