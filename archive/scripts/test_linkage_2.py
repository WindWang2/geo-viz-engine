import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'packages/geoviz_seismic')))
from PySide6.QtWidgets import QApplication
from geoviz_seismic.seismic_view import SeismicView
import numpy as np

app = QApplication([])
view = SeismicView()

def test_sum():
    s1 = view._profile_widget._vd._data.sum()
    print("sum 1:", s1)
    view._renderer_3d._il_slider.setValue(10)
    
def test_sum2():
    s2 = view._profile_widget._vd._data.sum()
    print("sum 2:", s2)
    app.quit()

from PySide6.QtCore import QTimer
QTimer.singleShot(100, test_sum)
QTimer.singleShot(1000, test_sum2)
app.exec()
