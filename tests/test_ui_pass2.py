import pytest
from PySide6.QtWidgets import QApplication
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
