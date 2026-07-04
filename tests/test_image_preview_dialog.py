"""Unit tests for ImagePreviewDialog image inspector modal."""
import pytest
from PySide6.QtGui import QPixmap, QColor
from geoviz_well_log.image_preview_dialog import ImagePreviewDialog

@pytest.fixture
def preview_dialog(qtbot):
    pixmap = QPixmap(200, 200)
    pixmap.fill(QColor(31, 102, 212))
    dialog = ImagePreviewDialog(pixmap=pixmap, title="Core Photo Segment #1 (2100m-2105m)")
    qtbot.addWidget(dialog)
    return dialog

def test_image_preview_dialog_initialization(preview_dialog):
    assert preview_dialog is not None
    assert "2100m" in preview_dialog.windowTitle()
