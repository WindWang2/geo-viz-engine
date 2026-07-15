from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QPixmap, QWheelEvent

from geoviz import (
    ErrorCode,
    GeoVizEngine,
    GeoVizError,
    PreviewKind,
    PreviewOptions,
    PreviewRequest,
)
from geoviz.previews.dat import WellStratificationBackend
from geoviz_cross_well import FormationTop, FormationTopsPreviewWidget


WELL_TOPS_HEADER = """\
#WellTops File From SMI
#WellName    Name         MD           X            Y            Z            TVD          Time(ms)
"""


@pytest.fixture
def well_tops_path(tmp_path: Path) -> Path:
    path = tmp_path / "tops.dat"
    path.write_text(
        WELL_TOPS_HEADER
        + "W1 A 1000 0 0 0 0 0\n"
        + "W1 B 1100 0 0 0 0 0\n"
        + "W1 broken bad-md 0 0 0 0 0\n"
        + "W1 C 1200 0 0 0 0 0\n"
        + "W2 A 1050 0 0 0 0 0\n"
        + "W2 B 1150 0 0 0 0 0\n"
        + "W2 C 1250 0 0 0 0 0\n",
        encoding="utf-8",
    )
    return path


def _request(
    path: Path, *, semantic_type: str = "well_stratification", format: str = "dat"
) -> PreviewRequest:
    return PreviewRequest("tops-1", str(path), semantic_type, format, "Formation tops")


def test_widget_derives_deterministic_rendering_state_and_reuses_formation_colors(qtbot):
    widget = FormationTopsPreviewWidget()
    qtbot.addWidget(widget)
    tops = (
        FormationTop("B-2", "Alpha", 1200.0),
        FormationTop("A-1", "Gamma", 1100.0),
        FormationTop("A-1", "Alpha", 1000.0),
        FormationTop("B-2", "Gamma", 1300.0),
    )

    widget.set_tops(tops)

    assert widget.tops == tops
    assert widget.well_names == ("A-1", "B-2")
    assert widget.full_depth_range == (1000.0, 1300.0)
    assert widget.view_depth_range == (1000.0, 1300.0)
    assert tops[0].color == tops[2].color
    assert tops[1].color == tops[3].color


def test_widget_clear_resets_all_preview_state(qtbot):
    widget = FormationTopsPreviewWidget()
    qtbot.addWidget(widget)
    widget.set_tops((FormationTop("A-1", "Alpha", 1000.0),))

    widget.clear()

    assert widget.tops == ()
    assert widget.well_names == ()
    assert widget.full_depth_range == (0.0, 1.0)
    assert widget.view_depth_range == (0.0, 1.0)


def _render(widget: FormationTopsPreviewWidget) -> None:
    widget.resize(500, 300)
    widget.render(QPixmap(widget.size()))


