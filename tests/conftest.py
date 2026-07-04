import os

import numpy as np
import pytest
import segyio


@pytest.fixture(scope="session", autouse=True)
def _qt_offscreen():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def pytest_collection_modifyitems(config, items):
    slow_modules = (
        "test_seismic_view",
        "test_renderer_3d",
        "test_seismic_3d",
        "test_well_tie_canvas",
        "test_chart_engine",
        "test_seismic_interaction",
        "test_advanced_viz",
        "test_well_tie_panel",
        "test_visual_parity",
        "test_well_log_ui",
        "test_well_log_fidelity",
        "test_map_visual",
        "test_paleo_map_visual",
        "test_plots_ui",
        "test_seismic_fidelity",
        "test_qpainter_widget",
        "test_hillshading_ui",
        "test_sculpting_ui",
        "test_surface_widget_interaction",
        "test_3d_contour_sync",
        "test_cross_plot_widget",
        "test_well_tie_export",
        "test_data_page_buttons",
        "test_data_fidelity",
        "test_data_kpi_detail",
    )
    for item in items:
        if any(m in item.nodeid for m in slow_modules):
            item.add_marker(pytest.mark.slow)


@pytest.fixture
def small_segy_path(tmp_path):
    """Create a small SEGY file for testing: 10 ilines x 20 xlines x 30 samples."""
    path = str(tmp_path / "test_cube.sgy")
    n_il, n_xl, n_samples = 10, 20, 30
    ilines = np.arange(100, 100 + n_il)
    xlines = np.arange(200, 200 + n_xl)
    dt_us = 4000

    spec = segyio.spec()
    spec.sorting = segyio.TraceSortingFormat.INLINE_SORTING
    spec.format = 1
    spec.ilines = ilines
    spec.xlines = xlines
    spec.samples = np.arange(n_samples, dtype=np.float32) * (dt_us / 1000.0)
    spec.binary_file_header = {}

    rng = np.random.default_rng(42)
    with segyio.create(path, spec) as f:
        for i, il in enumerate(ilines):
            for j, xl in enumerate(xlines):
                f.header[i * n_xl + j] = {
                    segyio.TraceField.INLINE_3D: int(il),
                    segyio.TraceField.CROSSLINE_3D: int(xl),
                }
                f.trace[i * n_xl + j] = rng.standard_normal(n_samples, dtype=np.float32)
        f.bin[segyio.BinField.Interval] = dt_us
        f.bin[segyio.BinField.Samples] = n_samples

    return path


@pytest.fixture
def dense_horizon_path(tmp_path):
    """Create a small dense horizon file: 10 ilines x 20 xlines."""
    path = str(tmp_path / "horizon_dense.txt")
    lines = []
    for il in range(100, 110):
        for xl in range(200, 220):
            lines.append(f"{il}\t{xl}\t{(il - 100) * 10.0}\n")
    with open(path, "w") as f:
        f.writelines(lines)
    return path


@pytest.fixture
def sparse_horizon_path(tmp_path):
    """Create a sparse horizon file with gaps."""
    path = str(tmp_path / "horizon_sparse.txt")
    lines = []
    for il in range(100, 110, 2):
        for xl in range(200, 220, 3):
            lines.append(f"{il}\t{xl}\t{(il - 100) * 10.0}\n")
    with open(path, "w") as f:
        f.writelines(lines)
    return path
