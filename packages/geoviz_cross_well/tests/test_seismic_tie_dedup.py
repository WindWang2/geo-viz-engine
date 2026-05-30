"""Red tests for A7: CheckshotTable should delegate to WellTieCalibration.

These tests verify that after refactoring, CheckshotTable internally uses
WellTieCalibration for T-D interpolation, gaining array support while
preserving existing scalar behavior.
"""

import numpy as np
import pytest

from geoviz_cross_well.seismic_tie import CheckshotTable, SeismicTie


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def table() -> CheckshotTable:
    return CheckshotTable(
        well_name="W1",
        depths_m=np.array([0.0, 100.0, 200.0, 300.0]),
        twt_ms=np.array([0.0, 50.0, 110.0, 180.0]),
    )


# ── Red: array support via delegation ─────────────────────────────────

class TestCheckshotTableArraySupport:
    """Currently fails: interpolate_twt / interpolate_depth only accept scalars."""

    def test_interpolate_twt_array(self, table):
        result = table.interpolate_twt(np.array([0.0, 100.0, 200.0]))
        assert isinstance(result, np.ndarray)
        np.testing.assert_allclose(result, [0.0, 50.0, 110.0])

    def test_interpolate_depth_array(self, table):
        result = table.interpolate_depth(np.array([0.0, 50.0, 110.0]))
        assert isinstance(result, np.ndarray)
        np.testing.assert_allclose(result, [0.0, 100.0, 200.0])

    def test_interpolate_twt_scalar_still_works(self, table):
        result = table.interpolate_twt(150.0)
        assert isinstance(result, float)
        assert abs(result - 80.0) < 0.01

    def test_interpolate_depth_scalar_still_works(self, table):
        result = table.interpolate_depth(80.0)
        assert isinstance(result, float)
        assert abs(result - 150.0) < 0.01


# ── Red: internal delegation to WellTieCalibration ────────────────────

class TestCheckshotTableDelegation:
    """Currently fails: no .calibration property yet."""

    def test_has_calibration_property(self, table):
        from geoviz_well_tie.calibration import WellTieCalibration
        assert hasattr(table, "calibration")
        assert isinstance(table.calibration, WellTieCalibration)

    def test_calibration_preserves_pairs(self, table):
        cal = table.calibration
        np.testing.assert_array_equal(cal.depths, table.depths_m)
        np.testing.assert_array_equal(cal.twt, table.twt_ms)


# ── Regression: existing SeismicTie behavior ──────────────────────────

class TestSeismicTieRegression:
    """Must still pass after refactor."""

    def test_depth_to_twt_scalar(self):
        tie = SeismicTie()
        table = CheckshotTable(
            well_name="W1",
            depths_m=np.array([0.0, 100.0, 200.0]),
            twt_ms=np.array([0.0, 50.0, 110.0]),
        )
        tie._tables["W1"] = table
        assert abs(tie.depth_to_twt("W1", 150.0) - 80.0) < 0.01

    def test_twt_to_depth_scalar(self):
        tie = SeismicTie()
        table = CheckshotTable(
            well_name="W1",
            depths_m=np.array([0.0, 100.0, 200.0]),
            twt_ms=np.array([0.0, 50.0, 110.0]),
        )
        tie._tables["W1"] = table
        assert abs(tie.twt_to_depth("W1", 80.0) - 150.0) < 0.01

    def test_missing_well_returns_none(self):
        tie = SeismicTie()
        assert tie.depth_to_twt("X", 100.0) is None
        assert tie.twt_to_depth("X", 50.0) is None
