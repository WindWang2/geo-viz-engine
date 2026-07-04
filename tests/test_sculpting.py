import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

def test_dual_gl_volume_item_sculpting_props(qtbot):
    from geoviz_seismic.renderer_3d import DualGLVolumeItem, Renderer3D

    # Need context
    widget = Renderer3D()
    qtbot.addWidget(widget)

    mock_data = np.zeros((4, 4, 4, 4), dtype=np.uint8)
    item = DualGLVolumeItem(mock_data)

    # Defaults
    assert getattr(item, "_sculpting_enabled", False) is False

    # Set horizon
    horizon_data = np.full((10, 10), 0.5, dtype=np.float32)
    item.setSculpting(True, horizon_data, mode="above")

    assert item._sculpting_enabled is True
    assert item._sculpting_mode == "above"
    assert np.array_equal(item._sculpt_horizon_data, horizon_data)
    assert item._sculpt_needs_upload is True

def test_renderer3d_set_sculpting_surface(qtbot):
    from geoviz_seismic.renderer_3d import Renderer3D, DualGLVolumeItem
    
    widget = Renderer3D()
    qtbot.addWidget(widget)
    
    # Load dummy data
    data = np.zeros((10, 10, 20), dtype=np.float32)
    widget.load_volume(data)
    widget.set_render_mode("volume")
    
    assert isinstance(widget._volume_visual, DualGLVolumeItem)
    assert widget._volume_visual._sculpting_enabled is False
    
    surface_z = np.full((10, 10), 10.0)
    
    widget.set_sculpting_surface(surface_z, mode="above")
    
    assert widget._volume_visual._sculpting_enabled is True
    assert widget._volume_visual._sculpting_mode == "above"
    norm = widget._volume_visual._sculpt_horizon_data
    assert norm is not None
    assert norm.shape == (10, 10)
    # Z-axis ranges from 0 to 19. If surface_z is 10, norm should be 10 / 19.
    assert np.allclose(norm, 10.0 / 19.0)
    
    # Disable
    widget.set_sculpting_surface(None)
    assert widget._volume_visual._sculpting_enabled is False
