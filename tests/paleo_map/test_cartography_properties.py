"""Property panel + delete-key behaviour (Task 8)."""

from PySide6.QtCore import QPointF, QRectF, Qt

from geoviz_paleo_map.cartography.items.free.box_items import FreeRectItem
from geoviz_paleo_map.cartography.window import CartographyLayoutWindow


def test_property_panel_reflects_selection(qtbot):
    win = CartographyLayoutWindow()
    qtbot.addWidget(win)
    item = FreeRectItem(QRectF(10.0, 10.0, 40.0, 20.0))
    win._scene.addItem(item)
    win._scene.clearSelection()
    item.setSelected(True)
    panel = win._property_panel
    panel.refresh_from_selection()
    assert panel._stroke_edit.text() == "#000000"
    assert panel._width_spin.value() == 0.3


def test_property_panel_edits_write_back(qtbot):
    win = CartographyLayoutWindow()
    qtbot.addWidget(win)
    item = FreeRectItem(QRectF(10.0, 10.0, 40.0, 20.0))
    win._scene.addItem(item)
    item.setSelected(True)
    panel = win._property_panel
    panel.refresh_from_selection()
    panel._stroke_edit.setText("#ff0000")
    panel._apply_stroke()
    assert item.stroke == "#ff0000"
    panel._width_spin.setValue(1.5)
    panel._apply_width()
    assert item.width_mm == 1.5


def test_delete_key_removes_selected(qtbot):
    win = CartographyLayoutWindow()
    qtbot.addWidget(win)
    item = FreeRectItem(QRectF(10.0, 10.0, 40.0, 20.0))
    win._scene.addItem(item)
    item.setSelected(True)
    win.set_tool_mode("select")
    # Simulate Del key.
    from PySide6.QtGui import QKeyEvent
    ev = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier
    )
    win.keyPressEvent(ev)
    assert item.scene() is None  # removed


def test_property_panel_empty_when_no_selection(qtbot):
    win = CartographyLayoutWindow()
    qtbot.addWidget(win)
    panel = win._property_panel
    panel.refresh_from_selection()
    assert not panel.isEnabled()
