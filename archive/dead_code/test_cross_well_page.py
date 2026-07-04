# tests/test_cross_well_page.py
import time
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from src.pages.cross_well.scene_page import _WellSelectDialog, _DepthRangeDialog


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_dialog_returns_selected_wells(app):
    dialog = _WellSelectDialog(["well1", "well2", "well3"])
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
from src.pages.cross_well.scene_page import _WellLoadWorker


def test_worker_emits_finished_with_data(app, qtbot):
    from unittest.mock import patch, MagicMock

    mock_data = MagicMock()
    mock_data.curves = []
    mock_data.top_depth = 0
    mock_data.bottom_depth = 100
    mock_data.intervals = None

    def fake_loader(path, well_name=None):
        return mock_data

    fake_entry = (fake_loader, "/fake/path.xlsx", {})

    worker = _WellLoadWorker(["well1"])
    received = []
    worker.finished.connect(lambda results: received.extend(results))

    with patch("src.pages.cross_well.scene_page.get_well_data", return_value=fake_entry):
        worker.run()

    assert len(received) == 1
    assert received[0][0] == "well1"
    assert received[0][1] is mock_data


def test_worker_skips_failed_wells(app, qtbot):
    from unittest.mock import patch, MagicMock

    def fake_get_well(name):
        if name == "bad_well":
            return None
        return (lambda path, well_name=None: MagicMock(curves=[], top_depth=0, bottom_depth=100, intervals=None), "/fake.xlsx", {})

    worker = _WellLoadWorker(["well1", "bad_well"])
    received = []
    worker.finished.connect(lambda results: received.extend(results))

    with patch("src.pages.cross_well.scene_page.get_well_data", side_effect=fake_get_well):
        worker.run()

    assert len(received) == 1  # bad_well skipped


# ---- CrossWellPage tests ----

from src.pages.cross_well.scene_page import CrossWellScenePage


def _wait_for_thread(page, timeout=5.0):
    """Wait for the background load thread to finish, processing Qt events."""
    deadline = time.monotonic() + timeout
    while getattr(page, "_thread", None) is not None and page._thread.isRunning():
        QApplication.processEvents()
        time.sleep(0.01)
        if time.monotonic() > deadline:
            pytest.fail("Timed out waiting for load thread to finish")


def test_page_creation(app):
    page = CrossWellScenePage()
    assert page.canvas_count == 0


def test_page_has_toolbar(app):
    page = CrossWellScenePage()
    assert page._toolbar is not None
    assert page._add_btn is not None


def test_page_add_button_opens_dialog(app, qtbot):
    page = CrossWellScenePage()
    assert page._add_btn.isEnabled()


def test_page_load_wells(app):
    from unittest.mock import patch, MagicMock
    page = CrossWellScenePage()

    mock_data = MagicMock()
    mock_data.curves = []
    mock_data.top_depth = 0
    mock_data.bottom_depth = 100
    mock_data.intervals = None

    fake_entry = (lambda path, well_name=None: mock_data, "/fake.xlsx", {})

    with patch("src.pages.cross_well.scene_page.get_well_data", return_value=fake_entry):
        with patch("src.pages.cross_well.scene_page.build_qpainter_tracks", return_value=[]):
            page._load_wells(["well1"])
            _wait_for_thread(page)

    assert page.canvas_count == 1


def test_page_clear_all(app):
    from unittest.mock import patch, MagicMock
    page = CrossWellScenePage()

    mock_data = MagicMock()
    mock_data.curves = []
    mock_data.top_depth = 0
    mock_data.bottom_depth = 100
    mock_data.intervals = None

    fake_entry = (lambda path, well_name=None: mock_data, "/fake.xlsx", {})

    with patch("src.pages.cross_well.scene_page.get_well_data", return_value=fake_entry):
        with patch("src.pages.cross_well.scene_page.build_qpainter_tracks", return_value=[]):
            page._load_wells(["well1", "well2"])
            _wait_for_thread(page)

    assert page.canvas_count == 2
    page._on_clear()
    assert page.canvas_count == 0


