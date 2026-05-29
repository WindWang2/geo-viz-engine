"""Tests for CrossWellCanvas."""
import pytest

from geoviz_cross_well.tops_model import FormationTopsModel, FormationTop
from geoviz_cross_well.picks_model import HorizonPicksModel
from geoviz_cross_well.seismic_tie import SeismicTie, CheckshotTable
from geoviz_cross_well.dtw_engine import DTWEngine
import numpy as np


def test_tops_model_integration():
    tops = FormationTopsModel()
    tops.add_top(FormationTop("W1", "Jurassic", 1250.0))
    tops.add_top(FormationTop("W2", "Jurassic", 1280.0))

    assert len(tops.tops_for_well("W1")) == 1
    assert tops.tops_for_well("W1")[0].depth_m == 1250.0


def test_picks_model_integration():
    picks = HorizonPicksModel()
    p1 = picks.add_pick("Jurassic", "W1", 1250.0)
    picks.connect_picks(p1, "W2", 1280.0)

    w1 = picks.picks_for_well("W1")
    assert len(w1) == 1
    assert w1[0].depth_for_well("W2") == 1280.0

    picks.undo()
    assert w1[0].depth_for_well("W2") is None


def test_seismic_tie():
    tie = SeismicTie()
    table = CheckshotTable(
        well_name="W1",
        depths_m=np.array([0.0, 100.0, 200.0, 300.0]),
        twt_ms=np.array([0.0, 50.0, 110.0, 180.0]),
    )
    tie._tables["W1"] = table

    twt = tie.depth_to_twt("W1", 150.0)
    assert twt is not None
    assert abs(twt - 80.0) < 0.01

    depth = tie.twt_to_depth("W1", 80.0)
    assert depth is not None
    assert abs(depth - 150.0) < 0.01

    assert tie.depth_to_twt("W2", 100.0) is None


def test_dtw_engine_basic():
    engine = DTWEngine()
    curve = np.sin(np.linspace(0, 4 * np.pi, 50))
    depths = np.linspace(0, 500, 50)

    result = engine.correlate(curve, depths, curve.copy(), depths)
    assert result.cost < 0.01
    assert result.confidence > 0.99
