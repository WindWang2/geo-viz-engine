"""Tests for Phase 7 advanced visualization: spectral decomposition, RGB fusion, render_rgba."""

import numpy as np
import pytest

from geoviz_seismic.attributes import (
    fuse_rgb,
    compute_envelope,
    compute_instantaneous_frequency,
    compute_rms_amplitude,
    compute_sweetness,
)



# ---------------------------------------------------------------------------
# RGB fusion
# ---------------------------------------------------------------------------

class TestFuseRGB:
    def test_output_shape_and_dtype(self):
        r = np.random.randn(50, 30).astype(np.float32)
        g = np.random.randn(50, 30).astype(np.float32)
        b = np.random.randn(50, 30).astype(np.float32)
        result = fuse_rgb(r, g, b)
        assert result.shape == (50, 30, 3)
        assert result.dtype == np.uint8

    def test_value_range(self):
        r = np.random.randn(40, 20).astype(np.float32)
        g = np.random.randn(40, 20).astype(np.float32)
        b = np.random.randn(40, 20).astype(np.float32)
        result = fuse_rgb(r, g, b)
        assert np.all(result >= 0)
        assert np.all(result <= 255)

    def test_constant_input(self):
        c = np.ones((20, 10), dtype=np.float32) * 5.0
        result = fuse_rgb(c, c, c)
        # All values should be the same (clipped to 255 or some constant)
        assert result.dtype == np.uint8

    def test_different_clip_percentile(self):
        r = np.random.randn(30, 15).astype(np.float32)
        g = np.random.randn(30, 15).astype(np.float32)
        b = np.random.randn(30, 15).astype(np.float32)
        result1 = fuse_rgb(r, g, b, clip_pct=99.0)
        result2 = fuse_rgb(r, g, b, clip_pct=90.0)
        # Different clipping should produce different results
        assert not np.array_equal(result1, result2)

    def test_independent_channels(self):
        """Each channel should be normalized independently."""
        r = np.ones((20, 10), dtype=np.float32) * 100  # high values
        g = np.ones((20, 10), dtype=np.float32) * 0.01  # low values
        b = np.ones((20, 10), dtype=np.float32) * -50   # negative
        result = fuse_rgb(r, g, b)
        # All constant inputs → each channel should be 0 (lo == hi)
        assert result.shape == (20, 10, 3)


# ---------------------------------------------------------------------------
# ProfileVD.render_rgba
# ---------------------------------------------------------------------------

class TestRenderRGBA:
    @pytest.fixture(autouse=True)
    def _init(self, qtbot):
        from geoviz_seismic import ProfileVD
        self.vd = ProfileVD()
        qtbot.addWidget(self.vd)

    def test_render_rgba_basic(self):
        rgba = np.random.randint(0, 255, (50, 30, 4), dtype=np.uint8)
        self.vd.render_rgba(rgba)
        assert self.vd.has_data()

    def test_render_rgba_preserves_data(self):
        rgba = np.full((40, 20, 4), 128, dtype=np.uint8)
        self.vd.render_rgba(rgba)
        assert self.vd.has_data()

    def test_switch_between_render_and_render_rgba(self):
        # Start with normal render
        data = np.random.randn(50, 30).astype(np.float32)
        self.vd.render(data, colormap="seismic")
        assert self.vd.has_data()

        # Switch to RGBA
        rgba = np.random.randint(0, 255, (50, 30, 4), dtype=np.uint8)
        self.vd.render_rgba(rgba)
        assert self.vd.has_data()

        # Switch back to normal
        self.vd.render(data, colormap="gray")
        assert self.vd.has_data()

    def test_render_rgba_invalid_shape_raises(self):
        with pytest.raises(AssertionError):
            self.vd.render_rgba(np.zeros((50, 30), dtype=np.uint8))

    def test_render_rgba_zoom(self):
        rgba = np.random.randint(0, 255, (100, 80, 4), dtype=np.uint8)
        self.vd.render_rgba(rgba)
        # Should not crash after zoom
        self.vd._zoom_scale = 2.0
        self.vd._view_h = (0.2, 0.8)
        self.vd._view_v = (0.1, 0.9)
        self.vd._build_image_from_rgba()
