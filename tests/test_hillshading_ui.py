import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

def test_seismic_view_hillshade_ui(qtbot):
    from geoviz_seismic.seismic_view import SeismicView
    
    view = SeismicView()
    qtbot.addWidget(view)
    
    # Check default
    assert view._hillshade_btn.isChecked() is False
    
    data = np.zeros((10, 10, 20), dtype=np.float32)
    view.load_demo(data)
    
    # Toggle on
    view._hillshade_btn.setChecked(True)
    assert view._renderer_3d._shading_enabled is True
    
    # Toggle off
    view._hillshade_btn.setChecked(False)
    assert view._renderer_3d._shading_enabled is False
