"""11.6-G regression: DTW 传播 button + UX wiring on the live CrossWellPage."""
import numpy as np
import pytest
from unittest.mock import patch

from src.pages.cross_well.page import CrossWellPage
from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_well_log.renderer.curve_track import CurveTrack
from geoviz_well_log.models import CurveData


def _populate_two_wells(page: CrossWellPage):
    """Inject two synthetic wells into the underlying CrossWellWidget."""
    n = 200
    rng = np.random.default_rng(7)
    base = rng.standard_normal(n).cumsum()
    depths = np.linspace(1000.0, 3000.0, n)
    target = np.roll(base, 15)
    for name, values in (("W1", base), ("W2", target)):
        sub = WellLogCanvas()
        sub.set_tracks([
            CurveTrack(
                curves=[CurveData(
                    name="GR", depth=list(depths), values=list(values),
                    display_range=(0.0, 200.0),
                )],
                label="GR",
            ),
        ])
        page._cross_well.add_canvas(sub, name)


def test_dtw_button_exists_and_tooltip(qtbot):
    """DTW button is in toolbar with a hint tooltip."""
    page = CrossWellPage()
    qtbot.addWidget(page)
    assert page._dtw_btn is not None
    assert page._dtw_btn.text() == "DTW 传播"
    assert "DTW" in page._dtw_btn.toolTip()
    assert "ghost" in page._dtw_btn.toolTip() or "灰色" in page._dtw_btn.toolTip()


def test_dtw_propagate_no_wells_shows_info(qtbot):
    """No wells loaded → message box, no crash."""
    page = CrossWellPage()
    qtbot.addWidget(page)
    with patch("src.pages.cross_well.page.QMessageBox.information") as mock_info:
        page._on_dtw_propagate()
    mock_info.assert_called_once()
    assert "至少需要 2 口井" in mock_info.call_args.args[2]


def test_dtw_propagate_no_manual_picks_shows_hint(qtbot):
    """Two wells but no manual pick → user-friendly hint."""
    page = CrossWellPage()
    qtbot.addWidget(page)
    _populate_two_wells(page)
    with patch("src.pages.cross_well.page.QMessageBox.information") as mock_info:
        page._on_dtw_propagate()
    mock_info.assert_called_once()
    assert "请先" in mock_info.call_args.args[2]


def test_dtw_propagate_produces_ghost_picks(qtbot):
    """Manual pick on W1 → DTW propagates to W2 as dtw-source pick."""
    page = CrossWellPage()
    qtbot.addWidget(page)
    _populate_two_wells(page)

    page._canvas.picks_model.add_pick("H1", "W1", 1800.0)

    with patch("src.pages.cross_well.page.QMessageBox.information"):
        page._on_dtw_propagate()

    w2_picks = page._canvas.picks_model.picks_for_well("W2")
    assert len(w2_picks) == 1
    assert w2_picks[0].source == "dtw"
    assert w2_picks[0].depth_for_well("W2") is not None


def test_status_shows_pick_hint_in_pick_mode(qtbot):
    """Status bar surfaces hotkey hint when pick mode is on."""
    page = CrossWellPage()
    qtbot.addWidget(page)
    _populate_two_wells(page)
    page._canvas.pick_mode = True
    page._update_status()
    text = page._status.text()
    assert "拾取模式" in text
    assert "左键" in text
    assert "Esc" in text


def test_status_updates_when_pick_added(qtbot):
    """picks_changed signal triggers status refresh with pick count."""
    page = CrossWellPage()
    qtbot.addWidget(page)
    _populate_two_wells(page)
    page._canvas.picks_model.add_pick("H1", "W1", 1500.0)
    assert "1 个层位点" in page._status.text()
