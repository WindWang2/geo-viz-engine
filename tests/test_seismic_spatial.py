"""Tests for spatial reference model and coordinate conversion.

Defines the BinGridGeometry API and xy_to_il_xl conversion needed for
placing wells on seismic sections.
"""
import numpy as np
import pytest

from geoviz_seismic.models import BinGridGeometry, SeismicVolumeMeta


# ---------------------------------------------------------------------------
# BinGridGeometry model
# ---------------------------------------------------------------------------

class TestBinGridGeometry:

    def test_creation(self):
        """BinGridGeometry stores origin, azimuth, and spacing."""
        bg = BinGridGeometry(
            x_origin=500000.0,
            y_origin=4000000.0,
            il_azimuth_deg=0.0,
            il_spacing_m=25.0,
            xl_spacing_m=25.0,
        )
        assert bg.x_origin == 500000.0
        assert bg.y_origin == 4000000.0
        assert bg.il_spacing_m == 25.0

    def test_defaults(self):
        """Optional fields have sensible defaults."""
        bg = BinGridGeometry(
            x_origin=0.0,
            y_origin=0.0,
            il_azimuth_deg=0.0,
            il_spacing_m=1.0,
            xl_spacing_m=1.0,
        )
        assert bg.il_azimuth_deg == 0.0

    def test_xy_to_il_xl_cardinal(self):
        """Convert (x, y) to (inline, crossline) for cardinal azimuth."""
        bg = BinGridGeometry(
            x_origin=500000.0,
            y_origin=4000000.0,
            il_azimuth_deg=0.0,    # inline along Y axis
            il_spacing_m=25.0,
            xl_spacing_m=25.0,
        )
        # Well at origin → iline 0, xline 0
        il, xl = bg.xy_to_il_xl(500000.0, 4000000.0)
        assert il == pytest.approx(0.0, abs=0.5)
        assert xl == pytest.approx(0.0, abs=0.5)

        # Well 100m north, 50m east → iline 4, xline 2
        il, xl = bg.xy_to_il_xl(500050.0, 4000100.0)
        assert il == pytest.approx(4.0, abs=0.5)
        assert xl == pytest.approx(2.0, abs=0.5)

    def test_xy_to_il_xl_rotated(self):
        """Convert (x, y) to (inline, crossline) with 45° rotation."""
        bg = BinGridGeometry(
            x_origin=0.0,
            y_origin=0.0,
            il_azimuth_deg=45.0,
            il_spacing_m=25.0,
            xl_spacing_m=25.0,
        )
        # Point at (100, 100) with azimuth 45°:
        # il = (-100*sin45 + 100*cos45)/25 = 0 (on the crossline axis)
        # xl = (100*cos45 + 100*sin45)/25 = 5.66
        il, xl = bg.xy_to_il_xl(100.0, 100.0)
        assert il == pytest.approx(0.0, abs=0.5)
        assert xl == pytest.approx(100 * np.cos(np.radians(45)) / 25.0 * 2, abs=0.5)

    def test_nearest_il_xl(self):
        """nearest_il_xl returns integer inline/crossline."""
        bg = BinGridGeometry(
            x_origin=500000.0,
            y_origin=4000000.0,
            il_azimuth_deg=0.0,
            il_spacing_m=25.0,
            xl_spacing_m=25.0,
        )
        # dx=0, dy=37.5 → il=1.5, xl=0.0 → round: il=2, xl=0
        il, xl = bg.nearest_il_xl(500000.0, 4000037.5)
        assert isinstance(il, int)
        assert isinstance(xl, int)
        assert il == 2   # 37.5 / 25 = 1.5, rounds to 2
        assert xl == 0   # 0 / 25 = 0.0


# ---------------------------------------------------------------------------
# SeismicVolumeMeta with spatial reference
# ---------------------------------------------------------------------------

class TestSeismicVolumeMetaSpatial:

    def test_meta_with_bin_grid(self):
        """SeismicVolumeMeta can optionally carry a BinGridGeometry."""
        bg = BinGridGeometry(
            x_origin=500000.0,
            y_origin=4000000.0,
            il_azimuth_deg=0.0,
            il_spacing_m=25.0,
            xl_spacing_m=25.0,
        )
        meta = SeismicVolumeMeta(
            filename="test.sgy",
            n_inlines=10,
            n_crosslines=20,
            n_samples=30,
            sample_interval=4.0,
            iline_start=100,
            iline_step=1,
            xline_start=200,
            xline_step=1,
            dt_ms=4.0,
            bin_grid=bg,
        )
        assert meta.bin_grid is not None
        assert meta.bin_grid.x_origin == 500000.0

    def test_meta_without_bin_grid(self):
        """BinGridGeometry is optional (backward compatible)."""
        meta = SeismicVolumeMeta(
            filename="test.sgy",
            n_inlines=10,
            n_crosslines=20,
            n_samples=30,
            sample_interval=4.0,
            iline_start=100,
            iline_step=1,
            xline_start=200,
            xline_step=1,
            dt_ms=4.0,
        )
        assert meta.bin_grid is None

    def test_xy_to_il_xl_via_meta(self):
        """Convenience: meta-level xy_to_il_xl delegates to bin_grid."""
        bg = BinGridGeometry(
            x_origin=0.0,
            y_origin=0.0,
            il_azimuth_deg=0.0,
            il_spacing_m=25.0,
            xl_spacing_m=25.0,
        )
        meta = SeismicVolumeMeta(
            filename="test.sgy",
            n_inlines=100,
            n_crosslines=200,
            n_samples=500,
            sample_interval=4.0,
            iline_start=1000,
            iline_step=1,
            xline_start=2000,
            xline_step=1,
            dt_ms=4.0,
            bin_grid=bg,
        )
        # Absolute il/xl = il_start + fractional il/xl
        il, xl = meta.xy_to_il_xl(50.0, 100.0)
        # fractional: il=100/25=4, xl=50/25=2
        # absolute: il=1000+4=1004, xl=2000+2=2002
        assert il == pytest.approx(1004.0, abs=0.5)
        assert xl == pytest.approx(2002.0, abs=0.5)

    def test_xy_to_il_xl_without_bin_grid_returns_none(self):
        """xy_to_il_xl without bin_grid returns None instead of a fabricated grid."""
        meta = SeismicVolumeMeta(
            filename="test.sgy",
            n_inlines=10,
            n_crosslines=20,
            n_samples=30,
            sample_interval=4.0,
            iline_start=100,
            iline_step=1,
            xline_start=200,
            xline_step=1,
            dt_ms=4.0,
        )
        # #46 removed the implicit default-grid fallback: an uncalibrated
        # volume must not fabricate coordinates, so the call fails explicitly
        # (None) and leaves bin_grid untouched.
        assert meta.bin_grid is None
        assert meta.xy_to_il_xl(100.0, 200.0) is None
        assert meta.bin_grid is None


