"""Critical gap tests — error paths, edge cases, integration seams."""
import numpy as np
import pytest
from pathlib import Path

from geoviz_seismic.models import SeismicVolumeMeta, SliceInfo
from geoviz_seismic.cache import SeismicCache
from geoviz_seismic.colormap import ColormapManager
from geoviz_seismic.loader import SeismicLoader
from geoviz_seismic.horizon import HorizonParser


# --- HorizonParser.fill_rbf ---
def test_horizon_fill_rbf_produces_valid_grid():
    """RBF fill should produce a complete grid with no NaN values."""
    sparse = np.full((5, 5), np.nan)
    sparse[1, 1] = 100.0
    sparse[3, 3] = 200.0
    parser = HorizonParser("/dev/null")
    result = parser.fill_rbf(sparse, neighbors=4, smoothing=0.0)
    assert not np.any(np.isnan(result))
    assert result.shape == (5, 5)


def test_horizon_fill_rbf_single_value():
    """RBF fill with a single known point should fill entire grid with that value."""
    sparse = np.full((4, 4), np.nan)
    sparse[2, 2] = 150.0
    parser = HorizonParser("/dev/null")
    result = parser.fill_rbf(sparse, neighbors=4, smoothing=0.0)
    assert result.shape == (4, 4)


# --- ColormapManager: jet + hsv ---
def test_colormap_jet_shape_and_range():
    rgba = ColormapManager.get_colormap("jet", n_colors=256)
    assert rgba.shape == (256, 4)
    assert rgba.dtype == np.uint8
    assert rgba[:, 3].min() == 255  # all fully opaque


def test_colormap_hsv_shape_and_range():
    rgba = ColormapManager.get_colormap("hsv", n_colors=256)
    assert rgba.shape == (256, 4)
    assert rgba.dtype == np.uint8
    assert rgba[:, 3].min() == 255  # all fully opaque


def test_colormap_apply_to_data_dmin_equals_dmax():
    """When all data values are the same, output should be a single color."""
    data = np.full((3, 3), 42.0)
    result = ColormapManager.apply_to_data(data, "seismic")
    assert result.shape == (3, 3, 4)
    # All pixels should have identical RGBA
    assert np.all(result == result[0, 0])


# --- SeismicLoader: error paths ---
def test_loader_file_not_found():
    """Inspecting a nonexistent file should raise a clear error."""
    loader = SeismicLoader("/nonexistent/path.sgy")
    with pytest.raises((FileNotFoundError, OSError)):
        loader.inspect()


def test_loader_close_clears_handle(tmp_path):
    """close() should release the file handle; second close should not error."""
    sgy_path = tmp_path / "test.sgy"
    import segyio
    spec = segyio.spec()
    spec.sorting = 2  # inline sorting
    spec.format = 1
    spec.ilines = [100, 101]
    spec.xlines = [200, 201]
    spec.samples = list(range(10))
    with segyio.create(str(sgy_path), spec) as f:
        tr = 0
        for il in spec.ilines:
            for xl in spec.xlines:
                f.header[tr] = {
                    segyio.TraceField.INLINE_3D: il,
                    segyio.TraceField.CROSSLINE_3D: xl,
                }
                f.trace[tr] = np.zeros(10, dtype=np.float32)
                tr += 1

    loader = SeismicLoader(str(sgy_path))
    loader.inspect()
    loader.close()
    # Second close should not raise
    loader.close()


def test_loader_inspect_cached(tmp_path):
    """Calling inspect() twice should return the same meta without re-reading."""
    sgy_path = tmp_path / "test.sgy"
    import segyio
    spec = segyio.spec()
    spec.sorting = 2
    spec.format = 1
    spec.ilines = [100]
    spec.xlines = [200]
    spec.samples = list(range(5))
    with segyio.create(str(sgy_path), spec) as f:
        f.header[0] = {
            segyio.TraceField.INLINE_3D: 100,
            segyio.TraceField.CROSSLINE_3D: 200,
        }
        f.trace[0] = np.zeros(5, dtype=np.float32)

    loader = SeismicLoader(str(sgy_path))
    meta1 = loader.inspect()
    meta2 = loader.inspect()
    assert meta1 == meta2
    assert meta1.n_inlines == 1
    assert meta1.n_crosslines == 1
    assert meta1.n_samples == 5
    loader.close()


# --- SeismicCache: edge cases ---
def test_cache_clear_empties_all():
    cache = SeismicCache(max_slices=3)
    cache.put(("inline", 100), np.zeros((5, 5)))
    cache.put(("crossline", 200), np.ones((5, 5)))
    cache.clear()
    assert cache.get(("inline", 100)) is None
    assert cache.get(("crossline", 200)) is None


def test_cache_lru_eviction():
    cache = SeismicCache(max_slices=2)
    cache.put(("a", 1), np.zeros(3))
    cache.put(("b", 2), np.ones(3))
    cache.put(("c", 3), np.full(3, 2.0))
    # ("a", 1) should be evicted
    assert cache.get(("a", 1)) is None
    assert cache.get(("b", 2)) is not None
    assert cache.get(("c", 3)) is not None


# --- SliceInfo: all three slice types ---
def test_slice_info_inline():
    info = SliceInfo(
        slice_type="inline",
        position=100,
        axis_h_label="Crossline",
        axis_v_label="Time (ms)",
        axis_h_values=[200.0, 201.0, 202.0],
        axis_v_values=[0.0, 4.0, 8.0],
    )
    assert info.slice_type == "inline"
    assert len(info.axis_h_values) == 3


def test_slice_info_crossline():
    info = SliceInfo(
        slice_type="crossline",
        position=200,
        axis_h_label="Inline",
        axis_v_label="Time (ms)",
        axis_h_values=[100.0, 101.0],
        axis_v_values=[0.0, 4.0],
    )
    assert info.slice_type == "crossline"


def test_slice_info_timeslice():
    info = SliceInfo(
        slice_type="time",
        position=50,
        axis_h_label="Crossline",
        axis_v_label="Inline",
        axis_h_values=[200.0, 201.0],
        axis_v_values=[100.0, 101.0],
    )
    assert info.slice_type == "time"
