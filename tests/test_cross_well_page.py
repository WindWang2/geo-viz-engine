# tests/test_cross_well_page.py
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from src.pages.cross_well.page import _WellSelectDialog


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_dialog_returns_selected_wells(app):
    dialog = _WellSelectDialog(["well1", "well2", "well3"])
    # Check two wells
    for i in range(dialog._list.count()):
        item = dialog._list.item(i)
        if item.text() in ("well1", "well3"):
            item.setCheckState(Qt.CheckState.Checked)
    result = dialog.get_selected()
    assert result == ["well1", "well3"]


def test_dialog_empty_selection(app):
    dialog = _WellSelectDialog(["well1"])
    result = dialog.get_selected()
    assert result == []


def test_dialog_sorted_wells(app):
    dialog = _WellSelectDialog(["well3", "well1", "well2"])
    items = [dialog._list.item(i).text() for i in range(dialog._list.count())]
    assert items == ["well1", "well2", "well3"]
