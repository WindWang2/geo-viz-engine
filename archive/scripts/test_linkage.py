import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'packages/geoviz_seismic')))
from PySide6.QtWidgets import QApplication
from geoviz_seismic.seismic_view import SeismicView
import numpy as np

app = QApplication([])
view = SeismicView()
data = np.random.randn(20, 20, 20).astype(np.float32)
view.load_demo(data)

def simulate_drag():
    print("Simulating inline drag to 5...")
    view._renderer_3d._il_slider.setValue(5)
    
def check_update():
    print(f"Profile widget current info: {view._profile_widget._vd._slice_info.position if view._profile_widget._vd._slice_info else None}")
    app.quit()

from PySide6.QtCore import QTimer
QTimer.singleShot(100, simulate_drag)
QTimer.singleShot(1000, check_update) # wait for 200ms timer
app.exec()
