import numpy as np
import pytest

from geoviz_seismic.colormap import ColormapManager


def test_seismic_colormap_shape():
    rgba = ColormapManager.get_colormap("seismic", n_colors=256)
    assert rgba.shape == (256, 4)
    assert rgba.dtype == np.uint8


def test_seismic_colormap_red_blue():
    rgba = ColormapManager.get_colormap("seismic", n_colors=256)
    assert rgba[0, 2] > rgba[0, 0]
    assert rgba[-1, 0] > rgba[-1, 2]


def test_gray_colormap_shape():
    rgba = ColormapManager.get_colormap("gray", n_colors=128)
    assert rgba.shape == (128, 4)


def test_unknown_colormap_raises():
    with pytest.raises(ValueError, match="Unknown colormap"):
        ColormapManager.get_colormap("nonexistent")


def test_apply_colormap_to_data():
    data = np.array([[-1.0, 0.0, 1.0]], dtype=np.float32)
    result = ColormapManager.apply_to_data(data, "seismic")
    assert result.shape == (1, 3, 4)
    assert result.dtype == np.uint8
    assert result[0, 1, :3].sum() > 600
