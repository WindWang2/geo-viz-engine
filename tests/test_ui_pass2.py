import pytest
from PySide6.QtWidgets import QApplication, QPushButton, QStackedWidget, QFrame, QLabel
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


# ---------------------------------------------------------------------------
# Header refinement tests (Task 3)
# ---------------------------------------------------------------------------

def test_header_height_is_48(window):
    """Header should be 48px tall (was 52px)."""
    assert window.header_frame.height() == 48


def test_header_has_search_bar(window):
    """Header should contain an integrated search bar."""
    assert hasattr(window, "search_bar")


def test_search_bar_has_placeholder(window):
    """Search bar should have placeholder text."""
    assert "搜索" in window.search_bar.placeholderText()


def test_header_has_notification_bell(window):
    """Header should have a notification bell button."""
    assert hasattr(window, "notification_bell_btn")


# ---------------------------------------------------------------------------
# Footer enhancement tests (Task 4)
# ---------------------------------------------------------------------------

def test_footer_height_is_32(window):
    """Footer should be 32px tall (was 26px)."""
    assert window.footer_frame.height() == 32


def test_footer_has_gpu_info(window):
    """Footer should display GPU info."""
    assert hasattr(window, "gpu_info_label")
    assert "GPU" in window.gpu_info_label.text()


def test_footer_has_cache_info(window):
    """Footer should display cache size."""
    assert hasattr(window, "cache_info_label")
    assert "缓存" in window.cache_info_label.text()


def test_footer_has_dividers(window):
    """Footer should have section dividers."""
    dividers = window.footer_frame.findChildren(QFrame)
    h_dividers = [d for d in dividers if d.frameShape() == QFrame.Shape.VLine]
    assert len(h_dividers) >= 2


def test_footer_technical_text_is_monospace(window):
    """Footer technical data should use monospace font."""
    ss = window.gpu_info_label.styleSheet()
    assert "monospace" in ss


# ---------------------------------------------------------------------------
# Content page existence tests (Task 5-7)
# ---------------------------------------------------------------------------

def test_sidebar_has_group_labels(window):
    """Sidebar should have '可视化' and '工作区' group labels."""
    labels = window.sidebar.findChildren(QLabel)
    label_texts = [l.text() for l in labels]
    assert "可视化" in label_texts
    assert "工作区" in label_texts


def test_map_page_exists(window):
    """Map page should be instantiated (or have placeholder)."""
    assert hasattr(window, "map_page") or window.stack.count() > 0


def test_well_log_page_exists(window):
    """Well log page should be instantiated."""
    assert hasattr(window, "well_log_page")


def test_cross_well_page_exists(window):
    """Cross well page should be instantiated."""
    assert hasattr(window, "cross_well_page")


def test_seismic_page_exists(window):
    """Seismic page should be instantiated."""
    assert hasattr(window, "seismic_page") or window.stack.count() > 4
