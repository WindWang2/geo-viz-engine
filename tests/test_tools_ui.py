import pytest
from PySide6.QtWidgets import QApplication, QPushButton, QGroupBox
from src.pages.tools.page import ToolsPage

@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])

def test_tools_page_azurite_icons(app):
    page = ToolsPage()
    
    # Check for icons on conversion button
    # Since it's a local variable in __init__, we might need to find children
    btns = page.findChildren(QPushButton)
    icon_btns = [b for b in btns if not b.icon().isNull()]
    assert len(icon_btns) >= 3, f"Expected at least 3 buttons with icons in ToolsPage, found {len(icon_btns)}"

def test_tools_page_styling(app):
    page = ToolsPage()
    # Check for Azurite title color
    from PySide6.QtWidgets import QLabel
    labels = page.findChildren(QLabel)
    title_label = [l for l in labels if l.text() == " 工具箱"][0]
    assert "#1f66d4" in title_label.styleSheet().lower()
