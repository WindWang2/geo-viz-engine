from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pytest

from geoviz import ErrorCode, GeoVizEngine, GeoVizError, PreviewKind, PreviewOptions, PreviewRequest
from geoviz_well_log import (
    WellLogCanvas,
    inspect_las_file,
    load_las_preview,
    read_sampled_ascii,
)


@pytest.fixture
def bounded_las(tmp_path: Path) -> Path:
    path = tmp_path / "bounded.las"
    curve_headers = [" DEPT.M : Depth"] + [
        f" C{index:02d}.UNIT{index:02d} : Curve {index:02d}"
        for index in range(1, 16)
    ]
    rows = []
    for row_index in range(5_001):
        values = [float(row_index + curve_index * 10_000) for curve_index in range(15)]
        if row_index == 3:
            values[0] = -99_999.0
        rows.append(
            " ".join(
                [f"{1_000.0 + row_index:.1f}"]
                + [f"{value:.1f}" for value in values]
            )
        )

    path.write_text(
        "\n".join(
            [
                "~VERSION INFORMATION",
                " VERS. 2.0 : CWLS LOG ASCII STANDARD",
                "~WELL INFORMATION",
                " WELL. BOUNDED-01 : WELL NAME",
                " NULL. -99999 : NULL VALUE",
                "~CURVE INFORMATION",
                *curve_headers,
                "~ASCII",
                *rows,
            ]
        ),
        encoding="utf-8",
    )
    return path


def _request(path: Path, *, semantic_type: str = "well_log", format: str = "las") -> PreviewRequest:
    return PreviewRequest("well-1", str(path), semantic_type, format, "Bounded well")


def test_load_las_preview_bounds_curves_and_depth_samples(bounded_las: Path):
    data = load_las_preview(str(bounded_las), max_curves=12, max_samples=2_000)

    assert data.well_name == "BOUNDED-01"
    assert len(data.curves) == 12
    assert len(data.curves[0].depth) <= 2_000
    assert {len(curve.depth) for curve in data.curves} == {len(data.curves[0].depth)}
    assert data.curves[0].depth[0] == 1_000.0
    assert data.curves[0].depth[-1] == 6_000.0
    assert data.top_depth == 1_000.0
    assert data.bottom_depth == 6_000.0


def test_load_las_preview_maps_null_and_derives_finite_display_range(bounded_las: Path):
    data = load_las_preview(str(bounded_las), max_curves=12, max_samples=2_000)
    curve = data.curves[0]
    values = np.asarray(curve.values)

    assert np.isnan(values[1])
    finite = values[np.isfinite(values)]
    assert curve.display_range == (float(finite.min()), float(finite.max()))


def test_read_sampled_ascii_keeps_unique_endpoints_at_minimum_capacity(bounded_las: Path):
    header = inspect_las_file(str(bounded_las))
    selected = header.non_depth_curves[:1]

    depth, values = read_sampled_ascii(
        str(bounded_las), header, selected, stride=1, max_samples=2
    )

    assert depth.tolist() == [1_000.0, 6_000.0]
    assert values[selected[0].index].shape == (2,)


def test_load_las_preview_rejects_capacity_that_cannot_keep_both_endpoints(bounded_las: Path):
    with pytest.raises(ValueError, match="at least two samples"):
        load_las_preview(str(bounded_las), max_samples=1)


@pytest.mark.parametrize(
    ("semantic_type", "format", "expected"),
    [
        ("well_log", "LAS", True),
        ("", "", True),
        ("unknown", ".las", True),
        ("seismic", "las", False),
        ("well_log", "txt", False),
    ],
)
def test_default_backend_supports_only_las_well_log_requests(
    tmp_path: Path, semantic_type: str, format: str, expected: bool
):
    engine = GeoVizEngine.default()
    request = _request(tmp_path / "sample.las", semantic_type=semantic_type, format=format)

    assert engine.supports(request) is expected


def test_backend_prepares_bounded_plain_payload_without_qt_objects(bounded_las: Path):
    engine = GeoVizEngine.default()
    options = PreviewOptions(max_curves=4, max_depth_samples=25)

    with ThreadPoolExecutor(max_workers=1) as executor:
        preview = executor.submit(engine.prepare, _request(bounded_las), options).result()

    assert preview.kind is PreviewKind.WELL_LOG
    assert preview.title == "Bounded well"
    assert len(preview.payload.curves) == 4
    assert len(preview.payload.curves[0].depth) <= 25
    assert preview.estimated_bytes > 0
    assert not isinstance(preview.payload, WellLogCanvas)


def test_backend_renders_and_releases_well_log_canvas(qtbot, bounded_las: Path):
    engine = GeoVizEngine.default()
    preview = engine.prepare(_request(bounded_las), PreviewOptions(max_curves=2, max_depth_samples=20))
    widget = engine.create_widget(preview.kind)
    qtbot.addWidget(widget)

    assert isinstance(widget, WellLogCanvas)
    engine.render(widget, preview)
    assert len(widget.tracks) == 3

    engine.release(widget)
    assert widget.tracks == []


def test_backend_maps_invalid_las_to_structured_error(tmp_path: Path):
    path = tmp_path / "invalid.las"
    path.write_text("~CURVE\nDEPT.M : Depth\n~ASCII\n1000\n", encoding="utf-8")

    with pytest.raises(GeoVizError) as caught:
        GeoVizEngine.default().prepare(_request(path), PreviewOptions.local())

    assert caught.value.code is ErrorCode.INVALID_DATA
    assert str(caught.value) == "无法解析 LAS 测井数据"


def test_backend_maps_os_error_to_structured_error(tmp_path: Path):
    path = tmp_path / "missing.las"

    with pytest.raises(GeoVizError) as caught:
        GeoVizEngine.default().prepare(_request(path), PreviewOptions.local())

    assert caught.value.code is ErrorCode.IO_ERROR
