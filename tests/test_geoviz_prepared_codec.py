# geo-viz-engine/tests/test_geoviz_prepared_codec.py
from __future__ import annotations

import numpy as np
import pytest

from geoviz import (
    PreparedPreview,
    PreviewKind,
    decode_prepared_preview,
    encode_prepared_preview,
)
from geoviz.previews.dat import SurfacePreviewPayload, XYPreviewPayload
from geoviz_cross_well import FormationTop


def test_roundtrip_xy_scatter():
    payload = XYPreviewPayload(
        names=("A1", "B2"),
        x=np.array([1.0, 2.0]),
        y=np.array([3.0, 4.0]),
    )
    prepared = PreparedPreview(
        kind=PreviewKind.XY_SCATTER,
        title="wells",
        payload=payload,
        summary_rows=(("井数", "2"),),
        estimated_bytes=64,
    )
    meta, arrays = encode_prepared_preview(prepared)
    restored = decode_prepared_preview(meta, arrays)
    assert restored.kind is PreviewKind.XY_SCATTER
    assert restored.title == "wells"
    assert restored.summary_rows == (("井数", "2"),)
    assert list(restored.payload.names) == ["A1", "B2"]
    np.testing.assert_array_equal(restored.payload.x, payload.x)
    np.testing.assert_array_equal(restored.payload.y, payload.y)


def test_roundtrip_surface():
    payload = SurfacePreviewPayload(
        grid_x=np.array([0.0, 1.0]),
        grid_y=np.array([0.0, 1.0]),
        grid_z=np.array([[1.0, 2.0], [3.0, 4.0]]),
        levels=(1.5, 2.5),
    )
    prepared = PreparedPreview(
        kind=PreviewKind.SURFACE,
        title="hz",
        payload=payload,
        estimated_bytes=128,
    )
    restored = decode_prepared_preview(*encode_prepared_preview(prepared))
    np.testing.assert_array_equal(restored.payload.grid_z, payload.grid_z)
    assert restored.payload.levels == (1.5, 2.5)


def test_roundtrip_formation_tops():
    tops = (
        FormationTop("W1", "A", 100.0, color="#111111"),
        FormationTop("W2", "A", 110.0, color="#111111"),
    )
    prepared = PreparedPreview(
        kind=PreviewKind.FORMATION_TOPS,
        title="tops",
        payload=tops,
        estimated_bytes=32,
    )
    restored = decode_prepared_preview(*encode_prepared_preview(prepared))
    assert len(restored.payload) == 2
    assert restored.payload[0].well_name == "W1"
    assert restored.payload[0].depth_m == 100.0


def test_rejects_well_log_kind():
    with pytest.raises(ValueError):
        encode_prepared_preview(
            PreparedPreview(kind=PreviewKind.WELL_LOG, title="x", payload=object())
        )
