import pytest
from app.services.data_generator import generate_well_log, generate_wells
from app.models.well_log import WellLogData


def test_generate_single_well_returns_model():
    well = generate_well_log("WELL-001", "Well 1", seed=42)
    assert isinstance(well, WellLogData)
    assert well.well_id == "WELL-001"
    assert well.well_name == "Well 1"


def test_generated_well_has_four_curves():
    well = generate_well_log("WELL-001", "Well 1", seed=42)
    assert len(well.curves) == 4


def test_generated_well_curve_names():
    well = generate_well_log("WELL-001", "Well 1", seed=42)
    names = {c.name for c in well.curves}
    assert names == {"GR", "RT", "DEN", "NPHI"}


def test_generated_well_sample_count():
    well = generate_well_log(
        "WELL-001", "Well 1",
        depth_start=0.0, depth_end=3000.0, depth_step=0.125, seed=42,
    )
    gr = next(c for c in well.curves if c.name == "GR")
    assert len(gr.data) == 24000
    assert len(gr.depth) == 24000


def test_gr_values_in_physical_range():
    well = generate_well_log("WELL-001", "Well 1", seed=42)
    gr = next(c for c in well.curves if c.name == "GR")
    assert all(5.0 <= v <= 200.0 for v in gr.data), "GR out of physical range"


def test_rt_values_positive():
    well = generate_well_log("WELL-001", "Well 1", seed=42)
    rt = next(c for c in well.curves if c.name == "RT")
    assert all(v > 0.0 for v in rt.data), "RT must be positive"


def test_den_values_in_physical_range():
    well = generate_well_log("WELL-001", "Well 1", seed=42)
    den = next(c for c in well.curves if c.name == "DEN")
    assert all(1.0 <= v <= 3.0 for v in den.data), "DEN out of physical range"


def test_nphi_values_in_physical_range():
    well = generate_well_log("WELL-001", "Well 1", seed=42)
    nphi = next(c for c in well.curves if c.name == "NPHI")
    assert all(0.0 <= v <= 0.6 for v in nphi.data), "NPHI out of physical range"


def test_gr_display_range_is_standard():
    well = generate_well_log("WELL-001", "Well 1", seed=42)
    gr = next(c for c in well.curves if c.name == "GR")
    assert gr.display_range == (0.0, 150.0)
    assert gr.unit == "API"


def test_rt_display_range_is_log_scale_friendly():
    well = generate_well_log("WELL-001", "Well 1", seed=42)
    rt = next(c for c in well.curves if c.name == "RT")
    assert rt.display_range == (0.1, 1000.0)
    assert rt.unit == "ohm.m"


def test_generate_multiple_wells_unique_ids():
    wells = generate_wells(count=10)
    assert len(wells) == 10
    ids = [w.well_id for w in wells]
    assert len(set(ids)) == 10


def test_different_seeds_produce_different_data():
    well1 = generate_well_log("W1", "W1", seed=1)
    well2 = generate_well_log("W2", "W2", seed=2)
    gr1 = next(c for c in well1.curves if c.name == "GR").data[:100]
    gr2 = next(c for c in well2.curves if c.name == "GR").data[:100]
    assert gr1 != gr2


def test_well_depth_metadata_correct():
    well = generate_well_log(
        "W1", "W1",
        depth_start=500.0, depth_end=2000.0, depth_step=0.5, seed=0,
    )
    assert well.depth_start == 500.0
    assert abs(well.depth_end - 2000.0) < 1.0
    assert well.depth_step == 0.5
