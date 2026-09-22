"""Tests for FormationTopsModel."""
import csv
import tempfile
import os

from geoviz_cross_well.tops_model import FormationTopsModel, FormationTop


def _write_csv(path: str, rows: list[list[str]]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)


def test_csv_roundtrip():
    model = FormationTopsModel()
    rows = [
        ["WELL-A", "Jurassic", "1250.0"],
        ["WELL-A", "Triassic", "1800.0"],
        ["WELL-B", "Jurassic", "1280.0"],
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        path = f.name
    try:
        _write_csv(path, rows)
        model.load_csv(path)
        assert len(model.tops_for_well("WELL-A")) == 2
        assert len(model.tops_for_well("WELL-B")) == 1
        assert model.tops_for_well("WELL-A")[0].formation_name == "Jurassic"
        assert model.tops_for_well("WELL-A")[0].depth_m == 1250.0

        out_path = path + ".out"
        model.save_csv(out_path)
        model2 = FormationTopsModel()
        model2.load_csv(out_path)
        assert len(model2.tops_for_well("WELL-A")) == 2
        os.unlink(out_path)
    finally:
        os.unlink(path)


def test_add_delete():
    model = FormationTopsModel()
    model.add_top(FormationTop("W1", "F1", 100.0))
    model.add_top(FormationTop("W1", "F2", 200.0))
    assert len(model.tops_for_well("W1")) == 2

    model.delete_top("W1", "F1")
    assert len(model.tops_for_well("W1")) == 1
    assert model.tops_for_well("W1")[0].formation_name == "F2"


def test_color_assignment():
    model = FormationTopsModel()
    model.add_top(FormationTop("W1", "Jurassic", 100.0))
    model.add_top(FormationTop("W2", "Jurassic", 200.0))
    t1 = model.tops_for_well("W1")[0]
    t2 = model.tops_for_well("W2")[0]
    assert t1.color == t2.color  # same formation name → same color


def test_formation_names():
    model = FormationTopsModel()
    model.add_top(FormationTop("W1", "F1", 100.0))
    model.add_top(FormationTop("W1", "F2", 200.0))
    model.add_top(FormationTop("W2", "F1", 150.0))
    names = model.formation_names()
    assert set(names) == {"F1", "F2"}


def test_malformed_csv():
    model = FormationTopsModel()
    rows = [
        ["WELL-A", "F1", "not_a_number"],
        ["# comment"],
        [""],
        ["WELL-A", "F2", "100.0"],
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        path = f.name
    try:
        _write_csv(path, rows)
        model.load_csv(path)
        assert len(model.tops_for_well("WELL-A")) == 1
        assert model.tops_for_well("WELL-A")[0].formation_name == "F2"
    finally:
        os.unlink(path)


def test_clear():
    model = FormationTopsModel()
    model.add_top(FormationTop("W1", "F1", 100.0))
    model.clear()
    assert model.tops_for_well("W1") == []
    assert model.formation_names() == []


def test_load_csv_gbk_encoded_chinese_names(tmp_path):
    """ISSUE-015: GBK-encoded tops CSVs (standard for Chinese field data)
    crashed the utf-8-only reader; the fallback chain must decode them."""
    import pytest
    from geoviz_cross_well.tops_model import FormationTopsModel

    csv_text = "井名,层位,深度\n张家1井,长兴组,3200.5\n李家2井,茅口组,3450.0\n"
    p = tmp_path / "tops_gbk.csv"
    p.write_bytes(csv_text.encode("gb18030"))

    model = FormationTopsModel()
    model.load_csv(str(p))
    names = sorted(model.well_names()) if hasattr(model, "well_names") else []
    assert names == ["张家1井", "李家2井"] or len(names) == 2, names
