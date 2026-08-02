# geo-viz-engine/tests/test_geoviz_prepared_codec.py
from __future__ import annotations

import numpy as np
import pytest

from geoviz import (
    PreparedPreview,
    PreviewRowIssue,
    PreviewKind,
    XYPreviewDiagnostics,
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
        resource_id="resource-7",
        record_ids=(4, 9),
        source_rows=(12, 18),
        source_version="sha256:v1",
        source_crs="EPSG:32648",
        coordinate_units="m",
        diagnostics=XYPreviewDiagnostics(
            total_records=3,
            valid_records=2,
            issues=(PreviewRowIssue(15, "井名为空"),),
        ),
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
    assert restored.payload.resource_id == "resource-7"
    assert restored.payload.record_ids == (4, 9)
    assert restored.payload.source_rows == (12, 18)
    assert restored.payload.source_version == "sha256:v1"
    assert restored.payload.source_crs == "EPSG:32648"
    assert restored.payload.coordinate_units == "m"
    assert restored.payload.diagnostics == payload.diagnostics
    np.testing.assert_array_equal(restored.payload.x, payload.x)
    np.testing.assert_array_equal(restored.payload.y, payload.y)


def test_decode_keeps_compatible_identity_free_xy_payloads():
    prepared = PreparedPreview(
        kind=PreviewKind.XY_SCATTER,
        title="wells",
        payload=XYPreviewPayload(
            names=("A1",),
            x=np.array([1.0]),
            y=np.array([2.0]),
            source_crs="EPSG:32648",
            coordinate_units="m",
        ),
    )
    meta, arrays = encode_prepared_preview(prepared)
    for field in ("resource_id", "record_ids", "source_rows", "source_version"):
        meta.pop(field)

    restored = decode_prepared_preview(meta, arrays)

    assert restored.payload.resource_id == ""
    assert restored.payload.record_ids == ()
    assert restored.payload.source_rows == ()
    assert restored.payload.source_version == ""
    assert restored.payload.source_crs == "EPSG:32648"
    assert restored.payload.coordinate_units == "m"
    np.testing.assert_array_equal(restored.payload.x, np.array([1.0]))
    np.testing.assert_array_equal(restored.payload.y, np.array([2.0]))


def test_decode_rejects_partially_present_xy_identity():
    prepared = PreparedPreview(
        kind=PreviewKind.XY_SCATTER,
        title="wells",
        payload=XYPreviewPayload(
            names=("A1",),
            x=np.array([1.0]),
            y=np.array([2.0]),
        ),
    )
    meta, arrays = encode_prepared_preview(prepared)
    meta["resource_id"] = "resource-7"

    with pytest.raises(ValueError, match="identity metadata"):
        decode_prepared_preview(meta, arrays)


def test_encode_rejects_partially_present_xy_identity():
    prepared = PreparedPreview(
        kind=PreviewKind.XY_SCATTER,
        title="wells",
        payload=XYPreviewPayload(
            names=("A1",),
            x=np.array([1.0]),
            y=np.array([2.0]),
            resource_id="resource-7",
        ),
    )

    with pytest.raises(ValueError, match="identity metadata"):
        encode_prepared_preview(prepared)


@pytest.mark.parametrize(
    "shortened_field",
    ("names", "x", "y", "record_ids", "source_rows"),
)
def test_encode_rejects_mismatched_xy_parallel_lengths(shortened_field: str):
    names = ("A1",) if shortened_field == "names" else ("A1", "B2")
    x = np.array([1.0]) if shortened_field == "x" else np.array([1.0, 2.0])
    y = np.array([3.0]) if shortened_field == "y" else np.array([3.0, 4.0])
    record_ids = (4,) if shortened_field == "record_ids" else (4, 9)
    source_rows = (12,) if shortened_field == "source_rows" else (12, 18)
    prepared = PreparedPreview(
        kind=PreviewKind.XY_SCATTER,
        title="wells",
        payload=XYPreviewPayload(
            names=names,
            x=x,
            y=y,
            resource_id="resource-7",
            record_ids=record_ids,
            source_rows=source_rows,
            source_version="sha256:v1",
        ),
    )

    with pytest.raises(ValueError, match="parallel lengths"):
        encode_prepared_preview(prepared)


@pytest.mark.parametrize(
    "shortened_field",
    ("names", "x", "y", "record_ids", "source_rows"),
)
def test_decode_rejects_mismatched_xy_parallel_lengths(shortened_field: str):
    prepared = PreparedPreview(
        kind=PreviewKind.XY_SCATTER,
        title="wells",
        payload=XYPreviewPayload(
            names=("A1", "B2"),
            x=np.array([1.0, 2.0]),
            y=np.array([3.0, 4.0]),
            resource_id="resource-7",
            record_ids=(4, 9),
            source_rows=(12, 18),
            source_version="sha256:v1",
        ),
    )
    meta, arrays = encode_prepared_preview(prepared)
    if shortened_field in arrays:
        arrays[shortened_field] = arrays[shortened_field][:-1]
    else:
        meta[shortened_field] = meta[shortened_field][:-1]

    with pytest.raises(ValueError, match="parallel lengths"):
        decode_prepared_preview(meta, arrays)


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
