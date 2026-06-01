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


def test_sidebar_has_seven_buttons(window):
    buttons = window.sidebar.findChildren(object)
    nav_buttons = [b for b in buttons if hasattr(b, "property") and b.property("nav_key") is not None]
    assert len(nav_buttons) == 7


def test_stacked_widget_has_seven_pages(window):
    stack = window.findChild(QStackedWidget)
    assert stack is not None
    assert stack.count() == 7


def test_sidebar_click_switches_page(window, qtbot):
    window.sidebar_buttons[1].click()
    stack = window.findChild(QStackedWidget)
    assert stack.currentIndex() == 1


def test_main_window_project_synchronization(window):
    """Verify that MainWindow sync_to_project and sync_from_project round-trips state correctly."""
    from src.data.project import ProjectSchema, ProjectMeta, ProjectViewState

    # 1. Test sync_from_project updates active page and tracks project data
    meta = ProjectMeta(name="TDD Expedition", created_at="2026-06-01T12:00:00", updated_at="2026-06-01T12:00:00")
    view_state = ProjectViewState(active_page=4)
    project_data = ProjectSchema(meta=meta, view_state=view_state)

    window.sync_from_project(project_data)
    assert window.stack.currentIndex() == 4
    assert window.current_project is not None
    assert window.current_project.meta.name == "TDD Expedition"

    # 2. Test sync_to_project gathers current UI states correctly
    window._switch_page(2)
    collected = window.sync_to_project()
    assert collected.view_state.active_page == 2

