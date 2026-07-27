from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pytest

from geoviz import ErrorCode, GeoVizEngine, GeoVizError, PreviewKind, PreviewOptions, PreviewRequest
from geoviz.previews.dat import (
    _scan_dat,
    HorizonSurfaceBackend,
    SurfacePreviewPayload,
    TimeDepthPreviewPayload,
    XYPreviewPayload,
    representative_indices,
)
from geoviz_plots import LineSeries, PlotWidget, ScatterSeries, SurfaceWidget


def _request(
    path: Path,
    semantic_type: str,
    *,
    label: str = "",
    format: str = "dat",
) -> PreviewRequest:
    return PreviewRequest("dat-1", str(path), semantic_type, format, label)


@pytest.fixture
def well_head_dat(tmp_path: Path) -> Path:
    path = tmp_path / "well-head.dat"
    path.write_text(
        "\n".join(
            (
                "#WellHead File From SMI",
                "#Name X Y KB TotalDepth BottomX BottomY WellType",
                "Alpha 100.0 500.0 0 2000 100 500 0",
                "Beta  130.0 480.0 0 2100 130 480 0",
                "Gamma 125.0 525.0 0 2200 125 525 0",
            )
        ),
        encoding="utf-8-sig",
    )
    return path


@pytest.fixture
def horizon_dat(tmp_path: Path) -> Path:
    path = tmp_path / "horizon.dat"
    path.write_text(
        "\n".join(
            (
                "# XYZInlineCrossline Format Horizon File From SMI",
                "# Type: scattered data",
                "# Field: 1 x",
                "# Field: 2 y",
                "# Field: 3 z ms",
                "# Field: 4 Inline",
                "# Field: 5 Crossline",
                "0.0  0.0 1000.0 10 20",
                "10.0 0.0 1010.0 11 20",
                "0.0 10.0 1020.0 10 21",
                "10.0 10.0 1030.0 11 21",
            )
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def time_depth_dat(tmp_path: Path) -> Path:
    path = tmp_path / "time-depth.dat"
    path.write_text(
        "\n".join(
            (
                "#TimeDepth File From SMI",
                "# ====================================",
                "# TIME  .ms",
                "# TVDSS   .m",
                "# TVD   .m",
                "# MD   .m",
                "# TVD' .m",
                "# Well",
                "# Well : A1",
                "# KB : 0",
                "# Datum : 0.00",
                "#TIME TVDSS TVD MD TVD' Well",
                "850.0 -900.0 900.0 1000.0 900.0 A1",
                "420.0 -450.0 450.0 500.0 450.0 A1",
                "1250.0 -1400.0 1400.0 1500.0 1400.0 A1",
            )
        ),
        encoding="utf-8",
    )
    return path


def test_representative_indices_bounds_count_and_keeps_endpoints():
    assert representative_indices(3, 5).tolist() == [0, 1, 2]

    indices = representative_indices(100_001, 50_000)

    assert indices.dtype == np.int64
    assert len(indices) == 50_000
    assert indices[0] == 0
    assert indices[-1] == 100_000
    assert np.all(np.diff(indices) > 0)


def test_well_head_prepare_preserves_names_xy_extent_and_plain_numpy_payload(
    well_head_dat: Path,
):
    engine = GeoVizEngine.default()

    with ThreadPoolExecutor(max_workers=1) as executor:
        preview = executor.submit(
            engine.prepare,
            _request(well_head_dat, "well_head", label="Well locations"),
            PreviewOptions(max_points=2),
        ).result()

    assert preview.kind is PreviewKind.XY_SCATTER
    assert preview.title == "Well locations"
    assert isinstance(preview.payload, XYPreviewPayload)
    assert preview.payload.names == ("Alpha", "Beta", "Gamma")
    assert preview.payload.resource_id == "dat-1"
    assert preview.payload.record_ids == (0, 1, 2)
    assert preview.payload.x.tolist() == [100.0, 130.0, 125.0]
    assert preview.payload.y.tolist() == [500.0, 480.0, 525.0]
    assert preview.estimated_bytes >= (
        preview.payload.x.nbytes
        + preview.payload.y.nbytes
        + len(preview.payload.record_ids) * np.dtype(np.int64).itemsize
    )


def test_well_head_prepare_keeps_all_renderable_rows_and_reports_bad_rows(
    tmp_path: Path,
):
    path = tmp_path / "recoverable-wells.dat"
    path.write_text(
        "\n".join(
            (
                "#WellHead File From SMI",
                "#Name X Y",
                "A1 10 20",
                '\"\" 30 40',
                "A2 bad 50",
                "A3 60 70",
            )
        ),
        encoding="utf-8",
    )

    preview = GeoVizEngine.default().prepare(
        _request(path, "well_head"),
        PreviewOptions(max_points=1),
    )

    assert preview.payload.names == ("A1", "A3")
    assert preview.payload.record_ids == (0, 3)
    assert preview.payload.source_rows == (3, 6)
    assert preview.payload.x.tolist() == [10.0, 60.0]
    assert preview.payload.y.tolist() == [20.0, 70.0]
    diagnostics = preview.payload.diagnostics
    assert (
        diagnostics.total_records,
        diagnostics.valid_records,
        diagnostics.skipped_count,
        diagnostics.omitted_issue_count,
    ) == (4, 2, 2, 0)
    assert [
        (issue.source_row, issue.reason)
        for issue in diagnostics.issues
    ] == [
        (4, "井名为空"),
        (5, "X 坐标不是有限数值"),
    ]
    assert "2 行已跳过" in preview.warning


def test_well_head_prepare_treats_malformed_width_as_a_row_diagnostic(
    tmp_path: Path,
):
    path = tmp_path / "recoverable-width.dat"
    path.write_text(
        "\n".join(
            (
                "#WellHead File From SMI",
                "#Name X Y",
                "A1 10 20",
                "A2 30",
                "A3 40 50 extra",
                "A4 60 70",
            )
        ),
        encoding="utf-8",
    )

    preview = GeoVizEngine.default().prepare(
        _request(path, "well_head"),
        PreviewOptions.local(),
    )

    assert preview.payload.names == ("A1", "A4")
    assert preview.payload.source_rows == (3, 6)
    assert preview.payload.diagnostics.skipped_count == 2


def test_well_head_prepare_reads_file_crs_and_matching_xy_units(
    tmp_path: Path,
):
    path = tmp_path / "metadata.dat"
    path.write_text(
        "\n".join(
            (
                "#WellHead File From SMI",
                "#SourceCRS: EPSG:32648",
                "#X .m",
                "#Y .m",
                "#Name X Y",
                "A1 10 20",
            )
        ),
        encoding="utf-8",
    )

    preview = GeoVizEngine.default().prepare(
        _request(path, "well_head"),
        PreviewOptions.local(),
    )

    assert preview.payload.source_crs == "EPSG:32648"
    assert preview.payload.coordinate_units == "m"
    assert "SourceCRS 未声明" not in preview.warning
    assert "坐标单位未知" not in preview.warning


def test_well_head_prepare_blocks_conflicting_coordinate_metadata(
    tmp_path: Path,
):
    path = tmp_path / "conflicting-metadata.dat"
    path.write_text(
        "\n".join(
            (
                "#WellHead File From SMI",
                "#SourceCRS: EPSG:32648",
                "#X .m",
                "#Y .ft",
                "#Name X Y",
                "A1 10 20",
            )
        ),
        encoding="utf-8",
    )
    request = PreviewRequest(
        resource_id="asset-1",
        path=str(path),
        semantic_type="well_head",
        format="dat",
        source_crs="EPSG:4326",
    )

    with pytest.raises(GeoVizError) as caught:
        GeoVizEngine.default().prepare(request, PreviewOptions.local())

    assert caught.value.code is ErrorCode.INVALID_DATA
    assert "conflicting" in caught.value.detail


def test_well_head_prepare_reports_explicit_resource_limit(tmp_path: Path):
    path = tmp_path / "too-many-wells.dat"
    rows = "\n".join(
        f"A{index} {index} {index + 1}"
        for index in range(50_001)
    )
    path.write_text(
        "#WellHead File From SMI\n#Name X Y\n" + rows,
        encoding="utf-8",
    )

    with pytest.raises(GeoVizError) as caught:
        GeoVizEngine.default().prepare(
            _request(path, "well_head"),
            PreviewOptions.local(),
        )

    assert caught.value.code is ErrorCode.RESOURCE_LIMIT
    assert "50,000" in str(caught.value)


def test_well_head_prepare_preserves_explicit_source_metadata(
    well_head_dat: Path,
):
    request = PreviewRequest(
        resource_id="asset-1",
        path=str(well_head_dat),
        semantic_type="well_head",
        format="dat",
        source_version="sha256:abc",
        source_crs="EPSG:32648",
        coordinate_units="m",
        comparison_crs="EPSG:4326",
    )

    preview = GeoVizEngine.default().prepare(
        request,
        PreviewOptions.local(),
    )

    assert preview.payload.source_version == "sha256:abc"
    assert preview.payload.source_crs == "EPSG:32648"
    assert preview.payload.coordinate_units == "m"
    assert "EPSG:32648" in preview.warning
    assert "EPSG:4326" in preview.warning
    assert "未转换" in preview.warning


def test_horizon_prepare_builds_finite_bounded_surface_grid(horizon_dat: Path):
    preview = GeoVizEngine.default().prepare(
        _request(horizon_dat, "horizon", label="H1"),
        PreviewOptions(surface_grid_size=300),
    )

    assert preview.kind is PreviewKind.SURFACE
    assert isinstance(preview.payload, SurfacePreviewPayload)
    assert preview.payload.grid_x.ndim == 1
    assert preview.payload.grid_y.ndim == 1
    assert len(preview.payload.grid_x) <= 256
    assert len(preview.payload.grid_y) <= 256
    assert preview.payload.grid_z.shape == (
        len(preview.payload.grid_y),
        len(preview.payload.grid_x),
    )
    assert np.all(np.isfinite(preview.payload.grid_z))
    assert preview.payload.levels
    assert np.all(np.isfinite(preview.payload.levels))
    assert preview.estimated_bytes == (
        preview.payload.grid_x.nbytes
        + preview.payload.grid_y.nbytes
        + preview.payload.grid_z.nbytes
        + 8 * len(preview.payload.levels)
    )


def test_horizon_field_metadata_controls_reordered_xyz_columns(tmp_path: Path):
    path = tmp_path / "reordered-horizon.dat"
    path.write_text(
        "\n".join(
            (
                "# XYZInlineCrossline Format Horizon File From SMI",
                "# Field: 1 z ms",
                "# Field: 2 y",
                "# Field: 3 x",
                "1000 20 10",
                "1010 20 30",
                "1020 40 10",
            )
        ),
        encoding="utf-8",
    )

    preview = GeoVizEngine.default().prepare(
        _request(path, "horizon"), PreviewOptions(surface_grid_size=4)
    )

    assert preview.payload.grid_x[[0, -1]].tolist() == [10.0, 30.0]
    assert preview.payload.grid_y[[0, -1]].tolist() == [20.0, 40.0]


def test_time_depth_uses_registered_columns_and_sorts_by_depth(time_depth_dat: Path):
    preview = GeoVizEngine.default().prepare(
        _request(time_depth_dat, "time_depth"), PreviewOptions.local()
    )

    assert preview.kind is PreviewKind.TIME_DEPTH
    assert isinstance(preview.payload, TimeDepthPreviewPayload)
    assert preview.payload.depth.tolist() == [500.0, 1000.0, 1500.0]
    assert preview.payload.time_ms.tolist() == [420.0, 850.0, 1250.0]
    assert preview.estimated_bytes == (
        preview.payload.depth.nbytes + preview.payload.time_ms.nbytes
    )


def test_time_depth_rejects_bare_time_column_without_millisecond_registration(
    tmp_path: Path,
):
    path = tmp_path / "time-unit-unknown.dat"
    path.write_text("# Depth Time\n1000 850\n", encoding="utf-8")

    request = _request(path, "time_depth")

    assert not GeoVizEngine.default().supports(request)


def test_time_depth_rejects_prose_comment_as_a_column_declaration(tmp_path: Path):
    path = tmp_path / "prose-header.dat"
    path.write_text(
        "# TimeDepth File From SMI\n# Depth versus Time(ms)\n1000 9999 850\n",
        encoding="utf-8",
    )

    with pytest.raises(GeoVizError) as caught:
        GeoVizEngine.default().prepare(
            _request(path, "time_depth"), PreviewOptions.local()
        )

    assert caught.value.code is ErrorCode.INVALID_DATA
    assert str(caught.value) == "DAT 数据结构与资源类型不匹配"


@pytest.mark.parametrize(
    ("semantic_type", "text"),
    [
        (
            "well_head",
            "#WellHead File From SMI\n# KB X Y\n0 1 2\n0 2 3\n0 3 1\n",
        ),
        (
            "well_head",
            "#WellHead File From SMI\n# 1 2 3\nA 1 2\nB 2 3\nC 3 1\n",
        ),
        (
            "horizon",
            "# XYZInlineCrossline Format Horizon File From SMI\n0 0 1\n1 0 2\n0 1 3\n",
        ),
        (
            "horizon",
            "# XYZInlineCrossline Format Horizon File From SMI\n"
            "# Field: 1 x\n# Field: 2 y\n0 0 1\n1 0 2\n0 1 3\n",
        ),
    ],
)
def test_smi_marker_without_reliable_required_columns_is_invalid(
    tmp_path: Path, semantic_type: str, text: str
):
    path = tmp_path / f"missing-columns-{semantic_type}.dat"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(GeoVizError) as caught:
        GeoVizEngine.default().prepare(
            _request(path, semantic_type), PreviewOptions.local()
        )

    assert caught.value.code is ErrorCode.INVALID_DATA
    assert str(caught.value) == "DAT 数据结构与资源类型不匹配"


@pytest.mark.parametrize(
    "rows",
    [
        ("0 0 1000", "1 1 1010"),
        ("0 0 1000", "0 0 1010", "1 1 1020", "1 1 1030"),
        ("0 0 1000", "0 1 1010", "0 2 1020"),
        ("0 0 1000", "1 1 1010", "2 2 1020"),
    ],
)
def test_horizon_rejects_insufficient_or_degenerate_spatial_geometry(
    tmp_path: Path, rows: tuple[str, ...]
):
    path = tmp_path / "degenerate-horizon.dat"
    path.write_text(
        "\n".join(
            (
                "# XYZInlineCrossline Format Horizon File From SMI",
                "# Field: 1 x",
                "# Field: 2 y",
                "# Field: 3 z ms",
                *rows,
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(GeoVizError) as caught:
        GeoVizEngine.default().prepare(
            _request(path, "horizon"), PreviewOptions.local()
        )

    assert caught.value.code is ErrorCode.INVALID_DATA
    assert str(caught.value) == "DAT 数据结构与资源类型不匹配"


def test_horizon_constant_z_plane_has_strictly_increasing_levels(tmp_path: Path):
    path = tmp_path / "constant-z.dat"
    path.write_text(
        "\n".join(
            (
                "# XYZInlineCrossline Format Horizon File From SMI",
                "# Field: 1 x",
                "# Field: 2 y",
                "# Field: 3 z ms",
                "0 0 1000",
                "10 0 1000",
                "0 10 1000",
                "10 10 1000",
            )
        ),
        encoding="utf-8",
    )

    preview = GeoVizEngine.default().prepare(
        _request(path, "horizon"), PreviewOptions(surface_grid_size=4)
    )

    assert np.allclose(preview.payload.grid_z, 1000.0)
    assert np.all(np.diff(preview.payload.levels) > 0.0)
    assert preview.payload.levels[0] < 1000.0 < preview.payload.levels[-1]


def test_comment_heavy_dat_retains_only_bounded_header_metadata(tmp_path: Path):
    path = tmp_path / "comment-heavy.dat"
    path.write_text(
        "\n".join(
            (
                "#WellHead File From SMI",
                "# Name X Y",
                *(f"# ignored metadata {index}" for index in range(2_000)),
                "A 0 0",
                "B 1 0",
                "C 0 1",
            )
        ),
        encoding="utf-8",
    )

    header, row_count, _ = _scan_dat(str(path))
    preview = GeoVizEngine.default().prepare(
        _request(path, "well_head"), PreviewOptions.local()
    )

    assert len(header) <= 256
    assert sum(len(line) for line in header) <= 64 * 1_024
    assert row_count == 3
    assert preview.payload.names == ("A", "B", "C")


@pytest.mark.parametrize("semantic_type", ["", "unknown", "tabular"])
def test_arbitrary_three_column_dat_is_not_guessed(tmp_path: Path, semantic_type: str):
    path = tmp_path / "arbitrary.dat"
    path.write_text("A B C\n1 2 3\n4 5 6\n", encoding="utf-8")

    engine = GeoVizEngine.default()
    request = _request(path, semantic_type)

    assert not engine.supports(request)
    with pytest.raises(GeoVizError) as caught:
        engine.prepare(request, PreviewOptions.local())
    assert caught.value.code is ErrorCode.UNSUPPORTED


@pytest.mark.parametrize(
    ("semantic_type", "text"),
    [
        ("well_head", "#WellHead File From SMI\n# Name X Y\nA 1\n"),
        (
            "horizon",
            "# XYZInlineCrossline Format Horizon File From SMI\n# X Y Z\n1 2 bad\n",
        ),
        ("time_depth", "# Depth Time(ms)\n100 bad\n"),
    ],
)
def test_declared_semantic_type_with_bad_schema_maps_exact_invalid_data(
    tmp_path: Path, semantic_type: str, text: str
):
    path = tmp_path / f"bad-{semantic_type}.dat"
    path.write_text(text, encoding="utf-8-sig")

    with pytest.raises(GeoVizError) as caught:
        GeoVizEngine.default().prepare(
            _request(path, semantic_type), PreviewOptions.local()
        )

    assert caught.value.code is ErrorCode.INVALID_DATA
    assert str(caught.value) == "DAT 数据结构与资源类型不匹配"


@pytest.mark.parametrize(
    ("semantic_type", "marker"),
    [
        ("well_head", "#WellHead File From SMI"),
        ("horizon", "# XYZInlineCrossline Format Horizon File From SMI"),
        ("time_depth", "# TimeDepth File From SMI"),
    ],
)
def test_malformed_quoted_header_maps_exact_invalid_data(
    tmp_path: Path, semantic_type: str, marker: str
):
    path = tmp_path / f"quoted-{semantic_type}.dat"
    path.write_text(f'{marker}\n# "Depth Time(ms)\n1 2 3\n', encoding="utf-8-sig")

    with pytest.raises(GeoVizError) as caught:
        GeoVizEngine.default().prepare(
            _request(path, semantic_type), PreviewOptions.local()
        )

    assert caught.value.code is ErrorCode.INVALID_DATA
    assert str(caught.value) == "DAT 数据结构与资源类型不匹配"


def test_malformed_unrecognized_time_depth_header_is_safe_to_probe(tmp_path: Path):
    path = tmp_path / "malformed-unrecognized.dat"
    path.write_text('# "Depth Time(ms)\n1 2\n', encoding="utf-8")

    assert not GeoVizEngine.default().supports(_request(path, "time_depth"))


def test_well_head_render_adds_one_scatter_series_and_release_clears(
    qtbot, well_head_dat: Path
):
    engine = GeoVizEngine.default()
    preview = engine.prepare(
        _request(well_head_dat, "well_head"), PreviewOptions.local()
    )
    widget = engine.create_widget(preview.kind)
    qtbot.addWidget(widget)

    assert isinstance(widget, PlotWidget)
    engine.render(widget, preview)
    assert len(widget.series_list) == 1
    assert isinstance(widget.series_list[0], ScatterSeries)
    assert widget.view_xmin < 100.0 < widget.view_xmax
    assert widget.view_ymin < 480.0 < widget.view_ymax
    assert widget._kdtree is not None
    assert len(widget._tree_metadata) == 3
    assert widget.axis_labels() == ("X", "Y")

    engine.release(widget)
    assert widget.series_list == []
    assert widget._kdtree is None
    assert widget._tree_metadata == []


def test_time_depth_render_uses_time_x_depth_y_and_release_clears(
    qtbot, time_depth_dat: Path
):
    engine = GeoVizEngine.default()
    preview = engine.prepare(
        _request(time_depth_dat, "time_depth"), PreviewOptions.local()
    )
    widget = engine.create_widget(preview.kind)
    qtbot.addWidget(widget)

    engine.render(widget, preview)
    assert isinstance(widget, PlotWidget)
    assert len(widget.series_list) == 1
    series = widget.series_list[0]
    assert isinstance(series, LineSeries)
    assert series.x.tolist() == preview.payload.time_ms.tolist()
    assert series.y.tolist() == preview.payload.depth.tolist()

    engine.release(widget)
    assert widget.series_list == []


def test_horizon_render_uses_surface_public_api_and_release_resets_state(
    qtbot, horizon_dat: Path, monkeypatch
):
    engine = GeoVizEngine.default()
    preview = engine.prepare(
        _request(horizon_dat, "horizon"), PreviewOptions(surface_grid_size=8)
    )
    widget = engine.create_widget(preview.kind)
    qtbot.addWidget(widget)
    calls = []
    original_clear = SurfaceWidget.clear

    def tracking_clear(surface):
        calls.append(surface)
        original_clear(surface)

    monkeypatch.setattr(SurfaceWidget, "clear", tracking_clear)

    assert isinstance(widget, SurfaceWidget)
    engine.render(widget, preview)
    assert np.array_equal(widget.grid_x, preview.payload.grid_x)
    assert np.array_equal(widget.grid_y, preview.payload.grid_y)
    assert np.array_equal(widget.grid_z, preview.payload.grid_z)
    assert widget.levels == sorted(preview.payload.levels)
    widget.set_control_points([{"id": "cp", "x": 1.0, "y": 2.0, "z": 3.0}])
    widget.set_fault_polylines([[(0.0, 0.0), (1.0, 1.0)]])
    widget.select_contour_level(widget.levels[0])
    widget.view_ymin, widget.view_ymax = -5.0, 25.0

    engine.release(widget)
    assert calls == [widget]
    assert widget.grid_x is None
    assert widget.grid_y is None
    assert widget.grid_z is None
    assert widget.levels == []
    assert widget.control_points == []
    assert widget.fault_polylines == []
    assert widget.selected_contour_level is None
    assert widget.view_xmin == 0.0
    assert widget.view_xmax == 1.0
    assert widget.view_ymin == 0.0
    assert widget.view_ymax == 1.0


def test_horizon_backend_rejects_wrong_widget_or_payload(qtbot):
    backend = HorizonSurfaceBackend()
    widget = PlotWidget()
    qtbot.addWidget(widget)

    with pytest.raises(GeoVizError) as caught:
        backend.release(widget)

    assert caught.value.code is ErrorCode.RENDER_ERROR
