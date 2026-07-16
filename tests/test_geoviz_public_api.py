from __future__ import annotations

import ast
from pathlib import Path

import pytest

import geoviz


@pytest.fixture
def dat_files(tmp_path: Path) -> dict[str, Path]:
    contents = {
        "well_head": (
            "#WellHead File From SMI\n"
            "#Name X Y KB TotalDepth BottomX BottomY WellType\n"
            "A1 100 200 0 1000 100 200 0\n"
        ),
        "well_stratification": (
            "#WellTops File From SMI\n"
            "#WellName Name MD X Y Z TVD Time(ms)\n"
            "A1 Top-A 1000 0 0 0 1000 800\n"
        ),
        "horizon": (
            "# XYZInlineCrossline Format Horizon File From SMI\n"
            "# Field: 1 x\n# Field: 2 y\n# Field: 3 z ms\n"
            "0 0 1000\n1 0 1001\n0 1 1002\n"
        ),
        "time_depth": (
            "#TimeDepth File From SMI\n"
            "# TIME .ms\n# TVD .m\n#TIME TVD\n"
            "800 1000\n"
        ),
    }
    paths = {}
    for semantic_type, content in contents.items():
        path = tmp_path / f"{semantic_type}.dat"
        path.write_text(content, encoding="utf-8")
        paths[semantic_type] = path
    return paths


def test_default_engine_exposes_all_local_preview_capabilities(
    dat_files: dict[str, Path], tmp_path: Path
):
    engine = geoviz.GeoVizEngine.default()
    requests = (
        (
            geoviz.PreviewRequest(
                "las", str(tmp_path / "A1.Las"), "well_log", "las", "A1"
            ),
            geoviz.PreviewKind.WELL_LOG,
            ("zoom", "pan"),
        ),
        (
            geoviz.PreviewRequest(
                "sgy", str(tmp_path / "cube.sgy"), "seismic", "sgy", "Cube"
            ),
            geoviz.PreviewKind.SEISMIC_2D,
            ("slice_switch", "slice_scrub", "zoom", "pan"),
        ),
        (
            geoviz.PreviewRequest(
                "heads", str(dat_files["well_head"]), "well_head", "dat", "Wells"
            ),
            geoviz.PreviewKind.XY_SCATTER,
            ("zoom", "pan"),
        ),
        (
            geoviz.PreviewRequest(
                "tops",
                str(dat_files["well_stratification"]),
                "well_stratification",
                "dat",
                "Tops",
            ),
            geoviz.PreviewKind.FORMATION_TOPS,
            ("zoom", "pan", "hover"),
        ),
        (
            geoviz.PreviewRequest(
                "horizon", str(dat_files["horizon"]), "horizon", "dat", "H1"
            ),
            geoviz.PreviewKind.SURFACE,
            ("zoom", "pan", "contour_select"),
        ),
        (
            geoviz.PreviewRequest(
                "td", str(dat_files["time_depth"]), "time_depth", "dat", "A1 TD"
            ),
            geoviz.PreviewKind.TIME_DEPTH,
            ("zoom", "pan"),
        ),
    )

    for request, expected_kind, expected_interactions in requests:
        assert engine.supports(request)
        capabilities = engine.capabilities(request)
        assert capabilities.kind is expected_kind
        assert capabilities.interactions == expected_interactions


def test_geoviz_package_has_no_workbench_imports():
    package_root = Path(geoviz.__file__).resolve().parent
    violations = []
    for path in package_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            if any(module.split(".", 1)[0] == "paleo_workbench" for module in modules):
                violations.append(str(path.relative_to(package_root.parent)))

    assert not violations, violations
