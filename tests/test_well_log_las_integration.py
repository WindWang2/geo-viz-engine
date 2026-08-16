"""Integration tests for WellLogPage LAS file import and ImageTrack export."""
import os
import pytest
from src.pages.well_log.page import WellLogPage

@pytest.fixture
def well_log_page(qtbot):
    page = WellLogPage()
    qtbot.addWidget(page)
    page.resize(1000, 700)
    page.show()
    return page

def test_well_log_page_las_import(well_log_page, tmp_path):
    las_file = str(tmp_path / "test_well.las")
    with open(las_file, "w", encoding="utf-8") as f:
        f.write("""~VERSION
 VERS . 2.0 : CWLS
~WELL
 WELL. TEST-WELL-99 :
~CURVE
 DEPT.M :
 GR.API :
~ASCII
 1000.00 45.0
 1001.00 50.0
""")

    ok = well_log_page.import_las_file(las_file)

    # #510/#573: the import must actually display data, not silently
    # discard the parse result (the old test only asserted the page object
    # existed — a tautology that masked the dead feature).
    assert ok is True
    assert well_log_page._last_import_error is None
    assert "TEST-WELL-99" in well_log_page._last_import_summary
    assert well_log_page._current_well == "TEST-WELL-99"
    assert well_log_page._current_data is not None
    assert well_log_page._current_data.curves, "parsed curves must be kept"
    curve_names = {c.name for c in well_log_page._current_data.curves}
    assert "GR" in curve_names
    # The display pipeline ran: tracks built and installed on the canvas.
    assert well_log_page._all_tracks, "tracks must be built from the LAS"
    assert well_log_page._qpainter_widget is not None
    assert "TEST-WELL-99" in well_log_page._well_name_label.text()
    gr_values = next(c for c in well_log_page._current_data.curves if c.name == "GR").values
    assert gr_values == [45.0, 50.0]


def test_well_log_page_las_import_failure_reports(well_log_page, tmp_path):
    """A garbage file must report failure and leave the page unchanged."""
    bad = tmp_path / "garbage.las"
    bad.write_text("not a las file at all\n", encoding="utf-8")

    ok = well_log_page.import_las_file(str(bad))
    assert ok is False
    assert well_log_page._last_import_error
    assert "LAS" in well_log_page._last_import_error
    assert well_log_page._current_well is None
    assert well_log_page._current_data is None


def test_well_log_page_las_import_empty_curves_reports(well_log_page, tmp_path):
    """A structurally valid LAS with no data rows must not count as success."""
    empty = tmp_path / "empty.las"
    empty.write_text(
        "~VERSION\n VERS . 2.0 : CWLS\n"
        "~WELL\n WELL. EMPTY-1 :\n"
        "~CURVE\n DEPT.M :\n GR.API :\n"
        "~ASCII\n",
        encoding="utf-8",
    )
    ok = well_log_page.import_las_file(str(empty))
    assert ok is False
    assert well_log_page._last_import_error
    assert well_log_page._current_well is None
