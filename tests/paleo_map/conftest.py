"""Ensure a QApplication exists for paleo_map tests that paint."""
import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication([])
    yield app