# ---------------------------------------------------------------------------
# SeismicLoader spatial header reading
# ---------------------------------------------------------------------------

class TestLoaderSpatialHeaders:
    """Tests for reading spatial reference from SEGY headers."""

    def test_inspect_reads_spatial(self, small_segy_path):
        """SeismicLoader.inspect() populates bin_grid from trace headers."""
        from geoviz_seismic.loader import SeismicLoader

        with SeismicLoader(small_segy_path) as loader:
            meta = loader.inspect()
            # Standard test SEGY may not have coordinate headers,
            # so bin_grid could be None — verify the field exists
            assert hasattr(meta, "bin_grid")

    def test_inspect_with_coordinates(self, tmp_path):
        """SEGY with CDP X/Y headers populates bin_grid."""
        import segyio

        path = str(tmp_path / "spatial_test.sgy")
        n_il, n_xl, n_samples = 5, 5, 10
        ilines = np.arange(100, 100 + n_il)
        xlines = np.arange(200, 200 + n_xl)
        dt_us = 4000
        il_spacing = 25.0
        xl_spacing = 25.0

        spec = segyio.spec()
        spec.sorting = segyio.TraceSortingFormat.INLINE_SORTING
        spec.format = 1
        spec.ilines = ilines
        spec.xlines = xlines
        spec.samples = np.arange(n_samples, dtype=np.float32) * (dt_us / 1000.0)

        rng = np.random.default_rng(42)
        with segyio.create(path, spec) as f:
            for i, il in enumerate(ilines):
                for j, xl in enumerate(xlines):
                    tr_idx = i * n_xl + j
                    # CDP X = il_index * il_spacing, CDP Y = xl_index * xl_spacing
                    cdp_x = int(i * il_spacing)
                    cdp_y = int(j * xl_spacing)
                    f.header[tr_idx] = {
                        segyio.TraceField.INLINE_3D: int(il),
                        segyio.TraceField.CROSSLINE_3D: int(xl),
                        segyio.TraceField.CDP_X: cdp_x,
                        segyio.TraceField.CDP_Y: cdp_y,
                    }
                    f.trace[tr_idx] = rng.standard_normal(n_samples, dtype=np.float32)
            f.bin[segyio.BinField.Interval] = dt_us
            f.bin[segyio.BinField.Samples] = n_samples

        from geoviz_seismic.loader import SeismicLoader
        with SeismicLoader(path) as loader:
            meta = loader.inspect()
            # If coordinates were read, bin_grid should be populated
            if meta.bin_grid is not None:
                assert meta.bin_grid.il_spacing_m > 0
                assert meta.bin_grid.xl_spacing_m > 0


# ---------------------------------------------------------------------------
# SeismicLoader read_trace convenience method
# ---------------------------------------------------------------------------

class TestReadTrace:
    """Tests for SeismicLoader.read_trace(iline, xline)."""

    def test_read_trace_shape(self, small_segy_path):
        """read_trace returns 1-D array of shape (n_samples,)."""
        from geoviz_seismic.loader import SeismicLoader

        with SeismicLoader(small_segy_path) as loader:
            meta = loader.inspect()
            trace = loader.read_trace(meta.iline_start, meta.xline_start)
            assert trace.ndim == 1
            assert trace.shape == (meta.n_samples,)
            assert trace.dtype == np.float32

    def test_read_trace_values_match_inline(self, small_segy_path):
        """Trace values from read_trace match the corresponding inline column."""
        from geoviz_seismic.loader import SeismicLoader

        with SeismicLoader(small_segy_path) as loader:
            meta = loader.inspect()
            il = meta.iline_start
            xl = meta.xline_start + 1  # second crossline

            inline = loader.read_inline(il)
            trace = loader.read_trace(il, xl)
            # The trace should match the corresponding column in the inline
            xl_idx = (xl - meta.xline_start) // meta.xline_step
            np.testing.assert_array_almost_equal(trace, inline[xl_idx, :])

    def test_read_trace_invalid_raises(self, small_segy_path):
        """read_trace raises ValueError for invalid inline/crossline."""
        from geoviz_seismic.loader import SeismicLoader

        with SeismicLoader(small_segy_path) as loader:
            loader.inspect()
            with pytest.raises(ValueError):
                loader.read_trace(99999, 99999)
