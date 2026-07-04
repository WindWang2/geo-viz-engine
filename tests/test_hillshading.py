import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

def test_dual_gl_volume_item_hillshading_props(qtbot):
    from geoviz_seismic.renderer_3d import DualGLVolumeItem, Renderer3D

    widget = Renderer3D()
    qtbot.addWidget(widget)

    mock_data = np.zeros((4, 4, 4, 4), dtype=np.uint8)
    item = DualGLVolumeItem(mock_data)

    assert getattr(item, "_shading_enabled", False) is False

    item.setShading(True, (1.0, 1.0, 1.0))

    assert item._shading_enabled is True
    assert item._shading_light_dir == (1.0, 1.0, 1.0)
    assert getattr(item, "_shading_needs_upload", False) is True

def test_renderer3d_set_hillshading(qtbot):
    from geoviz_seismic.renderer_3d import Renderer3D, DualGLVolumeItem
    
    widget = Renderer3D()
    qtbot.addWidget(widget)
    
    data = np.zeros((10, 10, 20), dtype=np.float32)
    widget.load_volume(data)
    widget.set_render_mode("volume")
    
    widget.set_hillshading(True)
    assert widget._volume_visual._shading_enabled is True
    
    widget.set_hillshading(False)
    assert widget._volume_visual._shading_enabled is False
