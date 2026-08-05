"""Free-graphics record contract tests — pure Python, no Qt (spec §3.5).

``records.py`` is the frozen cross-repo contract. It must stay importable
without PySide6, so this test loads it by file path instead of through the
package ``__init__`` chain (which imports Qt modules).
"""

import importlib.util
from pathlib import Path

_RECORDS_PATH = (
    Path(__file__).resolve().parents[2]
    / "packages/geoviz_paleo_map/geoviz_paleo_map/cartography/items/free/records.py"
)

_spec = importlib.util.spec_from_file_location("free_records", _RECORDS_PATH)
records = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(records)


def test_parse_minimal_text_record_applies_defaults():
    rec = records.parse_record(
        {"kind": "text", "geometry": {"x": 20.0, "y": 15.0}, "props": {"text": "Hi"}}
    )
    assert rec is not None
    assert rec["kind"] == "text"
    assert rec["style"] == {
        "stroke": "#000000", "fill": None, "width_mm": 0.3, "font_mm": 3.5,
    }
    assert rec["geometry"] == {"x": 20.0, "y": 15.0}
    assert rec["props"] == {"text": "Hi", "align": "left"}
    assert isinstance(rec["id"], str) and rec["id"]


def test_parse_preserves_id_and_full_style():
    rec = records.parse_record(
        {
            "id": "fixed-id",
            "kind": "rect",
            "style": {"stroke": "#FF0000", "fill": "#00ff00", "width_mm": 0.5, "font_mm": 4.0},
            "geometry": {"x": 10.0, "y": 10.0, "w": 40.0, "h": 20.0},
        }
    )
    assert rec["id"] == "fixed-id"
    assert rec["style"]["stroke"] == "#ff0000"  # hex normalised to lowercase
    assert rec["style"]["fill"] == "#00ff00"


def test_unknown_kind_rejected():
    assert records.parse_record({"kind": "blob", "geometry": {"x": 1, "y": 2}}) is None
    assert records.parse_record("not-a-dict") is None
    assert records.parse_record({"geometry": {"x": 1, "y": 2}}) is None


def test_bad_style_rejected():
    base = {"kind": "rect", "geometry": {"x": 1.0, "y": 1.0, "w": 2.0, "h": 2.0}}
    assert records.parse_record({**base, "style": {"stroke": "red"}}) is None
    assert records.parse_record({**base, "style": {"fill": "#xyzxyz"}}) is None
    assert records.parse_record({**base, "style": {"width_mm": -1}}) is None
    assert records.parse_record({**base, "style": {"width_mm": float("nan")}}) is None


def test_geometry_rules_per_kind():
    # box kinds need positive w/h
    assert records.parse_record(
        {"kind": "ellipse", "geometry": {"x": 1.0, "y": 1.0, "w": 0.0, "h": 2.0}}
    ) is None
    # polygon needs >= 3 points
    assert records.parse_record(
        {"kind": "polygon", "geometry": {"points": [[0.0, 0.0], [4.0, 0.0]]}}
    ) is None
    # arrow/freehand need >= 2 points
    assert records.parse_record(
        {"kind": "arrow", "geometry": {"points": [[0.0, 0.0]]}}
    ) is None
    assert records.parse_record(
        {"kind": "freehand", "geometry": {"points": [[0.0, 0.0], [4.0, 4.0]]}}
    ) is not None
    # text accepts optional wrap width, rejects bad one
    ok = records.parse_record({"kind": "text", "geometry": {"x": 1.0, "y": 1.0, "w": 30.0}})
    assert ok["geometry"]["w"] == 30.0
    assert records.parse_record(
        {"kind": "text", "geometry": {"x": 1.0, "y": 1.0, "w": -3.0}}
    ) is None


def test_props_rules_per_kind():
    # image requires a non-empty path
    assert records.parse_record(
        {"kind": "image", "geometry": {"x": 1.0, "y": 1.0, "w": 2.0, "h": 2.0}}
    ) is None
    ok = records.parse_record(
        {"kind": "image", "geometry": {"x": 1.0, "y": 1.0, "w": 2.0, "h": 2.0},
         "props": {"path": "plots/assets/p/a.png"}}
    )
    assert ok["props"] == {"path": "plots/assets/p/a.png"}
    # scale_bar denominator coerced to int, default 5000
    ok = records.parse_record(
        {"kind": "scale_bar", "geometry": {"x": 1.0, "y": 1.0, "w": 50.0, "h": 9.0}}
    )
    assert ok["props"] == {"denominator": 5000}
    assert records.parse_record(
        {"kind": "scale_bar", "geometry": {"x": 1.0, "y": 1.0, "w": 50.0, "h": 9.0},
         "props": {"denominator": -5}}
    ) is None
    # arrow head default 3.0; text align validated
    ok = records.parse_record({"kind": "arrow", "geometry": {"points": [[0.0, 0.0], [4.0, 0.0]]}})
    assert ok["props"] == {"head_mm": 3.0}
    assert records.parse_record(
        {"kind": "text", "geometry": {"x": 1.0, "y": 1.0}, "props": {"align": "justify"}}
    ) is None


def test_is_hex_colour():
    assert records.is_hex_colour("#a1B2c3")
    assert not records.is_hex_colour("a1b2c3")
    assert not records.is_hex_colour("#a1b2")
    assert not records.is_hex_colour(None)
