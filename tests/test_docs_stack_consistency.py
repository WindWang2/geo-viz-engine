"""Docs must describe the QPainter stack, not deleted MapLibre / primary-ECharts paths."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_does_not_teach_deleted_maplibre_renderer():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "QWebEngineView + MapLibre" not in text
    assert "MapLibre GL 暗色底图" not in text
    assert "renderer.py" not in text or "MapLibre" not in text
    assert "MapPage (MapLibre GL)" not in text


def test_readme_does_not_claim_echarts_is_the_well_log_engine():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "独立测井可视化引擎 (ECharts-based)" not in text
    assert "高性能 ECharts 渲染" not in text


def test_resources_do_not_ship_unused_echarts_min_js():
    """#709: leftover echarts.min.js must not ride along in src/resources."""
    leftover = ROOT / "src" / "resources" / "js" / "echarts.min.js"
    assert not leftover.exists()
    js_files = list((ROOT / "src" / "resources").rglob("*.js"))
    assert js_files == []


def test_geoviz_seismic_pyproject_matches_changelog_head():
    """#707: published package version must not lag the CHANGELOG head."""
    import re
    import tomllib

    pyproject = tomllib.loads(
        (ROOT / "packages" / "geoviz_seismic" / "pyproject.toml").read_text(encoding="utf-8")
    )
    changelog = (ROOT / "packages" / "geoviz_seismic" / "CHANGELOG.md").read_text(encoding="utf-8")
    heads = re.findall(r"^## \[([0-9]+\.[0-9]+\.[0-9]+)\]", changelog, flags=re.M)
    assert heads, "seismic CHANGELOG has no version headings"
    assert pyproject["project"]["version"] == heads[0]
    # Keep descending order: 0.1.2 must appear before 0.1.0.
    if "0.1.2" in heads and "0.1.0" in heads:
        assert heads.index("0.1.2") < heads.index("0.1.0")
