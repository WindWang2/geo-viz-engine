import numpy as np
import pytest

from geoviz_seismic.loader import SeismicLoader


def test_loader_inspect(small_segy_path):
    loader = SeismicLoader(small_segy_path)
    try:
        meta = loader.inspect()
        assert meta.n_inlines == 10
        assert meta.n_crosslines == 20
        assert meta.n_samples == 30
        assert meta.dt_ms == 4.0
        assert meta.iline_start == 100
        assert meta.xline_start == 200
    finally:
        loader.close()


def test_loader_read_inline(small_segy_path):
    loader = SeismicLoader(small_segy_path)
    try:
        loader.inspect()
        data = loader.read_inline(100)
        assert data.shape == (20, 30)
        assert data.dtype == np.float32
    finally:
        loader.close()


def test_loader_read_crossline(small_segy_path):
    loader = SeismicLoader(small_segy_path)
    try:
        loader.inspect()
        data = loader.read_crossline(200)
        assert data.shape == (10, 30)
        assert data.dtype == np.float32
    finally:
        loader.close()


def test_loader_read_timeslice(small_segy_path):
    loader = SeismicLoader(small_segy_path)
    try:
        loader.inspect()
        data = loader.read_timeslice(0)
        assert data.shape == (10, 20)
        assert data.dtype == np.float32
    finally:
        loader.close()


def test_loader_downsampled_volume(small_segy_path):
    loader = SeismicLoader(small_segy_path)
    try:
        loader.inspect()
        vol = loader.get_volume_downsampled(factor=(2, 2, 2))
        assert vol.ndim == 3
        assert vol.shape[0] == 5
        assert vol.shape[1] == 10
        assert vol.shape[2] == 15
    finally:
        loader.close()
