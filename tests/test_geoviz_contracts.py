from pathlib import Path

import pytest

from geoviz import (
    ErrorCode,
    GeoVizError,
    PreparedPreview,
    PreviewKind,
    PreviewOptions,
    PreviewRequest,
)


def test_local_options_are_exact_and_immutable():
    options = PreviewOptions.local()
    assert options.max_curves == 12
    assert options.max_depth_samples == 2_000
    assert options.max_slice_axis == 512
    assert options.max_points == 50_000
    assert options.surface_grid_size == 256
    with pytest.raises(AttributeError):
        options.max_curves = 99


def test_request_normalizes_format_without_workbench_model(tmp_path: Path):
    request = PreviewRequest(
        resource_id="r1",
        path=str(tmp_path / "A1.Las"),
        semantic_type="well_log",
        format=".LAS",
        label="A1",
    )
    assert request.normalized_format == "las"


def test_prepared_preview_reports_memory_weight():
    preview = PreparedPreview(
        kind=PreviewKind.WELL_LOG,
        title="A1",
        payload={"rows": 2_000},
        estimated_bytes=32_000,
    )
    assert preview.estimated_bytes == 32_000


def test_structured_error_preserves_public_code():
    error = GeoVizError(ErrorCode.INVALID_DATA, "LAS 曲线为空", detail="no curves")
    assert error.code is ErrorCode.INVALID_DATA
    assert str(error) == "LAS 曲线为空"
    assert error.detail == "no curves"
