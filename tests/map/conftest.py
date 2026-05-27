"""Ensure a QApplication exists for map layer tests that draw text."""
import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication([])
    yield app
