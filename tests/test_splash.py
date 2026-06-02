import pytest
from PySide6.QtWidgets import QApplication, QSplashScreen, QLabel
from src.main import BrandSplashScreen

@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])

def test_brand_splash_screen_existence(app):
    splash = BrandSplashScreen()
    assert isinstance(splash, QSplashScreen)
    
    # Verify logo or text display is present
    lbl = splash.findChild(QLabel)
    assert lbl is not None
    assert "geoviz" in lbl.text().lower() or "engine" in lbl.text().lower() or "geo" in lbl.text().lower()
