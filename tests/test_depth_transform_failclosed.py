"""Fail-closed guards for the depth transform chain (#147)."""

from __future__ import annotations

import numpy as np
import pytest

from geoviz_well_seismic_3d.depth_transform import (
    ConstantVelocityDepth,
    DepthTransformKind,
    select_depth_transform,
)


def test_constant_velocity_rejects_nonpositive_v0():
    with pytest.raises(ValueError):
        ConstantVelocityDepth(v0_m_s=0.0)
    with pytest.raises(ValueError):
        ConstantVelocityDepth(v0_m_s=-2500.0)
    with pytest.raises(ValueError):
        ConstantVelocityDepth(v0_m_s=float("nan"))


def test_select_depth_transform_rejects_zero_v0():
    with pytest.raises(ValueError):
        select_depth_transform(constant_v0=True, v0_m_s=0.0)


def test_select_depth_transform_valid_v0_roundtrips():
    state = select_depth_transform(constant_v0=True, v0_m_s=2500.0)
    assert state.kind is DepthTransformKind.CONSTANT_V0
    depth = state.constant.time_ms_to_depth_m(2000.0)
    assert depth == pytest.approx(2500.0 * 1.0)  # 2000 ms -> 1 s -> V0/2 * 1
    back = state.constant.depth_m_to_time_ms(depth)
    assert back == pytest.approx(2000.0)


def test_registration_time_ms_to_sample_idx_requires_dt_ms():
    """Missing dt_ms must fail closed, never map TWT ms to sample #2500."""
    from geoviz_well_seismic_3d.registration import VolumeRegistration
    from geoviz_well_seismic_3d.survey import BinGridGeometry, SurveySpec

    spec = SurveySpec(
        bin_grid=BinGridGeometry(
            x_origin=500000.0,
            y_origin=4000000.0,
            il_azimuth_deg=0.0,
            il_spacing_m=25.0,
            xl_spacing_m=25.0,
        ),
        iline_start=1,
        iline_step=1,
        xline_start=1,
        xline_step=1,
        n_inlines=16,
        n_crosslines=16,
        n_samples=256,
        dt_ms=0.0,  # header parse failed -> degenerate interval
        t0_ms=0.0,
    )
    reg = VolumeRegistration(
        survey=spec, n_inline=16, n_crossline=16, n_sample=256, strides=(1, 1, 1)
    )
    with pytest.raises(ValueError):
        reg.time_ms_to_sample_idx(2500.0)
