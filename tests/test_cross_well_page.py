# tests/test_cross_well_page.py
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from src.pages.cross_well.page import _WellSelectDialog


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_dialog_returns_selected_wells(app):
    dialog = _WellSelectDialog(["well1", "well2", "well3"])
    # Check two wells
    for i in range(dialog._list.count()):
        item = dialog._list.item(i)
        if item.text() in ("well1", "well3"):
            item.setCheckState(Qt.CheckState.Checked)
    result = dialog.get_selected()
    assert result == ["well1", "well3"]


def test_dialog_empty_selection(app):
    dialog = _WellSelectDialog(["well1"])
    result = dialog.get_selected()
    assert result == []


def test_dialog_sorted_wells(app):
    dialog = _WellSelectDialog(["well3", "well1", "well2"])
    items = [dialog._list.item(i).text() for i in range(dialog._list.count())]
    assert items == ["well1", "well2", "well3"]


from PySide6.QtCore import Qt, QThread
from src.pages.cross_well.page import _WellLoadWorker
from geoviz_well_log.renderer.canvas import WellLogCanvas


def test_worker_emits_finished_with_canvases(app, qtbot):
    """Worker should emit finished signal with a list of WellLogCanvas."""
    from unittest.mock import patch, MagicMock

    # Mock get_well_data to return a controlled loader
    mock_data = MagicMock()
    mock_data.curves = []
    mock_data.top_depth = 0
    mock_data.bottom_depth = 100
    mock_data.intervals = None

    def fake_loader(path, well_name=None):
        return mock_data

    fake_entry = (fake_loader, "/fake/path.xlsx", {})

    worker = _WellLoadWorker(["well1"])
    with patch("src.pages.cross_well.page.get_well_data", return_value=fake_entry):
        with patch("src.pages.cross_well.page.build_qpainter_tracks", return_value=[]):
            # Direct call (not threaded) for testing
            worker.run()

    assert len(worker.result) == 1
    assert isinstance(worker.result[0], WellLogCanvas)


def test_worker_skips_failed_wells(app):
    from unittest.mock import patch, MagicMock

    def fake_get_well(name):
        if name == "bad_well":
            return None
        return (lambda path, well_name=None: MagicMock(curves=[], top_depth=0, bottom_depth=100, intervals=None), "/fake.xlsx", {})

    worker = _WellLoadWorker(["well1", "bad_well"])
    with patch("src.pages.cross_well.page.get_well_data", side_effect=fake_get_well):
        with patch("src.pages.cross_well.page.build_qpainter_tracks", return_value=[]):
            worker.run()

    assert len(worker.result) == 1  # bad_well skipped


# ---- CrossWellPage tests ----

from src.pages.cross_well.page import CrossWellPage


def test_page_creation(app):
    page = CrossWellPage()
    assert page.canvas_count == 0


def test_page_has_toolbar(app):
    page = CrossWellPage()
    assert page._toolbar is not None
    assert page._add_btn is not None


def test_page_add_button_opens_dialog(app, qtbot):
    page = CrossWellPage()
    # Verify add_btn is connected (click should not crash without wells)
    # We just check the button exists and is enabled
    assert page._add_btn.isEnabled()


def test_page_load_wells(app):
    from unittest.mock import patch, MagicMock
    page = CrossWellPage()

    mock_data = MagicMock()
    mock_data.curves = []
    mock_data.top_depth = 0
    mock_data.bottom_depth = 100
    mock_data.intervals = None

    fake_entry = (lambda path, well_name=None: mock_data, "/fake.xlsx", {})

    with patch("src.pages.cross_well.page.get_well_data", return_value=fake_entry):
        with patch("src.pages.cross_well.page.build_qpainter_tracks", return_value=[]):
            page._load_wells(["well1"])

    assert page.canvas_count == 1


def test_page_clear_all(app):
    from unittest.mock import patch, MagicMock
    page = CrossWellPage()

    mock_data = MagicMock()
    mock_data.curves = []
    mock_data.top_depth = 0
    mock_data.bottom_depth = 100
    mock_data.intervals = None

    fake_entry = (lambda path, well_name=None: mock_data, "/fake.xlsx", {})

    with patch("src.pages.cross_well.page.get_well_data", return_value=fake_entry):
        with patch("src.pages.cross_well.page.build_qpainter_tracks", return_value=[]):
            page._load_wells(["well1", "well2"])

    assert page.canvas_count == 2
    page._on_clear()
    assert page.canvas_count == 0


def test_page_placeholder_visible_when_empty(app):
    page = CrossWellPage()
    page.show()
    assert page._placeholder.isVisible()


def test_page_placeholder_hidden_when_loaded(app):
    from unittest.mock import patch, MagicMock
    page = CrossWellPage()

    mock_data = MagicMock()
    mock_data.curves = []
    mock_data.top_depth = 0
    mock_data.bottom_depth = 100
    mock_data.intervals = None

    fake_entry = (lambda path, well_name=None: mock_data, "/fake.xlsx", {})

    with patch("src.pages.cross_well.page.get_well_data", return_value=fake_entry):
        with patch("src.pages.cross_well.page.build_qpainter_tracks", return_value=[]):
            page._load_wells(["well1"])

    page.show()
    assert not page._placeholder.isVisible()
