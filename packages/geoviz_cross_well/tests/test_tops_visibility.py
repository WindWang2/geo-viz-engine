"""CrossWellCanvas.set_tops_visible tests."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_tops_visible_default_true(qapp):
    from geoviz_cross_well.canvas import CrossWellCanvas

    canvas = CrossWellCanvas()
    assert canvas._overlay._tops_visible is True


def test_set_tops_visible_toggles_overlay(qapp):
    from geoviz_cross_well.canvas import CrossWellCanvas

    canvas = CrossWellCanvas()
    canvas.set_tops_visible(False)
    assert canvas._overlay._tops_visible is False
    canvas.set_tops_visible(True)
    assert canvas._overlay._tops_visible is True
