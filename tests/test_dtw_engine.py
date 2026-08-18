"""DTWEngine correctness: band feasibility, NaN guard, ghost-pick gating."""
import numpy as np
import pytest

from geoviz_cross_well.dtw_engine import DTWEngine


def _curves(n, m, seed=0, offset=0.0):
    rng = np.random.default_rng(seed)
    ref = rng.standard_normal(n).cumsum() + offset
    depths = np.linspace(1000.0, 3000.0, n)
    tgt = np.roll(ref, 15) if m == n else rng.standard_normal(m).cumsum()
    tgt_depths = np.linspace(1000.0, 3000.0, m)
    return ref, depths, tgt, tgt_depths


def test_correlate_infeasible_when_length_difference_exceeds_band():
    """|m-n| > band_radius makes the endpoint unreachable: the result must be
    reported infeasible instead of a single-cell path with false confidence."""
    engine = DTWEngine()
    ref, ref_depths, tgt, tgt_depths = _curves(1500, 2200)
    result = engine.correlate(
        ref, ref_depths, tgt, tgt_depths, band_radius=500
    )
    assert result.feasible is False
    assert result.confidence == 0.0
    assert result.suggested_depth == 0.0


def test_correlate_infeasible_on_nan_samples():
    """A single NaN sample must not produce NaN confidence; report infeasible."""
    engine = DTWEngine()
    ref, ref_depths, tgt, tgt_depths = _curves(200, 200)
    ref = ref.copy()
    ref[50] = np.nan
    result = engine.correlate(ref, ref_depths, tgt, tgt_depths)
    assert result.feasible is False
    assert result.confidence == 0.0


def test_correlate_feasible_within_band():
    """A normal in-band alignment stays feasible with a sane confidence."""
    engine = DTWEngine()
    ref, ref_depths, tgt, tgt_depths = _curves(200, 200)
    result = engine.correlate(ref, ref_depths, tgt, tgt_depths, band_radius=50)
    assert result.feasible is True
    assert 0.0 <= result.confidence <= 1.0
    assert ref_depths[0] <= result.suggested_depth <= ref_depths[-1]


def test_correlate_short_inputs_infeasible():
    engine = DTWEngine()
    ref, ref_depths, tgt, tgt_depths = _curves(1, 200)
    result = engine.correlate(ref, ref_depths, tgt, tgt_depths)
    assert result.feasible is False


def test_propagate_pick_via_dtw_skips_infeasible_targets(qtbot):
    """Ghost picks must not be created for infeasible alignments (#539)."""
    from unittest.mock import patch

    import numpy as np

    from geoviz_cross_well.canvas import CrossWellCanvas
    from geoviz_well_log.models import CurveData
    from geoviz_well_log.renderer.canvas import WellLogCanvas
    from geoviz_well_log.renderer.curve_track import CurveTrack

    def _well_canvas(name, n):
        rng = np.random.default_rng(3)
        values = rng.standard_normal(n).cumsum()
        depths = np.linspace(1000.0, 3000.0, n)
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
        return sub

    canvas = CrossWellCanvas()
    qtbot.addWidget(canvas)
    canvas.widget.add_canvas(_well_canvas("W1", 200), "W1")
    canvas.widget.add_canvas(_well_canvas("W2", 200), "W2")

    # A fake engine that reports infeasible for every target.
    with patch.object(
        canvas.dtw_engine,
        "correlate",
        return_value=type(
            "R", (), {"feasible": False, "suggested_depth": 1234.0, "confidence": 0.9}
        )(),
    ):
        created = canvas.propagate_pick_via_dtw("W1", 1500.0, "F1")
    assert created == []


def test_propagate_pick_via_dtw_creates_pick_when_feasible(qtbot):
    """A feasible alignment still creates the pick (sanity check the gate)."""
    from unittest.mock import patch

    import numpy as np

    from geoviz_cross_well.canvas import CrossWellCanvas
    from geoviz_well_log.models import CurveData
    from geoviz_well_log.renderer.canvas import WellLogCanvas
    from geoviz_well_log.renderer.curve_track import CurveTrack

    def _well_canvas(name, n):
        rng = np.random.default_rng(3)
        values = rng.standard_normal(n).cumsum()
        depths = np.linspace(1000.0, 3000.0, n)
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
        return sub

    canvas = CrossWellCanvas()
    qtbot.addWidget(canvas)
    canvas.widget.add_canvas(_well_canvas("W1", 200), "W1")
    canvas.widget.add_canvas(_well_canvas("W2", 200), "W2")

    with patch.object(
        canvas.dtw_engine,
        "correlate",
        return_value=type(
            "R", (), {"feasible": True, "suggested_depth": 2000.0, "confidence": 0.8}
        )(),
    ):
        created = canvas.propagate_pick_via_dtw("W1", 1500.0, "F1")
    assert len(created) == 1


def test_compute_dtw_propagation_is_pure_data(qtbot):
    """The compute half must not touch the picks model (#826 host contract:
    worker threads run DTW; GUI threads apply picks)."""
    import numpy as np

    from geoviz_cross_well.canvas import CrossWellCanvas
    from geoviz_well_log.models import CurveData
    from geoviz_well_log.renderer.canvas import WellLogCanvas
    from geoviz_well_log.renderer.curve_track import CurveTrack

    def _well_canvas(name, n):
        values = np.linspace(0.0, 100.0, n)
        depths = np.linspace(1000.0, 3000.0, n)
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
        return sub

    canvas = CrossWellCanvas()
    qtbot.addWidget(canvas)
    canvas.widget.add_canvas(_well_canvas("W1", 200), "W1")
    canvas.widget.add_canvas(_well_canvas("W2", 200), "W2")
    before = canvas.picks_model.all_picks()

    pairs = canvas.compute_dtw_propagation("W1", 1500.0)
    assert isinstance(pairs, list)
    for item in pairs:
        assert isinstance(item, tuple) and len(item) == 2
        name, depth = item
        assert name == "W2"
        assert 1000.0 <= float(depth) <= 3000.0
    # Pure computation: identical model state, no ghost picks created.
    assert canvas.picks_model.all_picks() == before

    # The legacy convenience API applies the computed pairs on top.
    created = canvas.propagate_pick_via_dtw("W1", 1500.0, "F1")
    assert len(created) == len(pairs)
    assert len(canvas.picks_model.all_picks()) == len(before) + len(pairs)
