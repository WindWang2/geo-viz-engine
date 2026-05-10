import pytest
from geoviz_seismic.models import SeismicVolumeMeta, SliceInfo, HorizonData


def test_seismic_volume_meta_creation():
    meta = SeismicVolumeMeta(
        filename="test.sgy",
        n_inlines=100,
        n_crosslines=200,
        n_samples=500,
        sample_interval=4.0,
        iline_start=1000,
        iline_step=1,
        xline_start=1000,
        xline_step=1,
        dt_ms=4.0,
        t0_ms=0.0,
    )
    assert meta.n_inlines == 100
    assert meta.dt_ms == 4.0


def test_seismic_volume_meta_defaults():
    meta = SeismicVolumeMeta(
        filename="test.sgy",
        n_inlines=10,
        n_crosslines=10,
        n_samples=100,
        sample_interval=2.0,
        iline_start=100,
        iline_step=1,
        xline_start=100,
        xline_step=1,
        dt_ms=2.0,
    )
    assert meta.t0_ms == 0.0


def test_slice_info_creation():
    info = SliceInfo(
        slice_type="inline",
        position=1050,
        axis_h_label="Crossline",
        axis_v_label="Time (ms)",
        axis_h_values=[100.0, 101.0, 102.0],
        axis_v_values=[0.0, 4.0, 8.0],
    )
    assert info.slice_type == "inline"
    assert len(info.axis_h_values) == 3


def test_horizon_data_creation():
    h = HorizonData(
        name="T60",
        unit="ms",
        shape=(100, 200),
        filled=False,
    )
    assert h.shape == (100, 200)
    assert not h.filled
