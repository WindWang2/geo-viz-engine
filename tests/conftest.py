import os

import numpy as np
import pytest
import segyio


@pytest.fixture(scope="session", autouse=True)
def _qt_offscreen():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# Exact module stems that need GL, QtWebEngine, or golden PNG compare.
# Substring matching used to drag in hardware-free files (e.g.
# test_seismic_3d_sculpting via "test_seismic_3d", shader-source tests
# via "test_renderer_3d"). Fast CI is `pytest -m "not slow"`.
_SLOW_MODULES = frozenset({
    "test_seismic_view",
    "test_seismic_view_async",
    "test_seismic_view_guards",
    "test_renderer_3d",
    "test_renderer_3d_stratal",
    "test_chart_engine",
    "test_seismic_interaction",
    "test_seismic_fidelity",
    "test_map_visual_parity",
    "test_paleo_map_visual_parity",
    "test_hillshading_ui",
    "test_sculpting_ui",
})

# Hardware-free tests that live in an otherwise-slow module. Shader
# source / LUT-lookup checks are the primary CI gate for the slice-plane
# LUT path and must run in the fast job.
_FAST_IN_SLOW_MODULES = frozenset({
    "test_dual_gl_volume_item_uses_pyopengl_compiler_and_clean_gles3_source",
    "test_dual_gl_volume_item_legacy_shaders_use_legacy_texture_functions",
    "test_gl_image_lut_item_shader_has_lut_lookup_and_compiles",
    "test_gl_image_lut_item_legacy_shader_uses_texture2d",
    "test_normalize_to_index_parity_with_apply_colormap",
    "test_renderer_3d_signals",
})


def _item_module_stem(item) -> str:
    path = getattr(item, "path", None)
    if path is not None:
        return path.stem
    return item.fspath.purebasename


def _item_original_name(item) -> str:
    name = getattr(item, "originalname", None)
    if name:
        return name
    return item.name.split("[", 1)[0]


def is_slow_test(module_stem: str, original_name: str) -> bool:
    """Return True when a collected test belongs in the advisory slow job."""
    if module_stem not in _SLOW_MODULES:
        return False
    return original_name not in _FAST_IN_SLOW_MODULES


def pytest_collection_modifyitems(config, items):
    for item in items:
        if is_slow_test(_item_module_stem(item), _item_original_name(item)):
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
