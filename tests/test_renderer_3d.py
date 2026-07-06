import numpy as np
import pytest
import warnings
from PySide6.QtCore import Signal

def test_renderer_3d_init(qtbot):
    from geoviz_seismic.renderer_3d import Renderer3D
    
    widget = Renderer3D()
    qtbot.addWidget(widget)
    # Ensure core 3D view initialized
    assert widget._view is not None
    assert widget._plotter is True

def test_renderer_3d_load_volume(qtbot):
    from geoviz_seismic.renderer_3d import Renderer3D
    
    widget = Renderer3D()
    qtbot.addWidget(widget)
    data = np.random.randn(10, 10, 10).astype(np.float32)
    widget.load_volume(data)
    assert widget._loaded
    # Ensure basic visual items added to view
    assert len(widget._view.items) > 0

def test_renderer_3d_load_volume_does_not_warn_on_slider_connections(qtbot):
    from geoviz_seismic.renderer_3d import Renderer3D

    widget = Renderer3D()
    qtbot.addWidget(widget)
    data = np.random.randn(10, 10, 10).astype(np.float32)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        widget.load_volume(data)
        widget.load_volume(data)

    disconnect_warnings = [
        warning
        for warning in caught
        if "Failed to disconnect" in str(warning.message)
    ]
    assert disconnect_warnings == []

def test_renderer_3d_signals():
    """Verify Renderer3D class exposes the expected signal."""
    from geoviz_seismic.renderer_3d import Renderer3D

    assert hasattr(Renderer3D, "slice_changed")
    assert isinstance(Renderer3D.slice_changed, Signal)

def test_renderer_3d_add_horizon(qtbot):
    from geoviz_seismic.renderer_3d import Renderer3D

    widget = Renderer3D()
    qtbot.addWidget(widget)
    h_data = np.zeros((5, 5), dtype=np.float32)
    widget.add_horizon(h_data, name="test_horizon")
    assert "test_horizon" in widget._horizons
    assert widget._horizons["test_horizon"] is not None

def test_renderer_3d_dual_volume(qtbot):
    """Verify that Renderer3D supports loading and managing a dual-volume overlay (amplitude + attribute)."""
    from geoviz_seismic.renderer_3d import Renderer3D
    
    widget = Renderer3D()
    qtbot.addWidget(widget)
    
    # 1. Load primary volume
    primary_data = np.random.randn(10, 10, 10).astype(np.float32)
    widget.load_volume(primary_data)
    assert widget._loaded
    widget.set_render_mode("volume")
    
    # 2. Load overlay/attribute volume
    overlay_data = np.random.randn(10, 10, 10).astype(np.float32)
    widget.load_overlay_volume(overlay_data, colormap="jet", opacity=0.6)
    
    # Ensure overlay visual item created and added
    assert widget._overlay_volume_visual is not None
    assert widget._overlay_volume_visual in widget._view.items
    
    # 3. Test changing overlay properties
    widget.set_overlay_colormap("seismic")
    assert widget._overlay_cmap_name == "seismic"
    
    widget.set_overlay_opacity(0.8)
    assert widget._overlay_opacity == 0.8
    
    # 4. Test visibility toggle
    widget.set_overlay_visible(False)
    assert widget._overlay_volume_visual.visible() is False
    
    widget.set_overlay_visible(True)
    assert widget._overlay_volume_visual.visible() is True
    
    # 5. Clear overlay
    widget.clear_overlay_volume()
    assert widget._overlay_volume_visual is None

def test_dual_gl_volume_item_unit(qtbot):
    """Verify that the custom DualGLVolumeItem compiled program and uniforms behave correctly."""
    from geoviz_seismic.renderer_3d import DualGLVolumeItem, Renderer3D
    
    # Initialize Renderer3D (to establish standard Qt OpenGL context)
    widget = Renderer3D()
    qtbot.addWidget(widget)
    
    mock_data = np.zeros((4, 4, 4, 4), dtype=np.uint8)
    item = DualGLVolumeItem(mock_data)
    
    # Check initial values
    assert item._primary_visible is True
    assert item._overlay_visible is True
    assert item._overlay_opacity == 0.5
    
    # Check setters
    item.setOverlayOpacity(0.7)
    assert item._overlay_opacity == 0.7
    
    item.setOverlayVisible(False)
    assert item._overlay_visible is False
    
    item.setPrimaryVisible(False)
    assert item._primary_visible is False
    
    # Check colormap setup
    primary_lut = np.ones((256, 4), dtype=np.uint8) * 10
    overlay_lut = np.ones((256, 4), dtype=np.uint8) * 20
    item.setColormaps(primary_lut, overlay_lut)
    
    assert item._primary_cmap_lut is primary_lut
    assert item._overlay_cmap_lut is overlay_lut
    assert item._cmap_needs_upload is True
