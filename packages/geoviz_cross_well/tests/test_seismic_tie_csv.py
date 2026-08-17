"""SeismicTie.load_csv grouping and header detection."""

from __future__ import annotations

from geoviz_cross_well.seismic_tie import SeismicTie


def test_load_csv_splits_tables_per_well(tmp_path):
    """#673: a well column must not concatenate every row onto the last well."""
    path = tmp_path / "multi_well_checkshots.csv"
    path.write_text(
        "depth_m,twt_ms,well\n"
        "0,0,W1\n"
        "500,400,W1\n"
        "1000,800,W1\n"
        "0,0,W2\n"
        "250,180,W2\n"
        "500,360,W2\n",
        encoding="utf-8",
    )
    tie = SeismicTie()
    tie.load_csv(str(path))

    assert set(tie.well_names()) == {"W1", "W2"}
    w1 = tie.table_for_well("W1")
    w2 = tie.table_for_well("W2")
    assert w1 is not None and w2 is not None
    assert float(w1.depths_m.min()) == 0.0
    assert float(w1.depths_m.max()) == 1000.0
    assert float(w2.depths_m.min()) == 0.0
    assert float(w2.depths_m.max()) == 500.0
    assert tie.depth_to_twt("W1", 500.0) == 400.0
    assert tie.depth_to_twt("W2", 250.0) == 180.0


def test_load_csv_single_well_without_well_column(tmp_path):
    path = tmp_path / "one_well.csv"
    path.write_text("depth_m,twt_ms\n0,0\n1000,800\n", encoding="utf-8")
    tie = SeismicTie()
    tie.load_csv(str(path), well_name="A1")
    assert tie.well_names() == ["A1"]
    assert float(tie.table_for_well("A1").depths_m.max()) == 1000.0
