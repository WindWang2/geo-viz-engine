import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'packages/geoviz_seismic')))
from PySide6.QtWidgets import QApplication
from geoviz_seismic.seismic_view import SeismicView

app = QApplication([])
view = SeismicView()
view.show()
from PySide6.QtCore import QTimer
def grab():
    print("Items:", len(view._renderer_3d._view.items))
    print("Has Volume:", view._renderer_3d._use_volume)
    app.quit()
QTimer.singleShot(1000, grab)
app.exec()
