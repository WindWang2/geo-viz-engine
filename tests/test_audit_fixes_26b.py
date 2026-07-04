"""Phase 26-B: HIGH priority audit fixes — TDD RED tests."""
from __future__ import annotations

import inspect
import math

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
        # The function should use a deterministic hash, not Python's hash()
        src = inspect.getsource(_formation_color)
        assert "hash(" not in src, (
            "_formation_color uses Python's hash() which is non-deterministic. "
            "Use a stable hash (e.g. sum of ords or zlib.crc32)."
        )

    def test_tops_model_color_is_deterministic(self):
        """FormationTop.__post_init__ must not use hash() for color assignment."""
        from geoviz_cross_well.tops_model import FormationTop
        src = inspect.getsource(FormationTop.__post_init__)
        assert "hash(" not in src, (
            "FormationTop.__post_init__ uses Python's hash() which is non-deterministic."
        )

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
        src_file = inspect.getsourcefile(
            __import__("geoviz_paleo_map.layers.region_labels", fromlist=["RegionLabelsLayer"])
        )
        with open(src_file) as f:
            src = f.read()
        # Check that __init__ sets visible_labels
        init_start = src.index("def __init__")
        # Find the end of __init__ (next def at same indentation)
        after_init = src[init_start:]
        # Look for visible_labels assignment in __init__
        # __init__ ends when we hit the next method
        next_method = after_init.index("\n    def ", 1)
        init_body = after_init[:next_method]
        assert "visible_labels" in init_body, (
            "RegionLabelsLayer.__init__ must initialize self.visible_labels = []"
        )


# ── 26-B8: line_style not passed to CurveData ───────────────────────────────

class TestLineStyleNotPassed:
    """loaders.py computes line_style but never passes it to CurveData().
    All curves default to 'solid' regardless of type."""

    def test_line_style_passed_to_curvedata(self):
        src_file = inspect.getsourcefile(
            __import__("src.data.loaders", fromlist=["load_excel_well_data"])
        )
        with open(src_file) as f:
            src = f.read()
        # Find the CurveData constructor call near the line_style assignment
        # The pattern should be: line_style = "dashed" ... CurveData(..., line_style=...)
        # But currently line_style is computed AFTER CurveData() and never passed
        # Find all CurveData( calls
        import re
        curvedata_calls = [m.start() for m in re.finditer(r"CurveData\(", src)]
        # At least one call should include line_style
        found_line_style_in_curvedata = False
        for pos in curvedata_calls:
            # Get the call (up to next closing paren at same nesting)
            depth = 0
            end = pos
            for i in range(pos, len(src)):
                if src[i] == "(":
                    depth += 1
                elif src[i] == ")":
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            call_text = src[pos:end + 1]
            if "line_style" in call_text:
                found_line_style_in_curvedata = True
                break
        assert found_line_style_in_curvedata, (
            "CurveData() is called without line_style parameter. "
            "The line_style variable is computed but never passed."
        )
