import pytest
from PySide6.QtWidgets import QApplication, QStackedWidget
from src.app import MainWindow


@pytest.fixture
def window(qtbot):
    w = MainWindow()
    qtbot.addWidget(w)
    return w


def test_main_window_title(window):
    assert window.windowTitle() == "GeoViz Engine"


def test_sidebar_has_four_buttons(window):
    buttons = window.sidebar.findChildren(object)
    nav_buttons = [b for b in buttons if hasattr(b, "property") and b.property("nav_key") is not None]
    assert len(nav_buttons) == 4


def test_stacked_widget_has_four_pages(window):
    stack = window.findChild(QStackedWidget)
    assert stack is not None
    assert stack.count() == 4


def test_sidebar_click_switches_page(window, qtbot):
    window.sidebar_buttons[1].click()
    stack = window.findChild(QStackedWidget)
    assert stack.currentIndex() == 1
