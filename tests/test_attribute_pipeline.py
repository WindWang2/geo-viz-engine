"""Integration tests for AttributePipeline dispatch (Phase 11.5-B / 11.5-D).

Covers all 15 attribute combo entries including the curvature/dip/azimuth
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
        assert len(ap.labels()) == len(ap.ATTRIBUTES) == 15

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

    @pytest.mark.parametrize("idx", [11])
    def test_curvature_idx_no_nan(self, idx):
        data = _sample_slice()
        out = ap.apply(idx, data)
        assert out.shape == data.shape
        assert not np.any(np.isnan(out))
        assert not np.any(np.isinf(out))


class TestUnsupported2DRejected:
    """Gaussian/max curvature degenerate to all-zero maps on 2-D slices
    (inline slope is identically zero) — apply() must reject them with a
    clear error instead of silently returning zeros."""

    @pytest.mark.parametrize("label", ["高斯曲率", "最大曲率"])
    def test_2d_raises_value_error(self, label):
        idx = ap.labels().index(label)
        data = _sample_slice()
        with pytest.raises(ValueError, match="2-D"):
            ap.apply(idx, data)

    @pytest.mark.parametrize("label", ["高斯曲率", "最大曲率"])
    def test_spec_marked_unsupported(self, label):
        idx = ap.labels().index(label)
        assert ap.ATTRIBUTES[idx].supports_2d is False

    def test_mean_curvature_still_supports_2d(self):
        idx = ap.labels().index("平均曲率")
        data = _sample_slice()
        out = ap.apply(idx, data)
        assert out.shape == data.shape

    def test_3d_input_still_allowed(self):
        idx = ap.labels().index("高斯曲率")
        rng = np.random.default_rng(0)
        vol = rng.standard_normal((8, 10, 20)).astype(np.float32)
        out = ap.apply(idx, vol)
        assert out.shape == vol.shape


class TestCoherenceC3:
    """Phase P5: expose C3 coherence in the attribute combo."""

    def test_coherence_c3_in_labels(self):
        assert "相干性(C3)" in ap.labels()

    def test_coherence_c3_apply_slice(self):
        idx = ap.labels().index("相干性(C3)")
        rng = np.random.default_rng(0)
        data = rng.standard_normal((16, 32)).astype(np.float32)
        out = ap.apply(idx, data)
        assert out.shape == data.shape
        assert float(np.nanmin(out)) >= 0.0
        assert float(np.nanmax(out)) <= 1.0

    def test_coherence_c3_high_for_smooth_data(self):
        idx = ap.labels().index("相干性(C3)")
        x = np.linspace(0, 4 * np.pi, 32, dtype=np.float32)
        data = np.tile(np.sin(x), (16, 1))
        out = ap.apply(idx, data)
        assert float(np.nanmean(out)) > 0.5


class TestApplyAllIndicesCovered:
    """Smoke-test every combo index dispatches without raising."""

    @pytest.mark.parametrize("idx", list(range(len(ap.ATTRIBUTES))))
    def test_dispatch_runs(self, idx):
        data = _sample_slice()
        if not ap.ATTRIBUTES[idx].supports_2d:
            with pytest.raises(ValueError):
                ap.apply(idx, data, sample_interval_s=0.002)
            return
        out = ap.apply(idx, data, sample_interval_s=0.002)
        assert out.shape == data.shape
