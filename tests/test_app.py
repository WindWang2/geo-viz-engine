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


def test_sidebar_has_eight_buttons(window):
    assert len(window.sidebar_buttons) == 8
    buttons = window.sidebar.findChildren(object)
    nav_buttons = [b for b in buttons if hasattr(b, "property") and b.property("nav_key") is not None]
    assert len(nav_buttons) == 9


def test_stacked_widget_has_nine_pages(window):
    stack = window.findChild(QStackedWidget)
    assert stack is not None
    assert stack.count() == 9


def test_plots_page_exists(window):
    from src.pages.plots.page import PlotsPage
    assert hasattr(window, "plots_page")
    assert isinstance(window.plots_page, PlotsPage)
    assert window.plots_page.surface_plot is not None


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


def test_data_page_project_controls(window):
    """Verify that DataPage exposes project lifecycle buttons and syncs metadata display."""
    from PySide6.QtWidgets import QPushButton, QLabel
    
    dp = window.data_page
    # 1. Assert UI controls exist
    assert hasattr(dp, "_new_proj_btn")
    assert hasattr(dp, "_open_proj_btn")
    assert hasattr(dp, "_save_proj_btn")
    assert hasattr(dp, "_save_as_proj_btn")
    assert hasattr(dp, "_project_meta_label")

    assert isinstance(dp._new_proj_btn, QPushButton)
    assert isinstance(dp._project_meta_label, QLabel)
    assert dp._project_meta_label.text() == "工程: 未加载"

    # 2. Test "New Project" creation
    dp._new_proj_btn.click()
    assert window.current_project is not None
    assert window.current_project.meta.name == "新工程"
    assert "工程: 新工程" in dp._project_meta_label.text()


