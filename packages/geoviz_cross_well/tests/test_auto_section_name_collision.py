"""ISSUE-014: duplicate well names must not drop wells from the section."""

from __future__ import annotations

from geoviz_cross_well.auto_section_planner import plan_section_nearest_neighbor


def test_duplicate_names_keep_all_wells():
    wells = [
        {"name": "A", "lng": 0.0, "lat": 0.0},
        {"name": "A", "lng": 1.0, "lat": 0.0},
        {"name": "B", "lng": 2.0, "lat": 0.0},
    ]
    out = plan_section_nearest_neighbor(wells)
    assert len(out) == 3, f"{len(out)}/3 wells returned — duplicate dropped"
    coords = sorted((w["lng"], w["lat"]) for w in out)
    assert coords == [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]


def test_distinct_names_unchanged():
    wells = [
        {"name": "A", "lng": 0.0, "lat": 0.0},
        {"name": "B", "lng": 1.0, "lat": 0.0},
        {"name": "C", "lng": 3.0, "lat": 0.0},
    ]
    out = plan_section_nearest_neighbor(wells)
    assert len(out) == 3
    lngs = [w["lng"] for w in out]
    # Nearest-neighbour from a PCA endpoint never skips a middle well.
    assert sorted(lngs) == [0.0, 1.0, 3.0]
