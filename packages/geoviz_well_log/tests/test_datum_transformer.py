from __future__ import annotations

from geoviz_well_log.section.datum_transformer import DatumTransformer


def test_datum_transformer_absolute_mode():
    dt = DatumTransformer(
        mode="absolute",
        scale_y=2.0,
        header_height=56.0,
        global_min_depth=100.0,
        global_max_depth=500.0,
    )

    # Depth 100m -> 56px
    y1 = dt.get_depth_y("W1", 100.0)
    assert abs(y1 - 56.0) < 1e-5

    # Depth 200m -> 56 + (200-100)*2 = 256px
    y2 = dt.get_depth_y("W1", 200.0)
    assert abs(y2 - 256.0) < 1e-5

    # Inverse
    assert abs(dt.inverse_y_to_depth("W1", 256.0) - 200.0) < 1e-5


def test_datum_transformer_datum_shift_mode():
    dt = DatumTransformer(
        mode="datum_shift",
        datum_name="C6",
        scale_y=1.5,
        y_datum=200.0,
        datum_depths={"W1": 3500.0, "W2": 3600.0},
    )

    # W1 at C6 (3500m) -> 200px
    y_w1_datum = dt.get_depth_y("W1", 3500.0)
    assert abs(y_w1_datum - 200.0) < 1e-5

    # W2 at C6 (3600m) -> 200px
    y_w2_datum = dt.get_depth_y("W2", 3600.0)
    assert abs(y_w2_datum - 200.0) < 1e-5

    # W1 10m below datum -> 200 + 10*1.5 = 215px
    y_w1_below = dt.get_depth_y("W1", 3510.0)
    assert abs(y_w1_below - 215.0) < 1e-5
