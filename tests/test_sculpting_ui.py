import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

def test_seismic_view_sculpting_ui(qtbot):
    from geoviz_seismic.seismic_view import SeismicView
    
    view = SeismicView()
    qtbot.addWidget(view)
    
    # Check default combo
    assert view._sculpt_horizon_combo.count() == 1
    assert view._sculpt_horizon_combo.currentText() == "无"
    
    # Load dummy data
    data = np.zeros((10, 10, 20), dtype=np.float32)
    view.load_demo(data)
    
    # Emulate loading a horizon
    horizon_data = np.full((10, 10), 10.0)
    # Patch _horizon_grids manually to simulate what _load_horizon would do
    view._horizon_grids["TestHorz"] = horizon_data
    view._renderer_3d.add_horizon(horizon_data, name="TestHorz")
    view._sculpt_horizon_combo.addItem("TestHorz")
    
    assert view._sculpt_horizon_combo.count() == 2
    
    # Select horizon
    view._sculpt_horizon_combo.setCurrentText("TestHorz")
    assert view._renderer_3d._sculpt_surface is horizon_data
    assert view._renderer_3d._sculpt_mode == "below" # default in our ui patch is "保留下部" which maps to "below"
    
    # Change mode
    view._sculpt_mode_combo.setCurrentText("保留上部")
    assert view._renderer_3d._sculpt_mode == "above"
    
    # Set back to 无
    view._sculpt_horizon_combo.setCurrentText("无")
    assert view._renderer_3d._sculpt_surface is None
