import pytest
from PySide6.QtWidgets import QApplication, QLabel, QFrame, QStackedWidget
from PySide6.QtGui import QColor
from src.app import MainWindow, SidebarButton

@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])

@pytest.fixture
def window(app, qtbot):
    w = MainWindow()
    qtbot.addWidget(w)
    return w

def test_mainwindow_sidebar_styling(window):
    sidebar = window.sidebar
    
    # Task 20.1: Sidebar width expanded to 200px
    assert sidebar.width() == 200 or sidebar.maximumWidth() == 200
    
    # Task 20.1: Sidebar background color is #ffffff (pure white)
    ss = sidebar.styleSheet()
    assert "background: #ffffff" in ss.lower() or "background-color: #ffffff" in ss.lower()

def test_mainwindow_appshell_elements(window):
    # Verify top header and bottom status bar exist as part of the new AppShell
    assert hasattr(window, "header_frame")
    assert hasattr(window, "footer_frame")
    assert isinstance(window.header_frame, QFrame)
    assert isinstance(window.footer_frame, QFrame)
    
    # Check header height constraint (Task 20.1: height 48px)
    assert window.header_frame.height() == 48 or window.header_frame.maximumHeight() == 48
    
    # Check footer height constraint (Task 20.1: height 26px)
    assert window.footer_frame.height() == 26 or window.footer_frame.maximumHeight() == 26

def test_brand_section_contents(window):
    # Verify brand logo and name label exist and show the correct HTML text
    assert hasattr(window, "brand_logo")
    assert hasattr(window, "brand_name_label")
    assert isinstance(window.brand_logo, QLabel)
    assert isinstance(window.brand_name_label, QLabel)
    
    # Rich HTML brand name text assert
    assert "geoviz" in window.brand_name_label.text().lower()
    assert "engine" in window.brand_name_label.text().lower()
    assert "span" in window.brand_name_label.text().lower()

def test_sidebar_button_azurite_styling(window):
    btn = window.sidebar_buttons[0]
    ss = btn.styleSheet()
    
    # Check for Azurite Blue (#1f66d4)
    assert "#1f66d4" in ss.lower()
    # Check for border-radius 8px
    assert "border-radius: 8px" in ss.lower()
    # Task 20.3: Active border-left strip indicator (3.5px solid #1f66d4)
    assert "border-left:" in ss.lower()
    assert "3.5px" in ss.lower()

def test_sidebar_grouping_and_settings(window):
    # Verify sidebar layout has the group labels "可视化" and "工作区"
    labels = window.sidebar.findChildren(QLabel)
    group_labels = [l.text() for l in labels if l.text() in ["可视化", "工作区"]]
    assert "可视化" in group_labels
    assert "工作区" in group_labels
    
    # Verify settings action is placed at the footer
    assert hasattr(window, "settings_btn")
    assert isinstance(window.settings_btn, SidebarButton)
    assert window.settings_btn.text().strip() == "设置"

def test_dynamic_header_footer_binding(window):
    # Switch to Map Page (index 0)
    window._switch_page(0)
    assert window.header_title.text() == "地图总览"
    assert "46" in window.header_sub.text()
    assert "地图就绪" in window.status_text.text()
    
    # Switch to Paleo Page (index 1)
    window._switch_page(1)
    assert window.header_title.text() == "古地理图"
    assert "沧浪铺组" in window.header_sub.text()
    assert "古地理图" in window.status_text.text()
    
    # Switch to Well Log Page (index 2)
    window._switch_page(2)
    assert window.header_title.text() == "老龙1"
    assert "2515" in window.header_sub.text()
    assert "老龙1" in window.status_text.text()
