import numpy as np
import pytest
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

def test_renderer_3d_signals():
    """Verify Renderer3D class exposes the expected signal."""
    from geoviz_seismic.renderer_3d import Renderer3D

    assert hasattr(Renderer3D, "slice_changed")
    assert isinstance(Renderer3D.slice_changed, Signal)

def test_renderer_3d_add_horizon(qtbot):
    from geoviz_seismic.renderer_3d import Renderer3D
    
    widget = Renderer3D()
    qtbot.addWidget(widget)
    # Must have volume context to render properly in scene logic usually but standalone check:
    h_data = np.zeros((5, 5), dtype=np.float32)
    widget.add_horizon(h_data)
    assert widget._horizon_visual is not None
