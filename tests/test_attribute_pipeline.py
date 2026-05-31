"""Integration tests for AttributePipeline dispatch (Phase 11.5-B / 11.5-D).

Covers all 14 attribute combo entries including the curvature/dip/azimuth
paths (idx 8-13) that previously had no UI-dispatch test coverage.
"""

import numpy as np
import pytest

from geoviz_seismic import attribute_pipeline as ap


def _sample_slice(shape=(64, 40)) -> np.ndarray:
    rng = np.random.default_rng(0)
    return rng.standard_normal(shape).astype(np.float32)


class TestAttributeRegistry:
    def test_label_count_matches_specs(self):
        assert len(ap.labels()) == len(ap.ATTRIBUTES) == 14

    def test_rgb_index_is_unique_and_kind_rgb(self):
        idx = ap.rgb_index()
        assert ap.ATTRIBUTES[idx].kind == "rgb"
        # Only one rgb entry
        assert sum(1 for s in ap.ATTRIBUTES if s.kind == "rgb") == 1

    def test_rgb_channel_indices_nonempty(self):
        chans = ap.rgb_channel_indices()
        assert len(chans) >= 3
        for i in chans:
            assert ap.ATTRIBUTES[i].rgb_channel


class TestApplyTraceAttributes:
    @pytest.mark.parametrize("idx", [0, 1, 2, 3, 4, 5, 6])
    def test_trace_returns_2d_same_shape(self, idx):
        data = _sample_slice()
        out = ap.apply(idx, data, sample_interval_s=0.002)
        assert out.shape == data.shape
        assert out.dtype in (np.float32, np.float64)

    def test_raw_passthrough_is_identity(self):
        data = _sample_slice()
        out = ap.apply(0, data)
        np.testing.assert_array_equal(out, data)

    def test_rgb_returns_data_unchanged(self):
        data = _sample_slice()
        out = ap.apply(ap.rgb_index(), data)
        np.testing.assert_array_equal(out, data)


class TestApplyCurvatureAttributes:
    """Phase 11.5-D: cover idx 8-13 (dip / azimuth / curvature)."""

    def test_dip_il_idx8(self):
        data = _sample_slice()
        out = ap.apply(8, data)
        assert out.shape == data.shape
        assert np.all(np.abs(out) <= np.pi / 2 + 1e-6)

    def test_dip_xl_idx9(self):
        data = _sample_slice()
        out = ap.apply(9, data)
        assert out.shape == data.shape
        assert np.all(np.abs(out) <= np.pi / 2 + 1e-6)

    def test_azimuth_idx10_in_range(self):
        data = _sample_slice()
        out = ap.apply(10, data)
        assert out.shape == data.shape
        assert np.all(out >= 0.0)
        assert np.all(out <= 2 * np.pi + 1e-6)

    @pytest.mark.parametrize("idx", [11, 12, 13])
    def test_curvature_idx_no_nan(self, idx):
        data = _sample_slice()
        out = ap.apply(idx, data)
        assert out.shape == data.shape
        assert not np.any(np.isnan(out))
        assert not np.any(np.isinf(out))


class TestApplyAllIndicesCovered:
    """Smoke-test every combo index dispatches without raising."""

    @pytest.mark.parametrize("idx", list(range(len(ap.ATTRIBUTES))))
    def test_dispatch_runs(self, idx):
        data = _sample_slice()
        out = ap.apply(idx, data, sample_interval_s=0.002)
        assert out.shape == data.shape