def test_page_placeholder_visible_when_empty(app):
    page = CrossWellScenePage()
    page.show()
    assert page._placeholder.isVisible()


def test_page_placeholder_hidden_when_loaded(app):
    from unittest.mock import patch, MagicMock
    page = CrossWellScenePage()

    mock_data = MagicMock()
    mock_data.curves = []
    mock_data.top_depth = 0
    mock_data.bottom_depth = 100
    mock_data.intervals = None

    fake_entry = (lambda path, well_name=None: mock_data, "/fake.xlsx", {})

    with patch("src.pages.cross_well.scene_page.get_well_data", return_value=fake_entry):
        with patch("src.pages.cross_well.scene_page.build_qpainter_tracks", return_value=[]):
            page._load_wells(["well1"])
            _wait_for_thread(page)

    page.show()
    assert not page._placeholder.isVisible()


def test_scene_has_tracks_after_load(app):
    from unittest.mock import patch, MagicMock
    from geoviz_well_log.renderer.depth_track import DepthTrack
    page = CrossWellScenePage()

    mock_data = MagicMock()
    mock_data.curves = []
    mock_data.top_depth = 0
    mock_data.bottom_depth = 100
    mock_data.intervals = None

    def fake_build(data):
        return [DepthTrack(top_depth=0, bottom_depth=100, width=60, label="深度")]

    fake_entry = (lambda path, well_name=None: mock_data, "/fake.xlsx", {})

    with patch("src.pages.cross_well.scene_page.get_well_data", return_value=fake_entry):
        with patch("src.pages.cross_well.scene_page.build_qpainter_tracks", side_effect=fake_build):
            page._load_wells(["well1"])
            _wait_for_thread(page)

    well = page._scene.well_by_name("well1")
    assert well is not None
    assert len(well.tracks) == 1


# ---- Edge case / guard tests ----


def test_page_export_no_wells(app):
    page = CrossWellScenePage()
    page._on_export()


def test_page_auto_link_no_wells(app):
    page = CrossWellScenePage()
    page._on_auto_link()


def test_page_manual_link_no_wells(app):
    page = CrossWellScenePage()
    page._on_toggle_manual_link()
    assert page._scene.manual_link_mode()
    page._on_toggle_manual_link()
    assert not page._scene.manual_link_mode()


def test_page_add_disabled_during_load(app):
    page = CrossWellScenePage()
    page._add_btn.setEnabled(False)
    assert not page._add_btn.isEnabled()
    page._on_load_finished([])
    assert page._add_btn.isEnabled()


# ---- Integration / smoke test ----


def test_full_workflow(app):
    from unittest.mock import patch, MagicMock
    from geoviz_well_log.renderer.depth_track import DepthTrack
    from geoviz_well_log.models import IntervalItem

    page = CrossWellScenePage()

    def fake_build(data):
        return [
            DepthTrack(top_depth=0, bottom_depth=100, width=60, label="深度"),
        ]

    mock_data = MagicMock()
    mock_data.curves = []
    mock_data.top_depth = 0
    mock_data.bottom_depth = 100
    mock_data.intervals = MagicMock()
    mock_data.intervals.formation = [
        IntervalItem(top=0, bottom=50, name="珠江组"),
        IntervalItem(top=50, bottom=100, name="韩江组"),
    ]

    fake_entry = (lambda path, well_name=None: mock_data, "/fake.xlsx", {})

    with patch("src.pages.cross_well.scene_page.get_well_data", return_value=fake_entry):
        with patch("src.pages.cross_well.scene_page.build_qpainter_tracks", side_effect=fake_build):
            page._load_wells(["well1", "well2"])
            _wait_for_thread(page)

    assert page.canvas_count == 2
    assert "well1" in page._scene._formation_data
    assert len(page._scene._formation_data["well1"]) == 2

    page._on_auto_link()
    assert len(page._scene.bands()) == 2  # 珠江组 and 韩江组

    page._on_clear()
    assert page.canvas_count == 0
    page.show()
    assert page._placeholder.isVisible()


