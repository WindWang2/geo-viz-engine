from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent

from geoviz import ErrorCode, GeoVizEngine, GeoVizError, PreviewKind, PreviewOptions, PreviewRequest
from geoviz_well_log import (
    WellLogCanvas,
    WellLogView,
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


@pytest.fixture
def damaged_binary_las(tmp_path: Path) -> Path:
    path = tmp_path / "damaged-binary.las"
    path.write_bytes(
        b"~vErSiOn InFoRmAtIoN\n"
        b"  vErS  .  2.0 : standard\n"
        b"~wElL InFoRmAtIoN\n"
        b"  wElL  .   BYTE-WELL   : well name\n"
        b"  nUlL  .   -99999      : null value\n"
        b"~cUrVe InFoRmAtIoN\n"
        b"  dEpTh   .   M    : depth\n"
        b"  gR      .   API  : gamma ray\n"
        b"  allnull .   V/V  : empty curve\n"
        b"~aScIi\n"
        b"1000 10 -99999\n"
        b"10\xff01 11 -99999\n"
        b"1002 12\xff0 -99999\n"
        b"1003 13\n"
        b"NOPE 14 -99999\n"
        b"1005 15 -99999\n"
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


def test_invalid_bytes_in_depth_reject_row_consistently_in_both_passes(
    damaged_binary_las: Path,
):
    header = inspect_las_file(str(damaged_binary_las))

    depth, _ = read_sampled_ascii(
        str(damaged_binary_las), header, (), stride=1, max_samples=header.row_count
    )

    assert header.row_count == 3
    assert depth.tolist() == [1_000.0, 1_002.0, 1_005.0]
    assert depth.size == header.row_count


def test_invalid_bytes_in_selected_curve_become_nan_without_dropping_row(
    damaged_binary_las: Path,
):
    data = load_las_preview(str(damaged_binary_las), max_samples=10)

    assert data.curves[0].depth == [1_000.0, 1_002.0, 1_005.0]
    assert data.curves[0].values[0] == 10.0
    assert np.isnan(data.curves[0].values[1])
    assert data.curves[0].values[2] == 15.0
    assert data.curves[0].display_range == (10.0, 15.0)


def test_mixed_case_headers_bad_rows_and_all_null_curve_fallback(
    damaged_binary_las: Path,
):
    data = load_las_preview(str(damaged_binary_las), max_samples=10)

    assert data.well_name == "BYTE-WELL"
    assert [(curve.name, curve.unit) for curve in data.curves] == [
        ("gR", "API"),
        ("allnull", "V/V"),
    ]
    assert all(np.isnan(value) for value in data.curves[1].values)
    assert data.curves[1].display_range == (0.0, 100.0)


@pytest.mark.parametrize(
    ("delimiter_name", "separator"),
    [("COMMA", ","), ("TAB", "\t")],
)
def test_inspection_and_preview_support_las_declared_delimiters(
    tmp_path: Path,
    delimiter_name: str,
    separator: str,
):
    path = tmp_path / f"delimited-{delimiter_name.lower()}.las"
    path.write_text(
        "\n".join(
            [
                "~VERSION INFORMATION",
                " VERS. 2.0 : standard",
                " WRAP. NO : one row per line",
                f" DLM. {delimiter_name} : delimiter",
                "~WELL INFORMATION",
                " WELL. DLM-WELL : name",
                " NULL. -999.25 : null",
                "~CURVE INFORMATION",
                " DEPT.M : depth",
                " GR.API : gamma",
                " RHOB.G/C3 : density",
                "~ASCII",
                separator.join(("1000", "10", "2.4")),
                separator.join(("1001", "11", "2.5")),
            ]
        ),
        encoding="utf-8",
    )

    header = inspect_las_file(str(path))
    data = load_las_preview(str(path), max_samples=10)

    assert header.row_count == 2
    assert data.well_name == "DLM-WELL"
    assert data.curves[0].depth == [1000.0, 1001.0]
    assert data.curves[0].values == [10.0, 11.0]


def test_inspection_and_preview_support_wrapped_las_rows(tmp_path: Path):
    path = tmp_path / "wrapped.las"
    path.write_text(
        "\n".join(
            [
                "~VERSION INFORMATION",
                " VERS. 2.0 : standard",
                " WRAP. YES : rows continue on following lines",
                " DLM. SPACE : delimiter",
                "~WELL INFORMATION",
                " WELL. WRAPPED-WELL : name",
                " NULL. -999.25 : null",
                "~CURVE INFORMATION",
                " DEPT.M : depth",
                " GR.API : gamma",
                " RHOB.G/C3 : density",
                "~ASCII",
                "1000",
                "10 2.4",
                "1001",
                "11 2.5",
            ]
        ),
        encoding="utf-8",
    )

    header = inspect_las_file(str(path))
    data = load_las_preview(str(path), max_samples=10)

    assert header.row_count == 2
    assert data.well_name == "WRAPPED-WELL"
    assert data.curves[0].depth == [1000.0, 1001.0]
    assert data.curves[1].values == [2.4, 2.5]


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


def test_backend_renders_and_releases_interactive_well_log_view(qtbot, bounded_las: Path):
    engine = GeoVizEngine.default()
    preview = engine.prepare(_request(bounded_las), PreviewOptions(max_curves=2, max_depth_samples=20))
    widget = engine.create_widget(preview.kind)
    qtbot.addWidget(widget)

    assert isinstance(widget, WellLogView)
    engine.render(widget, preview)
    assert len(widget.canvas.tracks) == 3
    assert (widget._full_top, widget._full_bottom) == (1_000.0, 6_000.0)
    assert (widget._zoom_handler._full_top, widget._zoom_handler._full_bottom) == (
        1_000.0,
        6_000.0,
    )

    widget.resize(640, 480)
    before_zoom = widget.canvas.tracks[0].depth_span
    wheel_event = QWheelEvent(
        QPointF(120.0, 120.0),
        QPointF(120.0, 120.0),
        QPoint(),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    widget.wheelEvent(wheel_event)
    assert widget.canvas.tracks[0].depth_span < before_zoom
    assert widget.verticalScrollBar().maximum() > 0

    widget.set_depth_range(1_500.0, 5_500.0)
    widget.reset_view()
    assert (widget.canvas.tracks[0].depth_top, widget.canvas.tracks[0].depth_bottom) == (
        1_000.0,
        6_000.0,
    )

    engine.release(widget)
    assert widget.canvas.tracks == []


def test_backend_maps_invalid_las_to_structured_error(tmp_path: Path):
    path = tmp_path / "invalid.las"
    path.write_text("~CURVE\nDEPT.M : Depth\n~ASCII\n1000\n", encoding="utf-8")

    with pytest.raises(GeoVizError) as caught:
        GeoVizEngine.default().prepare(_request(path), PreviewOptions.local())

    assert caught.value.code is ErrorCode.INVALID_DATA
    assert str(caught.value) == "无法解析测井数据"


def test_backend_maps_os_error_to_structured_error(tmp_path: Path):
    path = tmp_path / "missing.las"

    with pytest.raises(GeoVizError) as caught:
        GeoVizEngine.default().prepare(_request(path), PreviewOptions.local())

    assert caught.value.code is ErrorCode.IO_ERROR


def test_las_parser_provider_hook_and_fast_path(bounded_las: Path, tmp_path: Path):
    from geoviz import get_las_parser_provider, set_las_parser_provider

    # Ensure clean hook state
    set_las_parser_provider(None)
    assert get_las_parser_provider() is None

    # 1. Fallback when no provider registered
    data_slow = load_las_preview(str(bounded_las), fast=False)
    data_no_provider = load_las_preview(str(bounded_las), fast=True)
    assert data_no_provider.well_name == data_slow.well_name
    assert len(data_no_provider.curves) == len(data_slow.curves)
    assert data_no_provider.top_depth == data_slow.top_depth

    # 2. Mock provider registration and parity check
    def fake_parser(content: str, null_value: float):
        lines = content.splitlines()
        ascii_idx = next(i for i, l in enumerate(lines) if l.strip().startswith("~A")) + 1
        rows = [[float(x) for x in l.split()] for l in lines[ascii_idx:] if l.strip() and not l.strip().startswith("#")]
        arr = np.array(rows, dtype=np.float64)
        return tuple(f"C{i}" for i in range(arr.shape[1])), arr

    try:
        set_las_parser_provider(fake_parser)
        assert get_las_parser_provider() is fake_parser

        data_fast = load_las_preview(str(bounded_las), fast=True)
        assert data_fast.well_name == data_slow.well_name
        assert len(data_fast.curves) == len(data_slow.curves)
        assert data_fast.top_depth == pytest.approx(data_slow.top_depth)
        assert data_fast.bottom_depth == pytest.approx(data_slow.bottom_depth)
        for c_fast, c_slow in zip(data_fast.curves, data_slow.curves):
            assert c_fast.name == c_slow.name
            assert c_fast.depth == pytest.approx(c_slow.depth)
            assert np.allclose(np.nan_to_num(c_fast.values), np.nan_to_num(c_slow.values), equal_nan=True)

        # 3. Wrapped LAS file falls back gracefully
        wrapped_las = tmp_path / "wrapped.las"
        wrapped_las.write_text(
            "~VERSION\n VERS. 2.0 :\n WRAP. YES :\n~WELL\n WELL. W-01 :\n NULL. -99999 :\n~CURVE\n DEPT.M :\n GR.API :\n~ASCII\n1000\n 10\n1001\n 11\n",
            encoding="utf-8",
        )
        data_wrapped = load_las_preview(str(wrapped_las), fast=True)
        assert data_wrapped.well_name == "W-01"
        assert len(data_wrapped.curves) == 1

        # 4. Malformed provider output falls back gracefully
        def bad_parser(content: str, null_value: float):
            return (), np.zeros((1, 1))

        set_las_parser_provider(bad_parser)
        data_malformed = load_las_preview(str(bounded_las), fast=True)
        assert data_malformed.well_name == data_slow.well_name
    finally:
        set_las_parser_provider(None)

