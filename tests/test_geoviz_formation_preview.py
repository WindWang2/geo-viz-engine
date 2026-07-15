from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

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
        + "B-2 Gamma 1300 0 0 0 0 0\n"
        + "A-1 Alpha 1000 0 0 0 0 0\n"
        + "A-1 Beta bad-md 0 0 0 0 0\n"
        + "B-2 Alpha 1200 0 0 0 0 0\n"
        + "A-1 Gamma 1100 0 0 0 0 0\n",
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
        FormationTop("B-2", "Gamma", 1300.0),
        FormationTop("A-1", "Alpha", 1000.0),
        FormationTop("B-2", "Alpha", 1200.0),
        FormationTop("A-1", "Gamma", 1100.0),
    )
    assert preview.summary_rows == (("层位点", "4"), ("井数", "2"))
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


def test_backend_renders_releases_and_declares_interactions(qtbot, well_tops_path: Path):
    engine = GeoVizEngine.default()
    request = _request(well_tops_path)
    preview = engine.prepare(request, PreviewOptions.local())
    widget = engine.create_widget(PreviewKind.FORMATION_TOPS)
    qtbot.addWidget(widget)

    engine.render(widget, preview)

    assert engine.capabilities(request).interactions == ("zoom", "pan", "hover")
    assert widget.tops == preview.payload

    engine.release(widget)
    assert widget.tops == ()