# ---- Track filtering tests ----


def test_filter_tracks_selects_by_label(app):
    from geoviz_well_log.renderer.depth_track import DepthTrack
    from geoviz_well_log.renderer.interval_track import IntervalTrack
    from geoviz_well_log.models import IntervalItem

    tracks = [
        DepthTrack(top_depth=0, bottom_depth=100, width=60, label="深度"),
        IntervalTrack(intervals=[IntervalItem(top=10, bottom=50, name="A")], label="GR", width=140),
        IntervalTrack(intervals=[IntervalItem(top=10, bottom=50, name="B")], label="AC", width=140),
        IntervalTrack(intervals=[IntervalItem(top=10, bottom=50, name="C")], label="岩性", width=80),
    ]

    filtered = CrossWellScenePage._filter_tracks(tracks, ["深度", "AC", "岩性"])
    assert [t.label for t in filtered] == ["深度", "AC", "岩性"]


def test_filter_tracks_preserves_label_order(app):
    from geoviz_well_log.renderer.depth_track import DepthTrack
    from geoviz_well_log.renderer.interval_track import IntervalTrack
    from geoviz_well_log.models import IntervalItem

    tracks = [
        DepthTrack(top_depth=0, bottom_depth=100, width=60, label="深度"),
        IntervalTrack(intervals=[IntervalItem(top=10, bottom=50, name="A")], label="GR", width=140),
        IntervalTrack(intervals=[IntervalItem(top=10, bottom=50, name="B")], label="AC", width=140),
    ]

    filtered = CrossWellScenePage._filter_tracks(tracks, ["AC", "深度"])
    assert [t.label for t in filtered] == ["AC", "深度"]


def test_default_labels_depth_lithology_plus_3(app):
    labels = ["深度", "GR", "AC", "RT", "SP", "岩性", "组"]
    result = CrossWellScenePage._default_labels(labels)
    assert "深度" in result
    assert "岩性" in result
    optional = [l for l in result if l not in {"深度", "岩性"}]
    assert len(optional) == 3
    assert optional == ["GR", "AC", "RT"]


def test_default_labels_no_lithology_in_data(app):
    labels = ["深度", "GR", "AC", "RT", "SP"]
    result = CrossWellScenePage._default_labels(labels)
    assert "深度" in result
    assert "岩性" not in result
    optional = [l for l in result if l not in {"深度", "岩性"}]
    assert len(optional) == 3


def test_load_finished_filters_to_5_tracks(app):
    from unittest.mock import patch, MagicMock
    from geoviz_well_log.renderer.depth_track import DepthTrack
    from geoviz_well_log.renderer.interval_track import IntervalTrack
    from geoviz_well_log.models import IntervalItem

    page = CrossWellScenePage()

    def fake_build(data):
        return [
            DepthTrack(top_depth=0, bottom_depth=100, width=60, label="深度"),
            IntervalTrack(intervals=[], label="GR", width=140),
            IntervalTrack(intervals=[], label="AC", width=140),
            IntervalTrack(intervals=[], label="RT", width=140),
            IntervalTrack(intervals=[], label="SP", width=140),
            IntervalTrack(intervals=[], label="岩性", width=80),
            IntervalTrack(intervals=[], label="组", width=50),
        ]

    mock_data = MagicMock()
    mock_data.curves = []
    mock_data.top_depth = 0
    mock_data.bottom_depth = 100
    mock_data.intervals = None

    fake_entry = (lambda path, well_name=None: mock_data, "/fake.xlsx", {})

    with patch("src.pages.cross_well.scene_page.get_well_data", return_value=fake_entry):
        with patch("src.pages.cross_well.scene_page.build_qpainter_tracks", side_effect=fake_build):
            page._load_wells(["well1"])
            _wait_for_thread(page)

    assert page.canvas_count == 1
    well = page._scene.well_by_name("well1")
    track_labels = [t.label for t in well.tracks]
    assert len(track_labels) == 5
    assert "深度" in track_labels
    assert "岩性" in track_labels


