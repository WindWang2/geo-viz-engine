# tests/test_modules.py
from src.renderers.well_log.modules import CompositeModule, LayoutCoordinator
from unittest.mock import MagicMock

def test_composite_sync_depth_broadcasts_to_children():
    child1 = MagicMock()
    child2 = MagicMock()
    comp = CompositeModule(label="TEST", children=[child1, child2])
    comp.sync_depth(10.0, 50.0)
    child1.sync_depth.assert_called_once_with(10.0, 50.0)
    child2.sync_depth.assert_called_once_with(10.0, 50.0)

def test_composite_preferred_width_sum_or_override():
    c1 = MagicMock()
    c1.preferred_width.return_value = 80
    c2 = MagicMock()
    c2.preferred_width.return_value = 120
    comp = CompositeModule(label="GROUP", children=[c1, c2])
    assert comp.preferred_width() == 200  # sum of children

    comp_override = CompositeModule(label="OVERRIDE", children=[c1, c2], width_override=150)
    assert comp_override.preferred_width() == 150  # override wins

def test_composite_set_pixel_density_broadcasts():
    child1 = MagicMock()
    child2 = MagicMock()
    comp = CompositeModule(label="DENSITY", children=[child1, child2])
    comp.set_pixel_density(3.5)
    child1.set_pixel_density.assert_called_once_with(3.5)
    child2.set_pixel_density.assert_called_once_with(3.5)

def test_layout_coordinator_fit_calculates_correct_density():
    mock_vb = MagicMock()
    mock_vb.viewRange.return_value = ((0.0, 1.0), (-500.0, 0.0))  # y range top=-500, bottom=0
    child = MagicMock()
    coord = LayoutCoordinator(mock_vb, [child], viewport_height=1000)
    coord.fit_to_viewport()
    # span = 0 - (-500) = 500m; px_per_m = 1000/500 = 2.0
    child.set_pixel_density.assert_called_once_with(2.0)
    child.sync_depth.assert_called_once_with(-500.0, 0.0)

def test_layout_coordinator_on_resize_refits():
    mock_vb = MagicMock()
    mock_vb.viewRange.return_value = ((0.0, 1.0), (0.0, 100.0))
    child = MagicMock()
    coord = LayoutCoordinator(mock_vb, [child], viewport_height=200)
    coord.on_resize(600)  # simulate resize to taller window
    # 600 / 100m = 6 px/m
    child.set_pixel_density.assert_called_with(6.0)

def test_layout_coordinator_on_master_range_changed_broadcasts():
    mock_vb = MagicMock()
    mock_vb.viewRange.return_value = ((0.0, 1.0), (0.0, 100.0))
    child = MagicMock()
    coord = LayoutCoordinator(mock_vb, [child])
    coord.on_master_range_changed(mock_vb, (10.0, 80.0))
    child.sync_depth.assert_called_with(10.0, 80.0)