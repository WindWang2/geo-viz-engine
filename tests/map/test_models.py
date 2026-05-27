import pytest

from geoviz_map.models import ReferenceLabel, WellMarker


def test_well_marker_holds_name_color_data_flag():
    m = WellMarker(name="HZ19-1", lng=114.5, lat=20.1, color="#ef4444", has_data=True)
    assert m.name == "HZ19-1"
    assert m.lng == 114.5
    assert m.lat == 20.1
    assert m.color == "#ef4444"
    assert m.has_data is True


def test_well_marker_has_data_defaults_false():
    m = WellMarker(name="X", lng=100.0, lat=20.0, color="#000000")
    assert m.has_data is False


def test_reference_label_kind_must_be_city_or_capital_or_sea():
    ReferenceLabel(name="北京", lng=116.4, lat=39.9, kind="capital")
    ReferenceLabel(name="上海", lng=121.5, lat=31.2, kind="city")
    ReferenceLabel(name="南海", lng=115.5, lat=20.2, kind="sea")
    with pytest.raises(ValueError):
        ReferenceLabel(name="X", lng=0, lat=0, kind="invalid")