def test_track_select_dialog_enforces_limit(app):
    from src.pages.cross_well.scene_page import _TrackSelectDialog

    all_labels = ["深度", "GR", "AC", "RT", "SP", "岩性"]
    selected = ["深度", "GR", "AC", "RT", "岩性"]
    dialog = _TrackSelectDialog(all_labels, selected)

    for i in range(dialog._list.count()):
        item = dialog._list.item(i)
        if item.text() == "SP":
            item.setCheckState(Qt.CheckState.Checked)
            break

    optional_checked = sum(
        1 for i in range(dialog._list.count())
        if dialog._list.item(i).checkState() == Qt.CheckState.Checked
        and dialog._list.item(i).text() not in {"深度", "岩性"}
    )
    assert optional_checked <= 3


# ---- Depth scale and depth range tests ----


def test_depth_scale_spin_controls_scene(app):
    page = CrossWellScenePage()
    assert page._scene.depth_scale() == 0.8
    page._scale_spin.setValue(1.5)
    assert page._scene.depth_scale() == 1.5


def test_per_well_depth_range(app):
    from unittest.mock import patch, MagicMock
    page = CrossWellScenePage()

    mock_data = MagicMock()
    mock_data.curves = []
    mock_data.top_depth = 0
    mock_data.bottom_depth = 100
    mock_data.intervals = None

    fake_entry = (lambda path, well_name=None: mock_data, "/fake.xlsx", {})

    with patch("src.pages.cross_well.scene_page.get_well_data", return_value=fake_entry):
        with patch("src.pages.cross_well.scene_page.build_qpainter_tracks", return_value=[]):
            page._load_wells(["well1"])
            _wait_for_thread(page)

    page._scene.set_well_depth_range("well1", 10, 80)
    well = page._scene.well_by_name("well1")
    assert well.depth_top == 10
    assert well.depth_bottom == 80


def test_global_depth_range_sets_all_wells(app):
    from unittest.mock import patch, MagicMock
    page = CrossWellScenePage()

    mock_data = MagicMock()
    mock_data.curves = []
    mock_data.top_depth = 0
    mock_data.bottom_depth = 100
    mock_data.intervals = None

    fake_entry = (lambda path, well_name=None: mock_data, "/fake.xlsx", {})

    with patch("src.pages.cross_well.scene_page.get_well_data", return_value=fake_entry):
        with patch("src.pages.cross_well.scene_page.build_qpainter_tracks", return_value=[]):
            page._load_wells(["well1", "well2"])
            _wait_for_thread(page)

    page._scene.set_all_well_depth_range(20, 90)
    for w in page._scene.wells():
        assert w.depth_top == 20
        assert w.depth_bottom == 90


def test_depth_range_dialog_returns_values(app):
    dialog = _DepthRangeDialog("test_well", 0, 100)
    dialog._top_spin.setValue(10)
    dialog._bottom_spin.setValue(80)
    top, bottom = dialog.get_range()
    assert top == 10
    assert bottom == 80


def test_reset_well_to_data_range(app):
    from unittest.mock import patch, MagicMock
    page = CrossWellScenePage()

    mock_data = MagicMock()
    mock_data.curves = []
    mock_data.top_depth = 5
    mock_data.bottom_depth = 95
    mock_data.intervals = None

    fake_entry = (lambda path, well_name=None: mock_data, "/fake.xlsx", {})

    with patch("src.pages.cross_well.scene_page.get_well_data", return_value=fake_entry):
        with patch("src.pages.cross_well.scene_page.build_qpainter_tracks", return_value=[]):
            page._load_wells(["well1"])
            _wait_for_thread(page)

    # Override range
    page._scene.set_well_depth_range("well1", 20, 60)
    well = page._scene.well_by_name("well1")
    assert well.depth_top == 20

    # Reset to data range
    page._reset_well_to_data_range("well1")
    assert well.depth_top == 5
    assert well.depth_bottom == 95
