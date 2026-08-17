import pytest
from PySide6.QtWidgets import QApplication
from geoviz_seismic.seismic_view import SeismicView

@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])

def test_seismic_view_button_icons(app):
    view = SeismicView(auto_load=False)
    # Find the load button
    # Since it's a local variable in _build_toolbar, we might need to find children
    from PySide6.QtWidgets import QPushButton
    btns = view.findChildren(QPushButton)
    
    # In Azurite redesign, most primary buttons should have icons
    # Check if at least some buttons have icons
    icon_btns = [b for b in btns if not b.icon().isNull()]
    assert len(icon_btns) >= 5, f"Expected at least 5 buttons with icons, found {len(icon_btns)}"


def test_seismic_page_tie_label_is_not_fabricated(app):
    """#704: sidebar must not advertise a fake 87.4% well-tie quality."""
    from src.pages.seismic.page import SeismicPage

    page = SeismicPage(auto_load=False)
    text = page._tie_quality_label.text()
    assert "87.4" not in text
    assert "未标定" in text or "—" in text
