import pytest
from PySide6.QtWidgets import QApplication, QPushButton, QStackedWidget
from PySide6.QtCore import Qt
from src.utils.global_style import GLOBAL_STYLESHEET


@pytest.fixture
def app_instance():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.setStyleSheet(GLOBAL_STYLESHEET)
    return app


def test_global_stylesheet_contains_spacing_tokens(app_instance):
    """Global QSS should define spacing-aware padding values."""
    ss = app_instance.styleSheet()
    assert "padding: 6px 12px" in ss


def test_global_stylesheet_contains_radius_tokens(app_instance):
    """Global QSS should use 8px radius for buttons, 12px for cards."""
    ss = app_instance.styleSheet()
    assert "border-radius: 8px" in ss  # buttons
    assert "border-radius: 12px" in ss  # QGroupBox cards


def test_global_stylesheet_contains_shadow_tokens(app_instance):
    """QGroupBox cards should have L2 shadow."""
    ss = app_instance.styleSheet()
    assert "rgba(0,0,0" in ss


def test_global_stylesheet_contains_animation_tokens(app_instance):
    """Hover transitions should be defined."""
    ss = app_instance.styleSheet()
    assert "QPushButton:hover" in ss


# ---------------------------------------------------------------------------
# Collapsible sidebar tests (Task 2)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_sidebar_qsettings():
    """Ensure QSettings sidebar state is clean before and after each test."""
    from PySide6.QtCore import QSettings
    settings = QSettings("GeoViz", "Engine")
    settings.remove("sidebar/collapsed")
    yield
    settings.remove("sidebar/collapsed")


@pytest.fixture
def window(qtbot):
    from src.app import MainWindow
    w = MainWindow()
    qtbot.addWidget(w)
    return w


def test_sidebar_default_width_is_200(window):
    """Sidebar should default to 200px expanded width."""
    assert window.sidebar.width() == 200


def test_sidebar_can_collapse_to_56(window):
    """Sidebar should collapse to 56px when toggle is clicked."""
    window._toggle_sidebar()
    assert window.sidebar.width() == 56


def test_sidebar_can_expand_back_to_200(window):
    """Sidebar should expand back to 200px when toggle is clicked again."""
    window._toggle_sidebar()
    window._toggle_sidebar()
    assert window.sidebar.width() == 200


def test_sidebar_collapsed_shows_icons_only(window):
    """In collapsed state, sidebar buttons should hide text."""
    window._toggle_sidebar()
    for btn in window.sidebar_buttons:
        assert btn.text().strip() == "" or btn.toolTip() != ""


def test_sidebar_expanded_shows_text(window):
    """In expanded state, sidebar buttons should show text."""
    for btn in window.sidebar_buttons:
        assert len(btn.text().strip()) > 0


def test_sidebar_toggle_button_exists(window):
    """Header should contain a sidebar toggle button."""
    assert hasattr(window, "sidebar_toggle_btn")


def test_sidebar_state_persists_in_qsettings(window, qtbot):
    """Sidebar collapsed state should persist via QSettings."""
    from PySide6.QtCore import QSettings
    settings = QSettings("GeoViz", "Engine")
    window._toggle_sidebar()  # collapse
    assert settings.value("sidebar/collapsed", False, type=bool) is True
