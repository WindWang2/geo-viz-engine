import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor
from src.app import MainWindow, SidebarButton

@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])

def test_mainwindow_sidebar_styling(app):
    window = MainWindow()
    sidebar = window.sidebar
    
    # Check sidebar width (Task 20.2: 160px)
    assert sidebar.width() == 160 or sidebar.maximumWidth() == 160
    
    # Check sidebar background color (Task 20.2: #faf9f5)
    # Note: Stylesheet colors are harder to check directly without parsing QSS,
    # but we can check if the sidebar has the expected stylesheet snippet.
    ss = sidebar.styleSheet()
    assert "#faf9f5" in ss.lower()

def test_sidebar_button_azurite_styling(app):
    window = MainWindow()
    btn = window.sidebar_buttons[0]
    ss = btn.styleSheet()
    
    # Check for Azurite Blue (#1f66d4)
    assert "#1f66d4" in ss.lower()
    # Check for border-radius 8px
    assert "border-radius: 8px" in ss.lower()