def _wheel(widget: FormationTopsPreviewWidget, y: float, delta: int) -> None:
    event = QWheelEvent(
        QPointF(250.0, y),
        QPointF(250.0, y),
        QPoint(),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    widget.wheelEvent(event)


def _mouse_event(
    event_type: QEvent.Type,
    position: QPointF,
    button: Qt.MouseButton,
    buttons: Qt.MouseButton,
) -> QMouseEvent:
    return QMouseEvent(
        event_type,
        position,
        position,
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )


def test_wheel_and_drag_are_clamped_to_full_depth_range(qtbot):
    widget = FormationTopsPreviewWidget()
    qtbot.addWidget(widget)
    widget.set_tops(
        (FormationTop("W1", "A", 1000.0), FormationTop("W2", "A", 1300.0))
    )
    _render(widget)

    _wheel(widget, 150.0, 120)
    assert widget.view_depth_range[1] - widget.view_depth_range[0] < 300.0

    press = _mouse_event(
        QEvent.Type.MouseButtonPress,
        QPointF(250.0, 150.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
    )
    move = _mouse_event(
        QEvent.Type.MouseMove,
        QPointF(250.0, 10_000.0),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
    )
    release = _mouse_event(
        QEvent.Type.MouseButtonRelease,
        QPointF(250.0, 10_000.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
    )
    widget.mousePressEvent(press)
    widget.mouseMoveEvent(move)
    widget.mouseReleaseEvent(release)
    assert widget.full_depth_range[0] <= widget.view_depth_range[0]
    assert widget.view_depth_range[1] <= widget.full_depth_range[1]

    for _ in range(8):
        _wheel(widget, 150.0, -120)
    assert widget.view_depth_range == widget.full_depth_range


def test_single_depth_interactions_keep_a_stable_zero_span(qtbot):
    widget = FormationTopsPreviewWidget()
    qtbot.addWidget(widget)
    widget.set_tops((FormationTop("W1", "A", 1000.0),))

    _wheel(widget, 150.0, 120)
    widget.mousePressEvent(
        _mouse_event(
            QEvent.Type.MouseButtonPress,
            QPointF(250.0, 150.0),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
        )
    )
    widget.mouseMoveEvent(
        _mouse_event(
            QEvent.Type.MouseMove,
            QPointF(250.0, 250.0),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
        )
    )

    assert widget.view_depth_range == (1000.0, 1000.0)


def test_hover_is_cleared_on_leave_data_replace_and_clear(qtbot):
    widget = FormationTopsPreviewWidget()
    qtbot.addWidget(widget)
    first = FormationTop("W1", "A", 1000.0)
    widget.set_tops((first, FormationTop("W2", "A", 1100.0)))
    _render(widget)
    emitted = []
    widget.hovered_top_changed.connect(lambda *payload: emitted.append(payload))

    point = widget._visible_top_points[0][1]
    widget.mouseMoveEvent(
        _mouse_event(
            QEvent.Type.MouseMove,
            point,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
        )
    )
    assert emitted[-1] == ("W1", "A", 1000.0)

    widget.leaveEvent(QEvent(QEvent.Type.Leave))
    assert emitted[-1][0:2] == ("", "")
    assert emitted[-1][2] != emitted[-1][2]

    _render(widget)
    point = widget._visible_top_points[0][1]
    widget.mouseMoveEvent(
        _mouse_event(
            QEvent.Type.MouseMove,
            point,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
        )
    )
    widget.set_tops((FormationTop("W3", "B", 1200.0),))
    assert emitted[-1][0:2] == ("", "")

    _render(widget)
    point = widget._visible_top_points[0][1]
    widget.mouseMoveEvent(
        _mouse_event(
            QEvent.Type.MouseMove,
            point,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
        )
    )
    widget.clear()
    assert emitted[-1][0:2] == ("", "")
    assert widget._drag_start_y is None
    assert widget._drag_start_range == (0.0, 1.0)
    assert widget.cursor().shape() is Qt.CursorShape.ArrowCursor


def test_set_tops_preindexes_connectors_and_paint_caches_visible_points(qtbot):
    widget = FormationTopsPreviewWidget()
    qtbot.addWidget(widget)
    tops = tuple(
        FormationTop(well, formation, depth + offset)
        for well, offset in (("W1", 0.0), ("W2", 25.0))
        for formation, depth in (("A", 1000.0), ("B", 1100.0), ("C", 1200.0))
    )

    widget.set_tops(tops)

    assert tuple(widget._tops_by_well) == ("W1", "W2")
    assert tuple(widget._tops_by_formation) == ("A", "B", "C")
    assert len(widget._connectors) == 3
    assert widget._visible_top_points == ()

    _render(widget)
    assert len(widget._visible_top_points) == len(tops)


def test_connector_cache_uses_first_duplicate_formation_per_well(qtbot):
    widget = FormationTopsPreviewWidget()
    qtbot.addWidget(widget)
    widget.set_tops(
        (
            FormationTop("W1", "A", 1000.0),
            FormationTop("W1", "A", 1005.0),
            FormationTop("W2", "A", 1100.0),
        )
    )

    assert len(widget._connectors) == 1
    _, left_top, right_top = widget._connectors[0]
    assert (left_top.depth_m, right_top.depth_m) == (1000.0, 1100.0)


def test_sparse_well_indexes_have_no_connectors(qtbot):
    widget = FormationTopsPreviewWidget()
    qtbot.addWidget(widget)
    tops = tuple(
        FormationTop(f"W{index:04d}", f"F{index:04d}", float(index))
        for index in range(1_000)
    )

    widget.set_tops(tops)

    assert len(widget._tops_by_well) == 1_000
    assert len(widget._tops_by_formation) == 1_000
    assert widget._connectors == ()


@pytest.mark.parametrize(
    ("semantic_type", "format", "expected"),
    [
        ("well_stratification", "dat", True),
        ("well_stratification", "txt", False),
        ("well_head", "dat", False),
    ],
)
def test_backend_supports_only_declared_well_tops_dat(
    well_tops_path: Path, semantic_type: str, format: str, expected: bool
):
    backend = WellStratificationBackend()

    assert (
        backend.supports(
            _request(well_tops_path, semantic_type=semantic_type, format=format)
        )
        is expected
    )


def test_backend_requires_exact_smi_marker_and_registered_columns(tmp_path: Path):
    backend = WellStratificationBackend()
    wrong_marker = tmp_path / "wrong-marker.dat"
    wrong_marker.write_text(
        "# WellTops File From SMI\n"
        "#WellName Name MD X Y Z TVD Time(ms)\n"
        "A-1 Alpha 1000 0 0 0 0 0\n",
        encoding="utf-8",
    )
    wrong_columns = tmp_path / "wrong-columns.dat"
    wrong_columns.write_text(
        "#WellTops File From SMI\n"
        "#WellName Formation Depth X Y Z TVD Time(ms)\n"
        "A-1 Alpha 1000 0 0 0 0 0\n",
        encoding="utf-8",
    )

    assert not backend.supports(_request(wrong_marker))
    assert not backend.supports(_request(wrong_columns))


def test_backend_prepares_immutable_tops_and_ignores_bad_md(well_tops_path: Path):
    backend = WellStratificationBackend()

    preview = backend.prepare(_request(well_tops_path), PreviewOptions.local())

    assert preview.kind is PreviewKind.FORMATION_TOPS
    assert preview.payload == (
        FormationTop("W1", "A", 1000.0),
        FormationTop("W1", "B", 1100.0),
        FormationTop("W1", "C", 1200.0),
        FormationTop("W2", "A", 1050.0),
        FormationTop("W2", "B", 1150.0),
        FormationTop("W2", "C", 1250.0),
    )
    assert preview.summary_rows == (("层位点", "6"), ("井数", "2"))
    assert preview.estimated_bytes == sum(
        len(top.well_name.encode("utf-8"))
        + len(top.formation_name.encode("utf-8"))
        + len(top.color.encode("utf-8"))
        + 8
        for top in preview.payload
    )
    with pytest.raises(FrozenInstanceError):
        preview.payload[0].depth_m = 0.0


def test_backend_reports_exact_invalid_data_when_no_md_row_is_valid(tmp_path: Path):
    path = tmp_path / "invalid.dat"
    path.write_text(
        WELL_TOPS_HEADER
        + "A-1 Alpha missing 0 0 0 0 0\n"
        + "B-2 Beta nan 0 0 0 0 0\n",
        encoding="utf-8",
    )

    with pytest.raises(GeoVizError) as caught:
        WellStratificationBackend().prepare(_request(path), PreviewOptions.local())

    assert caught.value.code is ErrorCode.INVALID_DATA


def test_backend_caps_tops_at_50k_representative_rows(tmp_path: Path):
    path = tmp_path / "large.dat"
    path.write_text(
        WELL_TOPS_HEADER
        + "".join(
            f"W-{index % 3} F-{index % 7} {index} 0 0 0 0 0\n"
            for index in range(50_005)
        ),
        encoding="utf-8",
    )

    preview = WellStratificationBackend().prepare(
        _request(path), PreviewOptions(max_points=100_000)
    )

    assert len(preview.payload) == 50_000
    assert preview.payload[0].depth_m == 0.0
    assert preview.payload[-1].depth_m == 50_004.0


def test_low_limit_preserves_a_connector_for_grouped_well_rows(well_tops_path: Path):
    preview = WellStratificationBackend().prepare(
        _request(well_tops_path), PreviewOptions(max_points=2)
    )

    assert len(preview.payload) == 2
    assert {top.well_name for top in preview.payload} == {"W1", "W2"}
    assert len({top.formation_name for top in preview.payload}) == 1


def test_limit_one_has_deterministic_representative_without_promising_topology(
    well_tops_path: Path,
):
    preview = WellStratificationBackend().prepare(
        _request(well_tops_path), PreviewOptions(max_points=1)
    )

    assert preview.payload == (FormationTop("W1", "A", 1000.0),)


def test_topology_sampling_extends_a_chain_across_three_wells(
    tmp_path: Path,
):
    path = tmp_path / "three-wells.dat"
    path.write_text(
        WELL_TOPS_HEADER
        + "".join(
            f"{well} {formation} {base_depth + offset} 0 0 0 0 0\n"
            for well, offset in (("W1", 0), ("W2", 10), ("W3", 20))
            for formation, base_depth in (("A", 1000), ("B", 1100), ("C", 1200))
        ),
        encoding="utf-8",
    )

    preview = WellStratificationBackend().prepare(
        _request(path), PreviewOptions(max_points=4)
    )
    selected = {(top.well_name, top.formation_name) for top in preview.payload}

    assert len(preview.payload) == 4
    assert {("W1", "A"), ("W2", "A")} <= selected
    assert {("W2", "A"), ("W3", "A")} <= selected


def test_topology_sampling_covers_all_pairs_in_a_four_well_chain(tmp_path: Path):
    path = tmp_path / "four-wells.dat"
    path.write_text(
        WELL_TOPS_HEADER
        + "".join(
            f"{well} {formation} {base_depth + offset} 0 0 0 0 0\n"
            for well, offset in (
                ("W1", 0),
                ("W2", 10),
                ("W3", 20),
                ("W4", 30),
            )
            for formation, base_depth in (("A", 1000), ("B", 1100), ("C", 1200))
        ),
        encoding="utf-8",
    )

    preview = WellStratificationBackend().prepare(
        _request(path), PreviewOptions(max_points=4)
    )

    assert len(preview.payload) == 4
    assert {(top.well_name, top.formation_name) for top in preview.payload} == {
        ("W1", "A"),
        ("W2", "A"),
        ("W3", "A"),
        ("W4", "A"),
    }


@pytest.mark.parametrize(("limit", "expected_connectors"), [(3, 1), (4, 2)])
def test_topology_sampling_handles_disconnected_chains_and_insufficient_budget(
    tmp_path: Path, limit: int, expected_connectors: int
):
    path = tmp_path / f"disconnected-{limit}.dat"
    path.write_text(
        WELL_TOPS_HEADER
        + "W1 A 1000 0 0 0 0 0\n"
        + "W2 A 1010 0 0 0 0 0\n"
        + "W3 B 1020 0 0 0 0 0\n"
        + "W4 B 1030 0 0 0 0 0\n",
        encoding="utf-8",
    )

    preview = WellStratificationBackend().prepare(
        _request(path), PreviewOptions(max_points=limit)
    )
    selected = {(top.well_name, top.formation_name) for top in preview.payload}
    connectors = sum(
        endpoints <= selected
        for endpoints in (
            {("W1", "A"), ("W2", "A")},
            {("W3", "B"), ("W4", "B")},
        )
    )

    assert len(preview.payload) <= limit
    assert connectors == expected_connectors


def test_backend_renders_releases_and_declares_interactions(qtbot, well_tops_path: Path):
    engine = GeoVizEngine.default()
    request = _request(well_tops_path)
    preview = engine.prepare(request, PreviewOptions.local())
    widget = engine.create_widget(PreviewKind.FORMATION_TOPS)
    qtbot.addWidget(widget)

    engine.render(widget, preview)

    assert engine.capabilities(request).interactions == ("zoom", "pan", "hover")
    assert widget.tops == preview.payload

    _render(widget)
    emitted = []
    widget.hovered_top_changed.connect(lambda *payload: emitted.append(payload))
    widget.mouseMoveEvent(
        _mouse_event(
            QEvent.Type.MouseMove,
            widget._visible_top_points[0][1],
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
        )
    )

    engine.release(widget)
    assert widget.tops == ()
    assert emitted[-1][0:2] == ("", "")
