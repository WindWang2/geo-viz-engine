"""Phase 26-B: HIGH priority audit fixes — TDD RED tests."""
from __future__ import annotations

import numpy as np
import pytest


# ── 26-B3/B4: Non-deterministic hash() for formation colors ────────────────

class TestDeterministicFormationColors:
    """hash() is randomized across Python processes (PYTHONHASHSEED).
    Formation colors must be deterministic so exports are reproducible."""

    def test_correlation_layer_color_is_deterministic(self):
        """_formation_color() must return the same color for the same name
        regardless of PYTHONHASHSEED."""
        from geoviz_cross_well.correlation_layer import _formation_color
        from geoviz_cross_well.tops_model import _FORMATION_PALETTE

        name = "Permian"
        expected = _FORMATION_PALETTE[
            sum(ord(c) for c in name) % len(_FORMATION_PALETTE)
        ]
        assert _formation_color(name) == expected
        assert _formation_color(name) == _formation_color(name)

    def test_tops_model_color_is_deterministic(self):
        """FormationTop.__post_init__ must not use hash() for color assignment."""
        from geoviz_cross_well.tops_model import FormationTop, _FORMATION_PALETTE

        name = "Triassic"
        expected = _FORMATION_PALETTE[
            sum(ord(c) for c in name) % len(_FORMATION_PALETTE)
        ]
        top = FormationTop(well_name="W1", formation_name=name, depth_m=100.0)
        assert top.color == expected

    def test_formation_color_consistency(self):
        """Same formation name always yields same color."""
        from geoviz_cross_well.correlation_layer import _formation_color
        color1 = _formation_color("Permian")
        color2 = _formation_color("Permian")
        assert color1 == color2

    def test_tops_model_post_init_consistency(self):
        """Two FormationTop with same name get same default color."""
        from geoviz_cross_well.tops_model import FormationTop
        t1 = FormationTop(well_name="W1", formation_name="Triassic", depth_m=100.0)
        t2 = FormationTop(well_name="W2", formation_name="Triassic", depth_m=200.0)
        assert t1.color == t2.color

    def test_formation_color_stable_across_hash_seeds(self):
        """PYTHONHASHSEED must not change formation colors across interpreters."""
        import os
        import subprocess
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        pkg_paths = [str(root)] + [
            str(path) for path in (root / "packages").iterdir() if path.is_dir()
        ]
        pythonpath = os.pathsep.join(pkg_paths + [os.environ.get("PYTHONPATH", "")])
        snippet = (
            "from geoviz_cross_well.correlation_layer import _formation_color;"
            "print(_formation_color('Permian'))"
        )
        colors = []
        for seed in ("0", "1"):
            env = os.environ.copy()
            env["PYTHONHASHSEED"] = seed
            env["PYTHONPATH"] = pythonpath
            out = subprocess.check_output(
                [sys.executable, "-c", snippet], env=env, text=True
            )
            colors.append(out.strip())
        assert colors[0] == colors[1]
        assert colors[0].startswith("#")


# ── 26-B5: IDW empty input returns zeros not NaN ───────────────────────────

class TestIDWEmptyInput:
    """When all input points are NaN-filtered, IDW should return NaN, not zeros.
    Zeros look like valid interpolated data."""

    def test_empty_after_nan_filter_returns_nan(self):
        from geoviz_plots.interpolation.idw import interpolate_idw
        x = np.array([np.nan, np.nan])
        y = np.array([np.nan, np.nan])
        z = np.array([np.nan, np.nan])
        grid_x = np.array([0.0, 1.0])
        grid_y = np.array([0.0, 1.0])
        result = interpolate_idw(x, y, z, grid_x, grid_y)
        assert result.shape == (2, 2)
        assert np.all(np.isnan(result)), (
            "IDW with all-NaN input should return NaN grid, not zeros."
        )

    def test_empty_arrays_returns_nan(self):
        from geoviz_plots.interpolation.idw import interpolate_idw
        x = np.array([])
        y = np.array([])
        z = np.array([])
        grid_x = np.array([0.0, 1.0])
        grid_y = np.array([0.0, 1.0])
        result = interpolate_idw(x, y, z, grid_x, grid_y)
        assert np.all(np.isnan(result))


# ── 26-B6: nice_number crashes on negative input ────────────────────────────

class TestNiceNumberNegative:
    """nice_number(-5, True) crashes because math.log10(negative) is undefined."""

    def test_negative_value_does_not_crash(self):
        from geoviz_plots.chart.axes import nice_number
        try:
            result = nice_number(-5.0, True)
        except (ValueError, TypeError) as e:
            pytest.fail(f"nice_number(-5.0, True) raised {type(e).__name__}: {e}")

    def test_negative_value_returns_negative(self):
        from geoviz_plots.chart.axes import nice_number
        result = nice_number(-5.0, True)
        assert result < 0, "nice_number(-5) should return a negative value"

    def test_negative_round_symmetry(self):
        """nice_number should handle negative values symmetrically."""
        from geoviz_plots.chart.axes import nice_number
        pos = nice_number(5.0, True)
        neg = nice_number(-5.0, True)
        assert abs(abs(neg) - pos) < 1e-9

    def test_negative_ceil(self):
        from geoviz_plots.chart.axes import nice_number
        result = nice_number(-3.7, False)
        assert result < 0


# ── 26-B7: RegionLabelsLayer.visible_labels not initialized ─────────────────

class TestRegionLabelsVisibleLabels:
    """visible_labels is set in paint() but not in __init__.
    Accessing it before first paint raises AttributeError."""

    def test_visible_labels_exists_before_paint(self):
        """__init__ must set self.visible_labels = [] so it's safe to read
        before the first paint call."""
        from geoviz_paleo_map.layers.region_labels import RegionLabelsLayer
        from geoviz_paleo_map.style import FaciesStyleResolver
        from geoviz_well_log.renderer.pattern_engine import PatternEngine

        layer = RegionLabelsLayer([], FaciesStyleResolver(PatternEngine()))
        assert hasattr(layer, "visible_labels")
        assert layer.visible_labels == []


# ── 26-B8: line_style not passed to CurveData ───────────────────────────────

class TestLineStyleNotPassed:
    """loaders.py computes line_style but never passes it to CurveData().
    All curves default to 'solid' regardless of type."""

    def test_line_style_passed_to_curvedata(self, tmp_path):
        import pandas as pd

        from geoviz_well_log.models import LineStyle
        from src.data.loaders import load_well_log_converted

        path = tmp_path / "curves.xlsx"
        df = pd.DataFrame({
            "深度": [100.0, 101.0],
            "GR": [10.0, 20.0],
            "AC": [70.0, 80.0],
            "RXO": [1.0, 2.0],
        })
        with pd.ExcelWriter(path) as writer:
            df.to_excel(writer, sheet_name="测井曲线", index=False)

        data = load_well_log_converted(path)
        by_name = {curve.name: curve for curve in data.curves}
        assert by_name["GR"].line_style == LineStyle.SOLID
        assert by_name["AC"].line_style == LineStyle.DASHED
        assert by_name["RXO"].line_style == LineStyle.DASHED
