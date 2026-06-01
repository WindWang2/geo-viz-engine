import pytest
from PySide6.QtWidgets import QApplication, QPushButton, QGroupBox
from src.main import main

@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])

def test_global_qss_azurite_standards(app):
    # Verify that the Azurite design system constants are present in src/main.py
    with open("src/main.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    assert "#faf9f5" in content.lower()  # Background
    assert "1.6px" in content.lower()    # Stroke width
    assert "border-radius: 8px" in content.lower()
    assert "#1f66d4" in content.lower()  # Azurite Blue
    assert "#586878" in content.lower()  # Stroke Color
