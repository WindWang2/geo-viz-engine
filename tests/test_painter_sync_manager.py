import pytest
from PySide6.QtWidgets import QApplication
from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_well_log.painter_sync_manager import QPainterSyncManager


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_sync_manager_creation(app):
    mgr = QPainterSyncManager()
    assert mgr._canvases == []
    assert mgr._is_syncing is False


def test_sync_manager_add_canvas(app):
    mgr = QPainterSyncManager()
    c1 = WellLogCanvas()
    c2 = WellLogCanvas()
    mgr.add_canvas(c1)
    mgr.add_canvas(c2)
    assert len(mgr._canvases) == 2


def test_sync_manager_range_sync(app):
    mgr = QPainterSyncManager()
    c1 = WellLogCanvas()
    c2 = WellLogCanvas()
    mgr.add_canvas(c1)
    mgr.add_canvas(c2)
    # Set initial range on both
    c1.set_depth_range(0, 100)
    c2.set_depth_range(0, 100)
    # Change range on c1 — should propagate to c2
    c1.set_depth_range(10, 90)
    assert c2.depth_span == 80.0


def test_sync_manager_no_recursion(app):
    mgr = QPainterSyncManager()
    c1 = WellLogCanvas()
    c2 = WellLogCanvas()
    mgr.add_canvas(c1)
    mgr.add_canvas(c2)
    c1.set_depth_range(0, 100)
    c2.set_depth_range(0, 100)
    # This should not infinite-loop
    c1.set_depth_range(20, 80)
    assert c2.depth_span == 60.0


def test_sync_manager_remove_canvas(app):
    mgr = QPainterSyncManager()
    c1 = WellLogCanvas()
    c2 = WellLogCanvas()
    mgr.add_canvas(c1)
    mgr.add_canvas(c2)
    mgr.remove_canvas(c1)
    assert len(mgr._canvases) == 1
