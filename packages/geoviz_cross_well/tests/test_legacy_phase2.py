"""Red tests for Phase 2 legacy items: DTW ghost picks UX and dual-axis display."""

import numpy as np
import pytest

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent

from geoviz_cross_well.picks_model import HorizonPicksModel, HorizonPick
from geoviz_cross_well.seismic_tie import SeismicTie, CheckshotTable


# ── DTW Ghost Picks: left-click accept ────────────────────────────────

class TestDTWGhostPickAccept:
    """Left-clicking a DTW ghost pick should accept it (source → manual)."""

    def test_accept_dtw_pick_changes_source(self):
        """accept_dtw_pick should change source from 'dtw' to 'manual'."""
        model = HorizonPicksModel()
        pick_id = model.add_pick("F1", "W1", 1000.0, source="dtw")
        model.accept_dtw_pick(pick_id)
        pick = model.get_pick(pick_id)
        assert pick is not None
        assert pick.source == "manual"
        assert pick.confidence == {}

    def test_accept_dtw_pick_preserves_depths(self):
        """Accepting should keep all well depths intact."""
        model = HorizonPicksModel()
        pick_id = model.add_pick("F1", "W1", 1000.0, source="dtw")
        model.connect_picks(pick_id, "W2", 1050.0)
        model.accept_dtw_pick(pick_id)
        pick = model.get_pick(pick_id)
        assert pick.depth_for_well("W1") == 1000.0
        assert pick.depth_for_well("W2") == 1050.0

    def test_accept_manual_pick_is_noop(self):
        """Accepting a manual pick should be a no-op."""
        model = HorizonPicksModel()
        pick_id = model.add_pick("F1", "W1", 1000.0, source="manual")
        model.accept_dtw_pick(pick_id)
        pick = model.get_pick(pick_id)
        assert pick.source == "manual"

    def test_accept_nonexistent_pick_is_noop(self):
        """Accepting a nonexistent pick should not crash."""
        model = HorizonPicksModel()
        model.accept_dtw_pick("nonexistent-id")  # should not raise


# ── SeismicTie: dual-axis domain conversion ───────────────────────────

class TestSeismicTieDualAxis:
    """Verify depth domain conversion via SeismicTie for overlay rendering."""

    @pytest.fixture
    def tie(self):
        tie = SeismicTie()
        table = CheckshotTable(
            well_name="W1",
            depths_m=np.array([0.0, 500.0, 1000.0, 1500.0, 2000.0]),
            twt_ms=np.array([0.0, 300.0, 650.0, 1050.0, 1500.0]),
        )
        tie._tables["W1"] = table
        return tie

    def test_depth_to_twt_for_well(self, tie):
        result = tie.depth_to_twt("W1", 1000.0)
        assert result is not None
        assert abs(result - 650.0) < 0.01

    def test_twt_to_depth_for_well(self, tie):
        result = tie.twt_to_depth("W1", 650.0)
        assert result is not None
        assert abs(result - 1000.0) < 0.01

    def test_depth_to_twt_array_via_calibration(self, tie):
        """CheckshotTable.calibration enables array TWT conversion."""
        table = tie.table_for_well("W1")
        depths = np.array([0.0, 1000.0, 2000.0])
        twt = table.calibration.depth_to_twt(depths)
        np.testing.assert_allclose(twt, [0.0, 650.0, 1500.0])

    def test_depth_domain_toggle(self, qtbot):
        """PickingOverlay.set_depth_domain should accept 'MD' and 'TWT'."""
        from geoviz_cross_well.canvas import PickingOverlay
        overlay = PickingOverlay()
        qtbot.addWidget(overlay)
        overlay.set_depth_domain("TWT")
        assert overlay._depth_domain == "TWT"
        overlay.set_depth_domain("MD")
        assert overlay._depth_domain == "MD"
