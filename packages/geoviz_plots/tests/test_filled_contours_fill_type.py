"""ISSUE-013: ``"Separate"`` was in the signature but never a contourpy
FillType — every call with it crashed. It is now rejected with a clear
error and the only supported type works."""

from __future__ import annotations

import numpy as np
import pytest

from geoviz_plots.surface.marching_squares import extract_filled_contours


def _grid():
    gx, gy = np.meshgrid(np.linspace(0.0, 10.0, 20), np.linspace(0.0, 10.0, 20))
    return gx, gy, gx + gy


def test_separate_rejected_with_clear_error():
    gx, gy, gz = _grid()
    with pytest.raises(ValueError, match="OuterOffset"):
        extract_filled_contours(gx, gy, gz, [2.0, 5.0, 8.0], fill_type="Separate")


def test_outer_offset_extracts_bands():
    gx, gy, gz = _grid()
    bands = extract_filled_contours(gx, gy, gz, [2.0, 5.0, 8.0])
    assert len(bands) == 2
    assert bands[0].level_min == 2.0 and bands[0].level_max == 5.0
