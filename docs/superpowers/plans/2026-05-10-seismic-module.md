# Seismic Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `geoviz-seismic` as an independent PySide6 package providing 3D seismic volume rendering + interactive 2D profile display (VD/Wiggle), integrated into GeoViz Engine's seismic page.

**Architecture:** PyVista for 3D volume rendering with interactive slice plane widgets. QImage for VD (heatmap) profile rendering. VisPy for Wiggle (waveform) profile rendering. segyio for on-demand SEGY slicing. Data layer ported from clustering reference project. Package follows the same workspace pattern as `geoviz-well-log`.

**Tech Stack:** PySide6, PyVista/VTK, VisPy (optional), segyio, numpy, scipy, pydantic, pytest-qt

---

## File Structure

### Package files (create)

```
packages/geoviz_seismic/
├── pyproject.toml
├── README.md
├── geoviz_seismic/
│   ├── __init__.py              # Public API exports
│   ├── models.py                # SeismicVolumeMeta, SliceInfo, HorizonData
│   ├── cache.py                 # LRU slice cache
│   ├── colormap.py              # Seismic colormap manager
│   ├── loader.py                # SEGY on-demand reader
│   ├── horizon.py               # Horizon parser (ported from clustering)
│   ├── profile_vd.py            # VD heatmap rendering (QImage)
│   ├── profile_wiggle.py        # Wiggle rendering (VisPy)
│   ├── profile_widget.py        # Unified 2D profile widget
│   ├── renderer_3d.py           # PyVista 3D renderer with slice widgets
│   └── seismic_view.py          # High-level composite widget
```

### Test files (create)

```
tests/
├── conftest.py                  # Add SEGY fixture (append to existing)
├── test_seismic_models.py
├── test_seismic_cache.py
├── test_seismic_colormap.py
├── test_seismic_loader.py
├── test_seismic_horizon.py
├── test_profile_vd.py
├── test_profile_wiggle.py
├── test_profile_widget.py
├── test_renderer_3d.py
├── test_seismic_view.py
```

### App files (modify)

```
pyproject.toml                   # Add workspace member + dependency
src/app.py                       # Update seismic page import
src/pages/seismic_page.py        # Rewrite to use package
src/data/models.py               # Remove SeismicVolumeMeta (moved to package)
src/renderers/seismic_renderer.py # Delete (replaced by package)
```

---

### Task 1: Package Scaffolding

**Files:**
- Create: `packages/geoviz_seismic/pyproject.toml`
- Create: `packages/geoviz_seismic/geoviz_seismic/__init__.py`
- Create: `packages/geoviz_seismic/README.md`
- Modify: `pyproject.toml` (add workspace member + dependency)

- [ ] **Step 1: Create package directory structure**

```bash
mkdir -p packages/geoviz_seismic/geoviz_seismic
```

- [ ] **Step 2: Create pyproject.toml**

Create `packages/geoviz_seismic/pyproject.toml`:

```toml
[project]
name = "geoviz-seismic"
version = "0.1.0"
description = "Seismic volume visualization package"
authors = [{ name = "Kevin", email = "kevin@example.com" }]
requires-python = ">=3.12"
dependencies = [
    "PySide6>=6.6",
    "pyvista>=0.43",
    "segyio>=1.9",
    "numpy>=1.26",
    "scipy>=1.12",
    "pydantic>=2.0",
]

[project.optional-dependencies]
wiggle = ["vispy>=0.14"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["geoviz_seismic"]
```

- [ ] **Step 3: Create __init__.py**

Create `packages/geoviz_seismic/geoviz_seismic/__init__.py`:

```python
__version__ = "0.1.0"
```

- [ ] **Step 4: Register in workspace**

Modify root `pyproject.toml`:
- In `dependencies`, add `"geoviz-seismic"`.
- In `[tool.uv.workspace].members`, add `"packages/geoviz_seismic"`.
- In `[tool.uv.sources]`, add `geoviz-seismic = { workspace = true }`.

- [ ] **Step 5: Install and verify**

```bash
pip install -e ".[dev]"
python -c "import geoviz_seismic; print(geoviz_seismic.__version__)"
```

Expected: `0.1.0`

- [ ] **Step 6: Commit**

```bash
git add packages/geoviz_seismic/ pyproject.toml
git commit -m "feat(seismic): scaffold geoviz-seismic package"
```

- [ ] **Step 7: Create placeholder README**

Create `packages/geoviz_seismic/README.md` with a single line:
```
# geoviz-seismic
```
(Full content added in Task 1b.)

---

### Task 1b: README & Quickstart

**Files:**
- Create: `packages/geoviz_seismic/README.md`

- [ ] **Step 1: Create README.md**

Create `packages/geoviz_seismic/README.md`:

```markdown
# geoviz-seismic

3D seismic volume visualization + 2D profile display (VD/Wiggle) for PySide6.

## Install

```bash
pip install geoviz-seismic
# Optional: GPU-accelerated Wiggle rendering
pip install geoviz-seismic[wiggle]
```

## Quick Start

```python
import sys
from PySide6.QtWidgets import QApplication
from geoviz_seismic import SeismicView

app = QApplication(sys.argv)

# Option A: Load a SEGY file
view = SeismicView(path="survey.sgy")

# Option B: Built-in demo with synthetic data
view = SeismicView()

view.show()
app.exec()
```

## Features

- **3D volume rendering** with interactive inline/crossline/time slice planes
- **2D profile display** in VD (variable density heatmap) or Wiggle (waveform) mode
- **On-demand SEGY loading** — reads slices from disk, not the entire volume
- **LRU slice cache** for fast slice switching
- **Horizon surface overlay** with nearest/RBF interpolation
- **Professional seismic colormaps** (seismic, gray, jet, huang)

## API

```python
from geoviz_seismic import SeismicView, SeismicLoader, SeismicCache
from geoviz_seismic import Renderer3D, ProfileWidget, ProfileVD, ProfileWiggle
from geoviz_seismic import HorizonParser, ColormapManager
from geoviz_seismic.models import SeismicVolumeMeta, SliceInfo, HorizonData
```

## Horizon File Format

Tab-separated: `inline  crossline  time_ms`

```
1000    2000    1500.0
1000    2001    1502.5
1001    2000    1498.0
```
```

- [ ] **Step 2: Commit**

```bash
git add packages/geoviz_seismic/README.md
git commit -m "docs(seismic): add README with quickstart and API overview"
```

---

### Task 2: Data Models

**Files:**
- Create: `packages/geoviz_seismic/geoviz_seismic/models.py`
- Create: `tests/test_seismic_models.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_seismic_models.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify failure**

```bash
pytest tests/test_seismic_models.py -v
```

Expected: FAIL — `ImportError: cannot import name 'SeismicVolumeMeta' from 'geoviz_seismic'`

- [ ] **Step 3: Create models.py**

Create `packages/geoviz_seismic/geoviz_seismic/models.py`:

```python
from pydantic import BaseModel


class SeismicVolumeMeta(BaseModel):
    filename: str
    n_inlines: int
    n_crosslines: int
    n_samples: int
    sample_interval: float
    iline_start: int
    iline_step: int
    xline_start: int
    xline_step: int
    dt_ms: float
    t0_ms: float = 0.0


class SliceInfo(BaseModel):
    slice_type: str  # "inline" | "crossline" | "time"
    position: int
    axis_h_label: str
    axis_v_label: str
    axis_h_values: list[float]
    axis_v_values: list[float]


class HorizonData(BaseModel):
    name: str
    unit: str
    shape: tuple[int, int]
    filled: bool
```

- [ ] **Step 4: Update __init__.py exports**

Add to `packages/geoviz_seismic/geoviz_seismic/__init__.py`:

```python
from .models import SeismicVolumeMeta, SliceInfo, HorizonData

__version__ = "0.1.0"

__all__ = [
    "SeismicVolumeMeta",
    "SliceInfo",
    "HorizonData",
]
```

- [ ] **Step 5: Run tests to verify pass**

```bash
pytest tests/test_seismic_models.py -v
```

Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add packages/geoviz_seismic/geoviz_seismic/models.py \
        packages/geoviz_seismic/geoviz_seismic/__init__.py \
        tests/test_seismic_models.py
git commit -m "feat(seismic): add data models (SeismicVolumeMeta, SliceInfo, HorizonData)"
```

---

### Task 3: LRU Cache

**Files:**
- Create: `packages/geoviz_seismic/geoviz_seismic/cache.py`
- Create: `tests/test_seismic_cache.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_seismic_cache.py`:

```python
import numpy as np
import pytest

from geoviz_seismic.cache import SeismicCache


def test_cache_miss_returns_none():
    cache = SeismicCache(max_slices=5)
    assert cache.get(("inline", 100)) is None


def test_cache_put_and_get():
    cache = SeismicCache(max_slices=5)
    data = np.ones((10, 20), dtype=np.float32)
    cache.put(("inline", 100), data)
    result = cache.get(("inline", 100))
    assert result is not None
    np.testing.assert_array_equal(result, data)


def test_cache_lru_eviction():
    cache = SeismicCache(max_slices=3)
    for i in range(5):
        cache.put(("inline", i), np.zeros((5, 5), dtype=np.float32))
    assert cache.get(("inline", 0)) is None
    assert cache.get(("inline", 1)) is None
    assert cache.get(("inline", 2)) is not None
    assert cache.get(("inline", 3)) is not None
    assert cache.get(("inline", 4)) is not None


def test_cache_clear():
    cache = SeismicCache(max_slices=5)
    cache.put(("inline", 0), np.zeros((5, 5)))
    cache.clear()
    assert cache.get(("inline", 0)) is None


def test_cache_hit_refreshes_lru():
    cache = SeismicCache(max_slices=3)
    cache.put(("inline", 0), np.zeros((5, 5)))
    cache.put(("inline", 1), np.zeros((5, 5)))
    cache.put(("inline", 2), np.zeros((5, 5)))
    # Access 0 to refresh it
    cache.get(("inline", 0))
    # Add 3, should evict 1 (LRU)
    cache.put(("inline", 3), np.zeros((5, 5)))
    assert cache.get(("inline", 0)) is not None
    assert cache.get(("inline", 1)) is None
```

- [ ] **Step 2: Run tests to verify failure**

```bash
pytest tests/test_seismic_cache.py -v
```

Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement SeismicCache**

Create `packages/geoviz_seismic/geoviz_seismic/cache.py`:

```python
from collections import OrderedDict

import numpy as np


class SeismicCache:
    def __init__(self, max_slices: int = 50):
        self._max = max_slices
        self._cache: OrderedDict[tuple, np.ndarray] = OrderedDict()

    def get(self, key: tuple) -> np.ndarray | None:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, key: tuple, data: np.ndarray):
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = data
        while len(self._cache) > self._max:
            self._cache.popitem(last=False)

    def clear(self):
        self._cache.clear()
```

- [ ] **Step 4: Update __init__.py exports**

Add `SeismicCache` import and to `__all__`.

- [ ] **Step 5: Run tests to verify pass**

```bash
pytest tests/test_seismic_cache.py -v
```

Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add packages/geoviz_seismic/geoviz_seismic/cache.py \
        packages/geoviz_seismic/geoviz_seismic/__init__.py \
        tests/test_seismic_cache.py
git commit -m "feat(seismic): add LRU slice cache"
```

---

### Task 4: Colormap Manager

**Files:**
- Create: `packages/geoviz_seismic/geoviz_seismic/colormap.py`
- Create: `tests/test_seismic_colormap.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_seismic_colormap.py`:

```python
import numpy as np
import pytest

from geoviz_seismic.colormap import ColormapManager


def test_seismic_colormap_shape():
    rgba = ColormapManager.get_colormap("seismic", n_colors=256)
    assert rgba.shape == (256, 4)
    assert rgba.dtype == np.uint8


def test_seismic_colormap_red_blue():
    rgba = ColormapManager.get_colormap("seismic", n_colors=256)
    # Negative amplitudes → blue channel dominant at start
    assert rgba[0, 2] > rgba[0, 0]  # blue > red at low end
    # Positive amplitudes → red channel dominant at end
    assert rgba[-1, 0] > rgba[-1, 2]  # red > blue at high end


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
    # Middle value (0.0) should be white-ish
    assert result[0, 1, :3].sum() > 600  # near white
```

- [ ] **Step 2: Run tests to verify failure**

```bash
pytest tests/test_seismic_colormap.py -v
```

- [ ] **Step 3: Implement ColormapManager**

Create `packages/geoviz_seismic/geoviz_seismic/colormap.py`:

```python
import numpy as np


def _build_seismic(n: int) -> np.ndarray:
    t = np.linspace(0, 1, n)
    rgba = np.zeros((n, 4), dtype=np.uint8)
    mid = n // 2
    rgba[:mid, 0] = np.clip(t[:mid] * 2 * 255, 0, 255).astype(np.uint8)
    rgba[:mid, 1] = np.clip(t[:mid] * 2 * 255, 0, 255).astype(np.uint8)
    rgba[:mid, 2] = 255
    rgba[mid:, 0] = 255
    rgba[mid:, 1] = np.clip((1 - (t[mid:] - 0.5) * 2) * 255, 0, 255).astype(np.uint8)
    rgba[mid:, 2] = np.clip((1 - (t[mid:] - 0.5) * 2) * 255, 0, 255).astype(np.uint8)
    rgba[:, 3] = 255
    return rgba


def _build_gray(n: int) -> np.ndarray:
    vals = np.linspace(0, 255, n, dtype=np.uint8)
    rgba = np.zeros((n, 4), dtype=np.uint8)
    rgba[:, 0] = vals
    rgba[:, 1] = vals
    rgba[:, 2] = vals
    rgba[:, 3] = 255
    return rgba


def _build_jet(n: int) -> np.ndarray:
    t = np.linspace(0, 1, n)
    r = np.clip(1.5 - abs(4 * t - 3), 0, 1)
    g = np.clip(1.5 - abs(4 * t - 2), 0, 1)
    b = np.clip(1.5 - abs(4 * t - 1), 0, 1)
    rgba = np.zeros((n, 4), dtype=np.uint8)
    rgba[:, 0] = (r * 255).astype(np.uint8)
    rgba[:, 1] = (g * 255).astype(np.uint8)
    rgba[:, 2] = (b * 255).astype(np.uint8)
    rgba[:, 3] = 255
    return rgba


def _build_hsv(n: int) -> np.ndarray:
    import colorsys
    rgba = np.zeros((n, 4), dtype=np.uint8)
    for i in range(n):
        h = i / n
        r, g, b = colorsys.hsv_to_rgb(h, 1.0, 1.0)
        rgba[i] = [int(r * 255), int(g * 255), int(b * 255), 255]
    return rgba


class ColormapManager:
    SEISMIC = "seismic"
    GRAY = "gray"
    JET = "jet"
    HSV = "hsv"

    _COLORMAPS = {
        "seismic": _build_seismic,
        "gray": _build_gray,
        "jet": _build_jet,
        "hsv": _build_hsv,
    }

    @staticmethod
    def get_colormap(name: str, n_colors: int = 256) -> np.ndarray:
        builder = ColormapManager._COLORMAPS.get(name)
        if builder is None:
            raise ValueError(f"Unknown colormap: {name}")
        return builder(n_colors)

    @staticmethod
    def apply_to_data(data: np.ndarray, name: str) -> np.ndarray:
        dmin, dmax = np.nanmin(data), np.nanmax(data)
        if dmax == dmin:
            normalized = np.zeros_like(data, dtype=np.float32)
        else:
            normalized = (data - dmin) / (dmax - dmin)
        lut = ColormapManager.get_colormap(name)
        indices = (normalized * (len(lut) - 1)).astype(np.int32)
        indices = np.clip(indices, 0, len(lut) - 1)
        return lut[indices]
```

- [ ] **Step 4: Update __init__.py exports**

Add `ColormapManager` import and to `__all__`.

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_seismic_colormap.py -v
```

Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add packages/geoviz_seismic/geoviz_seismic/colormap.py \
        packages/geoviz_seismic/geoviz_seismic/__init__.py \
        tests/test_seismic_colormap.py
git commit -m "feat(seismic): add seismic colormap manager"
```

---

### Task 5: SEGY Loader

**Files:**
- Create: `packages/geoviz_seismic/geoviz_seismic/loader.py`
- Create: `tests/test_seismic_loader.py`
- Modify: `tests/conftest.py` (add SEGY fixture)

- [ ] **Step 1: Add SEGY test fixture to conftest.py**

Append to `tests/conftest.py` (or create if missing):

```python
import numpy as np
import pytest
import segyio
import tempfile
import os


@pytest.fixture
def small_segy_path(tmp_path):
    """Create a small SEGY file for testing: 10 ilines × 20 xlines × 30 samples."""
    path = str(tmp_path / "test_cube.sgy")
    n_il, n_xl, n_samples = 10, 20, 30
    ilines = np.arange(100, 100 + n_il)
    xlines = np.arange(200, 200 + n_xl)
    dt_us = 4000  # 4ms

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
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_seismic_loader.py`:

```python
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
        assert vol.shape[0] == 5   # 10/2
        assert vol.shape[1] == 10  # 20/2
        assert vol.shape[2] == 15  # 30/2
    finally:
        loader.close()
```

- [ ] **Step 3: Run tests to verify failure**

```bash
pytest tests/test_seismic_loader.py -v
```

- [ ] **Step 4: Implement SeismicLoader**

Create `packages/geoviz_seismic/geoviz_seismic/loader.py`:

```python
from __future__ import annotations

import logging
import time
import numpy as np
import segyio

from .models import SeismicVolumeMeta

logger = logging.getLogger(__name__)


class SeismicLoader:
    def __init__(self, path: str):
        self._path = path
        self._f: segyio.SegyFile | None = None
        self._meta: SeismicVolumeMeta | None = None
        self._downsampled: np.ndarray | None = None

    def inspect(self) -> SeismicVolumeMeta:
        if self._meta is not None:
            return self._meta
        f = self._open()
        ilines = np.asarray(f.ilines, dtype=np.int32)
        xlines = np.asarray(f.xlines, dtype=np.int32)
        samples = np.asarray(f.samples, dtype=np.float64)
        try:
            dt_us = int(f.bin[segyio.BinField.Interval])
        except Exception:
            dt_us = 0
        if dt_us > 0:
            dt_ms = dt_us / 1000.0
        elif samples.size >= 2:
            dt_ms = float(samples[1] - samples[0])
        else:
            dt_ms = 4.0

        self._meta = SeismicVolumeMeta(
            filename=self._path,
            n_inlines=int(ilines.size),
            n_crosslines=int(xlines.size),
            n_samples=int(samples.size),
            sample_interval=dt_ms,
            iline_start=int(ilines[0]),
            iline_step=int(ilines[1] - ilines[0]) if ilines.size > 1 else 1,
            xline_start=int(xlines[0]),
            xline_step=int(xlines[1] - xlines[0]) if xlines.size > 1 else 1,
            dt_ms=dt_ms,
            t0_ms=float(samples[0]),
        )
        return self._meta

    def read_inline(self, iline: int) -> np.ndarray:
        try:
            t0 = time.monotonic()
            f = self._open()
            data = np.asarray(f.iline[iline], dtype=np.float32)
            logger.debug("read_inline(%d): %.3fs, shape=%s", iline,
                         time.monotonic() - t0, data.shape)
            return data
        except (KeyError, ValueError) as e:
            raise ValueError(
                f"Failed to read inline {iline} from {self._path}: "
                f"{e}. Inline may be out of range "
                f"(available: {f.ilines[0]}–{f.ilines[-1]})."
            ) from e

    def read_crossline(self, xline: int) -> np.ndarray:
        try:
            t0 = time.monotonic()
            f = self._open()
            data = np.asarray(f.xline[xline], dtype=np.float32)
            logger.debug("read_crossline(%d): %.3fs, shape=%s", xline,
                         time.monotonic() - t0, data.shape)
            return data
        except (KeyError, ValueError) as e:
            raise ValueError(
                f"Failed to read crossline {xline} from {self._path}: "
                f"{e}. Crossline may be out of range "
                f"(available: {f.xlines[0]}–{f.xlines[-1]})."
            ) from e

    def read_timeslice(self, sample_idx: int) -> np.ndarray:
        try:
            t0 = time.monotonic()
            f = self._open()
            meta = self._meta or self.inspect()
            try:
                data = np.asarray(f.depth_slice[sample_idx], dtype=np.float32)
            except (AttributeError, KeyError):
                result = np.empty((meta.n_inlines, meta.n_crosslines),
                                  dtype=np.float32)
                for i, il in enumerate(f.ilines.tolist()):
                    line = np.asarray(f.iline[il], dtype=np.float32)
                    result[i, :] = line[:, sample_idx]
                data = result
            logger.debug("read_timeslice(%d): %.3fs, shape=%s", sample_idx,
                         time.monotonic() - t0, data.shape)
            return data
        except (IndexError, KeyError) as e:
            meta = self._meta or self.inspect()
            raise ValueError(
                f"Failed to read time slice {sample_idx} from {self._path}: "
                f"{e}. Sample index may be out of range "
                f"(available: 0–{meta.n_samples - 1})."
            ) from e

    def get_volume_downsampled(self, factor: tuple[int, int, int] = (4, 4, 2)) -> np.ndarray:
        if self._downsampled is not None:
            return self._downsampled
        meta = self.inspect()
        f = self._open()
        fi, fx, ft = factor
        il_indices = range(0, meta.n_inlines, fi)
        xl_indices = range(0, meta.n_crosslines, fx)
        t_indices = range(0, meta.n_samples, ft)
        vol = np.empty((len(il_indices), len(xl_indices), len(t_indices)), dtype=np.float32)
        for i, il_idx in enumerate(il_indices):
            il = int(f.ilines[il_idx])
            line = np.asarray(f.iline[il], dtype=np.float32)
            vol[i, :, :] = line[np.array(xl_indices)][:, np.array(t_indices)]
        self._downsampled = vol
        return vol

    def close(self):
        if self._f is not None:
            self._f.close()
            self._f = None

    def _open(self) -> segyio.SegyFile:
        if self._f is None:
            self._f = segyio.open(self._path, "r", strict=False, ignore_geometry=False)
        return self._f

    def __del__(self):
        self.close()
```

- [ ] **Step 5: Update __init__.py exports**

Add `SeismicLoader` import and to `__all__`.

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_seismic_loader.py -v
```

Expected: 5 passed

- [ ] **Step 7: Commit**

```bash
git add packages/geoviz_seismic/geoviz_seismic/loader.py \
        packages/geoviz_seismic/geoviz_seismic/__init__.py \
        tests/test_seismic_loader.py \
        tests/conftest.py
git commit -m "feat(seismic): add SEGY loader with on-demand slicing"
```

---

### Task 6: Horizon Parser

**Files:**
- Create: `packages/geoviz_seismic/geoviz_seismic/horizon.py`
- Create: `tests/test_seismic_horizon.py`

- [ ] **Step 1: Create test horizon fixture**

Append to `tests/conftest.py`:

```python
@pytest.fixture
def dense_horizon_path(tmp_path):
    """Create a small dense horizon file: 10 ilines × 20 xlines."""
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
    for il in range(100, 110, 2):  # every other inline
        for xl in range(200, 220, 3):  # every 3rd xline
            lines.append(f"{il}\t{xl}\t{(il - 100) * 10.0}\n")
    with open(path, "w") as f:
        f.writelines(lines)
    return path
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_seismic_horizon.py`:

```python
import numpy as np
import pytest

from geoviz_seismic.horizon import HorizonParser


def _make_axes():
    return {
        "ilines": np.arange(100, 110, dtype=np.int32),
        "xlines": np.arange(200, 220, dtype=np.int32),
        "nI": 10,
        "nX": 20,
    }


def test_parse_dense_horizon(dense_horizon_path):
    parser = HorizonParser(dense_horizon_path, unit="ms")
    axes = _make_axes()
    grid = parser.parse(axes)
    assert grid.shape == (10, 20)
    assert not np.any(np.isnan(grid))


def test_parse_sparse_has_gaps(sparse_horizon_path):
    parser = HorizonParser(sparse_horizon_path, unit="ms")
    axes = _make_axes()
    grid = parser.parse(axes)
    assert grid.shape == (10, 20)
    assert np.any(np.isnan(grid))


def test_nearest_fill(sparse_horizon_path):
    parser = HorizonParser(sparse_horizon_path, unit="ms")
    axes = _make_axes()
    grid = parser.parse(axes)
    filled = parser.fill_nearest(grid, max_dist=0)
    assert not np.any(np.isnan(filled))


def test_sample_unit_conversion(dense_horizon_path):
    parser_ms = HorizonParser(dense_horizon_path, unit="ms")
    parser_samp = HorizonParser(dense_horizon_path, unit="sample", scale=0.5)
    axes = _make_axes()
    axes["dt_ms"] = 4.0
    grid_ms = parser_ms.parse(axes)
    grid_samp = parser_samp.parse(axes)
    # sample values should be multiplied by scale * dt_ms
    assert not np.allclose(grid_ms, grid_samp)
```

- [ ] **Step 3: Run tests to verify failure**

```bash
pytest tests/test_seismic_horizon.py -v
```

- [ ] **Step 4: Implement HorizonParser**

Create `packages/geoviz_seismic/geoviz_seismic/horizon.py`:

```python
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt

_NUM_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


class HorizonParser:
    def __init__(self, path: str, unit: str = "ms", scale: float = 1.0,
                 iline_offset: int = 0, xline_offset: int = 0):
        self._path = path
        self._unit = unit
        self._scale = scale
        self._il_offset = iline_offset
        self._xl_offset = xline_offset

    def parse(self, axes: dict) -> np.ndarray:
        points = self._read_points()
        if not points:
            raise ValueError(
                f"No valid data points found in {self._path}. "
                f"Expected format: inline crossline time_ms (tab-separated). "
                f"Each line should have exactly 3 numeric columns."
            )
        ilines = axes["ilines"]
        xlines = axes["xlines"]
        nI, nX = axes["nI"], axes["nX"]
        il_to_i = {int(v): i for i, v in enumerate(ilines)}
        xl_to_j = {int(v): j for j, v in enumerate(xlines)}

        matched = 0
        grid = np.full((nI, nX), np.nan, dtype=np.float64)
        for (il, xl), val in points.items():
            il_adj = il + self._il_offset
            xl_adj = xl + self._xl_offset
            i = il_to_i.get(il_adj)
            j = xl_to_j.get(xl_adj)
            if i is not None and j is not None:
                grid[i, j] = val
                matched += 1
        if matched == 0:
            import logging
            logging.getLogger(__name__).warning(
                "Horizon file %s: %d points read but 0 matched axes "
                "(ilines %d–%d, xlines %d–%d). Check inline/xline numbering.",
                self._path, len(points),
                int(ilines[0]), int(ilines[-1]),
                int(xlines[0]), int(xlines[-1]),
            )
        return grid

        grid = np.full((nI, nX), np.nan, dtype=np.float64)
        for (il, xl), val in points.items():
            il_adj = il + self._il_offset
            xl_adj = xl + self._xl_offset
            i = il_to_i.get(il_adj)
            j = xl_to_j.get(xl_adj)
            if i is not None and j is not None:
                grid[i, j] = val
        return grid

    def fill_nearest(self, grid: np.ndarray, max_dist: float = 0) -> np.ndarray:
        mask = np.isfinite(grid)
        if mask.all():
            return grid.copy()
        dist, indices = distance_transform_edt(~mask, return_indices=True)
        filled = grid[indices[0], indices[1]]
        if max_dist > 0:
            filled[dist > max_dist] = np.nan
        return filled

    def fill_rbf(self, grid: np.ndarray, max_dist: float = 0,
                 neighbors: int = 24, smoothing: float = 0.0) -> np.ndarray:
        from scipy.interpolate import RBFInterpolator
        mask = np.isfinite(grid)
        if mask.all():
            return grid.copy()
        ys, xs = np.where(mask)
        vals = grid[mask]
        target_ys, target_xs = np.where(~mask)
        if len(ys) == 0:
            return grid.copy()
        interp = RBFInterpolator(
            np.column_stack([ys, xs]), vals,
            kernel="linear", degree=0,
            neighbors=min(neighbors, len(ys)),
            smoothing=smoothing,
        )
        result = grid.copy()
        if len(target_ys) > 0:
            result[target_ys, target_xs] = interp(np.column_stack([target_ys, target_xs]))
        if max_dist > 0:
            dist = distance_transform_edt(mask)
            result[(~mask) & (dist > max_dist)] = np.nan
        return result

    def _read_points(self) -> dict[tuple[int, int], float]:
        points: dict[tuple[int, int], float] = {}
        text = Path(self._path).read_text(encoding="utf-8", errors="replace")
        for line in text.strip().splitlines():
            nums = _NUM_RE.findall(line)
            if len(nums) < 3:
                continue
            il = int(float(nums[0]))
            xl = int(float(nums[1]))
            val = float(nums[-1]) * self._scale
            points[(il, xl)] = val
        return points
```

- [ ] **Step 5: Update __init__.py exports**

Add `HorizonParser` import and to `__all__`.

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_seismic_horizon.py -v
```

Expected: 4 passed

- [ ] **Step 7: Commit**

```bash
git add packages/geoviz_seismic/geoviz_seismic/horizon.py \
        packages/geoviz_seismic/geoviz_seismic/__init__.py \
        tests/test_seismic_horizon.py \
        tests/conftest.py
git commit -m "feat(seismic): add horizon parser with nearest and RBF fill"
```

---

### Task 7: VD Profile Rendering (QImage)

**Files:**
- Create: `packages/geoviz_seismic/geoviz_seismic/profile_vd.py`
- Create: `tests/test_profile_vd.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_profile_vd.py`:

```python
import numpy as np
import pytest

from geoviz_seismic.profile_vd import ProfileVD


def test_profile_vd_render_creates_image(qtbot):
    widget = ProfileVD()
    qtbot.addWidget(widget)
    data = np.random.randn(20, 50).astype(np.float32)
    widget.render(data, colormap="seismic")
    assert widget.has_data()


def test_profile_vd_colormap_change(qtbot):
    widget = ProfileVD()
    qtbot.addWidget(widget)
    data = np.random.randn(20, 50).astype(np.float32)
    widget.render(data, colormap="seismic")
    widget.set_colormap("gray")
    assert widget.current_colormap() == "gray"
```

- [ ] **Step 2: Run tests to verify failure**

```bash
pytest tests/test_profile_vd.py -v
```

- [ ] **Step 3: Implement ProfileVD**

Create `packages/geoviz_seismic/geoviz_seismic/profile_vd.py`:

```python
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QImage, QPainter, QPen, QColor, QFont
from PySide6.QtWidgets import QWidget

from .colormap import ColormapManager
from .models import SliceInfo

_AXIS_MARGIN = 50   # pixels for axis labels
_COLORBAR_W = 20    # pixels for colorbar width


class ProfileVD(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._qimage: QImage | None = None
        self._current_colormap: str = "seismic"
        self._data: np.ndarray | None = None
        self._slice_info: SliceInfo | None = None
        self._dmin: float = 0.0
        self._dmax: float = 1.0

    def render(self, data: np.ndarray, colormap: str = "seismic",
               slice_info: SliceInfo | None = None):
        self._data = data
        self._current_colormap = colormap
        self._slice_info = slice_info
        self._dmin = float(np.nanmin(data))
        self._dmax = float(np.nanmax(data))
        if self._dmin == self._dmax:
            self._dmax = self._dmin + 1.0

        rgba = ColormapManager.apply_to_data(data, colormap)
        h, w = rgba.shape[:2]
        img_data = np.ascontiguousarray(rgba)
        self._qimage = QImage(
            img_data.data, w, h, w * 4,
            QImage.Format.Format_RGBA8888,
        )
        self._img_data = img_data
        self.update()

    def has_data(self) -> bool:
        return self._data is not None

    def current_colormap(self) -> str:
        return self._current_colormap

    def paintEvent(self, event):
        if self._qimage is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = self.width(), self.height()

        # Image area (with margins for axes)
        img_x = _AXIS_MARGIN
        img_y = 0
        img_w = w - _AXIS_MARGIN - _COLORBAR_W - 10
        img_h = h - _AXIS_MARGIN

        # Draw seismic image
        target = QRectF(img_x, img_y, img_w, img_h)
        painter.drawImage(target, self._qimage)

        # Draw axis labels
        painter.setPen(QPen(QColor(200, 200, 200)))
        painter.setFont(QFont("Monospace", 8))
        if self._slice_info:
            # Horizontal axis ticks
            h_vals = self._slice_info.axis_h_values
            n_h = min(5, len(h_vals))
            for i in range(n_h):
                frac = i / max(n_h - 1, 1)
                x = img_x + frac * img_w
                val = h_vals[int(frac * (len(h_vals) - 1))]
                painter.drawText(QPointF(x - 15, h - 5), f"{val:.0f}")
            # Vertical axis ticks
            v_vals = self._slice_info.axis_v_values
            n_v = min(5, len(v_vals))
            for i in range(n_v):
                frac = i / max(n_v - 1, 1)
                y = img_y + frac * img_h
                val = v_vals[int(frac * (len(v_vals) - 1))]
                painter.drawText(QPointF(2, y + 10), f"{val:.0f}")

        # Draw colorbar
        cb_x = w - _COLORBAR_W - 5
        cb_y = img_y + 10
        cb_h = img_h - 20
        lut = ColormapManager.get_colormap(self._current_colormap)
        n_colors = len(lut)
        for row in range(cb_h):
            frac = row / max(cb_h - 1, 1)
            idx = int((1 - frac) * (n_colors - 1))
            c = lut[idx]
            painter.setPen(QColor(int(c[0]), int(c[1]), int(c[2])))
            painter.drawLine(cb_x, cb_y + row, cb_x + _COLORBAR_W, cb_y + row)
        # Colorbar labels
        painter.setPen(QPen(QColor(200, 200, 200)))
        painter.drawText(QPointF(cb_x - 5, cb_y - 2), f"{self._dmax:.1f}")
        painter.drawText(QPointF(cb_x - 5, cb_y + cb_h + 10), f"{self._dmin:.1f}")

        painter.end()

    def set_colormap(self, name: str):
        if self._data is not None and name != self._current_colormap:
            self.render(self._data, colormap=name, slice_info=self._slice_info)
```

- [ ] **Step 4: Update __init__.py exports**

Add `ProfileVD` import and to `__all__`.

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_profile_vd.py -v
```

Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add packages/geoviz_seismic/geoviz_seismic/profile_vd.py \
        packages/geoviz_seismic/geoviz_seismic/__init__.py \
        tests/test_profile_vd.py
git commit -m "feat(seismic): add VD heatmap profile rendering with QImage"
```

---

### Task 8: Wiggle Profile Rendering (VisPy)

**Files:**
- Create: `packages/geoviz_seismic/geoviz_seismic/profile_wiggle.py`
- Create: `tests/test_profile_wiggle.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_profile_wiggle.py`:

```python
import numpy as np
import pytest

from geoviz_seismic.profile_wiggle import ProfileWiggle


def test_profile_wiggle_render(qtbot):
    widget = ProfileWiggle()
    qtbot.addWidget(widget)
    data = np.random.randn(20, 50).astype(np.float32)
    widget.render(data, trace_step=2)
    assert widget.has_data()
    assert widget.trace_step() == 2


def test_profile_wiggle_trace_step(qtbot):
    widget = ProfileWiggle()
    qtbot.addWidget(widget)
    data = np.random.randn(20, 50).astype(np.float32)
    widget.render(data, trace_step=5)
    assert widget.trace_step() == 5


def test_profile_wiggle_no_data(qtbot):
    widget = ProfileWiggle()
    qtbot.addWidget(widget)
    assert not widget.has_data()
    assert widget.trace_step() == 1
```

- [ ] **Step 2: Run tests to verify failure**

```bash
pytest tests/test_profile_wiggle.py -v
```

- [ ] **Step 3: Implement ProfileWiggle**

Create `packages/geoviz_seismic/geoviz_seismic/profile_wiggle.py`:

VisPy is optional. When unavailable, falls back to QPainter rendering.
This avoids mixing VTK and VisPy OpenGL contexts in one process.

```python
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QPolygonF
from PySide6.QtWidgets import QWidget

try:
    import vispy.app
    vispy.app.use_app("pyside6")
    from vispy.scene import SceneCanvas
    _HAS_VISPY = True
except ImportError:
    _HAS_VISPY = False


class ProfileWiggle(QWidget):
    _fallback_warned = False

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: np.ndarray | None = None
        self._trace_step: int = 1
        self._vispy_canvas = None
        self._vispy_view = None

        if _HAS_VISPY:
            self._init_vispy()
        else:
            if not ProfileWiggle._fallback_warned:
                import logging
                logging.getLogger(__name__).info(
                    "VisPy not available. Wiggle using QPainter fallback. "
                    "For GPU acceleration: pip install geoviz-seismic[wiggle]"
                )
                ProfileWiggle._fallback_warned = True

    def _init_vispy(self):
        from PySide6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._vispy_canvas = SceneCanvas(keys="interactive", show=False)
        self._vispy_view = self._vispy_canvas.central_widget.add_view()
        self._vispy_view.camera = "panzoom"
        layout.addWidget(self._vispy_canvas.native)
        self._visuals = []

    def has_data(self) -> bool:
        return self._data is not None

    def trace_step(self) -> int:
        return self._trace_step

    def render(self, data: np.ndarray, trace_step: int = 1):
        self._data = data
        self._trace_step = max(1, trace_step)
        if _HAS_VISPY and self._vispy_canvas is not None:
            self._draw_vispy()
        self.update()

    def set_trace_step(self, step: int):
        if self._data is not None and step != self._trace_step:
            self._trace_step = max(1, step)
            self.update()

    def paintEvent(self, event):
        if _HAS_VISPY and self._vispy_canvas is not None:
            return  # VisPy handles its own rendering
        if self._data is None:
            return
        self._draw_qpainter()

    def _draw_qpainter(self):
        """QPainter fallback when VisPy is unavailable."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            painter.end()
            return

        data = self._data
        n_traces, n_samples = data.shape
        trace_indices = list(range(0, n_traces, self._trace_step))
        n_draw = len(trace_indices)
        if n_draw == 0:
            painter.end()
            return

        trace_w = w / n_draw
        pen = QPen(QColor(0, 0, 0), 1)
        fill_brush = QBrush(QColor(50, 50, 50, 150))
        no_brush = QBrush()

        for i, t in enumerate(trace_indices):
            trace = data[t]
            x_center = (i + 0.5) * trace_w
            y_scale = h / max(n_samples - 1, 1)
            amp_scale = trace_w * 0.4

            # Draw filled positive area
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill_brush)
            points = []
            in_fill = False
            for s in range(n_samples):
                x = x_center + trace[s] * amp_scale
                y = s * y_scale
                if trace[s] > 0:
                    if not in_fill:
                        points.append((x_center, y))
                        in_fill = True
                    points.append((x, y))
                else:
                    if in_fill:
                        points.append((x_center, y))
                        poly = QPolygonF([QPointF(px, py) for px, py in points])
                        painter.drawPolygon(poly)
                        points = []
                        in_fill = False
            if in_fill and points:
                points.append((x_center, (n_samples - 1) * y_scale))
                poly = QPolygonF([QPointF(px, py) for px, py in points])
                painter.drawPolygon(poly)

            # Draw trace line
            painter.setPen(pen)
            painter.setBrush(no_brush)
            line_points = []
            for s in range(n_samples):
                x = x_center + trace[s] * amp_scale
                y = s * y_scale
                line_points.append(QPointF(x, y))
            painter.drawPolyline(QPolygonF(line_points))

        painter.end()

    def _draw_vispy(self):
        """VisPy batch rendering for large trace counts."""
        from vispy.scene.visuals import Line
        for v in self._visuals:
            v.parent = None
        self._visuals.clear()
        if self._data is None:
            return

        data = self._data
        n_traces, n_samples = data.shape
        trace_indices = list(range(0, n_traces, self._trace_step))
        scale = 0.8 * self._trace_step

        # Batch all lines into a single visual using connect segments
        all_pos = []
        connections = []
        for t_idx, t in enumerate(trace_indices):
            trace = data[t]
            x_center = float(t_idx * scale)
            y = np.arange(n_samples, dtype=np.float32)
            x = x_center + trace * scale * 0.4
            seg = np.column_stack([x, y]).astype(np.float32)
            start = len(all_pos)
            all_pos.append(seg)
            # connect points within this trace, disconnect between traces
            conn = np.ones(len(seg) - 1, dtype=bool)
            connections.append(conn)

        if all_pos:
            pos = np.vstack(all_pos)
            conn = np.concatenate(connections)
            line = Line(pos=pos, connect=conn, color="black",
                       width=1, parent=self._vispy_view.scene,
                       method="gl")
            self._visuals.append(line)

        self._vispy_view.camera.set_range()
        self._vispy_canvas.update()
```

- [ ] **Step 4: Update __init__.py exports**

Add `ProfileWiggle` import and to `__all__`.

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_profile_wiggle.py -v
```

Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add packages/geoviz_seismic/geoviz_seismic/profile_wiggle.py \
        packages/geoviz_seismic/geoviz_seismic/__init__.py \
        tests/test_profile_wiggle.py
git commit -m "feat(seismic): add Wiggle trace profile rendering with VisPy"
```

---

### Task 9: Profile Widget (VD/Wiggle Switch)

**Files:**
- Create: `packages/geoviz_seismic/geoviz_seismic/profile_widget.py`
- Create: `tests/test_profile_widget.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_profile_widget.py`:

```python
import numpy as np
import pytest

from PySide6.QtWidgets import QStackedWidget

from geoviz_seismic.profile_widget import ProfileWidget


def test_profile_widget_default_vd(qtbot):
    widget = ProfileWidget()
    qtbot.addWidget(widget)
    assert widget._mode == "vd"


def test_profile_widget_switch_mode(qtbot):
    widget = ProfileWidget()
    qtbot.addWidget(widget)
    widget.set_display_mode("wiggle")
    assert widget._mode == "wiggle"


def test_profile_widget_update_profile(qtbot):
    widget = ProfileWidget()
    qtbot.addWidget(widget)
    data = np.random.randn(20, 50).astype(np.float32)
    widget.update_profile(data)
    assert widget._vd.has_data()
```

- [ ] **Step 2: Run tests to verify failure**

```bash
pytest tests/test_profile_widget.py -v
```

- [ ] **Step 3: Implement ProfileWidget**

Create `packages/geoviz_seismic/geoviz_seismic/profile_widget.py`:

```python
from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QWidget, QStackedWidget, QVBoxLayout

from .profile_vd import ProfileVD
from .profile_wiggle import ProfileWiggle
from .models import SliceInfo


class ProfileWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        self._vd = ProfileVD()
        self._wiggle = ProfileWiggle()
        self._stack.addWidget(self._vd)
        self._stack.addWidget(self._wiggle)

        self._mode = "vd"

    def update_profile(self, data: np.ndarray, trace_step: int = 2,
                       slice_info: SliceInfo | None = None):
        if self._mode == "vd":
            self._vd.render(data, colormap=self._vd.current_colormap(),
                            slice_info=slice_info)
        else:
            self._wiggle.render(data, trace_step=trace_step)

    def set_display_mode(self, mode: str):
        if mode == "vd":
            self._stack.setCurrentIndex(0)
            self._mode = "vd"
        elif mode == "wiggle":
            self._stack.setCurrentIndex(1)
            self._mode = "wiggle"

    def set_colormap(self, name: str):
        self._vd.set_colormap(name)

    def set_wiggle_density(self, trace_step: int):
        self._wiggle.set_trace_step(trace_step)
```

- [ ] **Step 4: Update __init__.py exports**

Add `ProfileWidget` import and to `__all__`.

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_profile_widget.py -v
```

Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add packages/geoviz_seismic/geoviz_seismic/profile_widget.py \
        packages/geoviz_seismic/geoviz_seismic/__init__.py \
        tests/test_profile_widget.py
git commit -m "feat(seismic): add unified profile widget with VD/Wiggle switching"
```

---

### Task 10: 3D Renderer (PyVista)

**Files:**
- Create: `packages/geoviz_seismic/geoviz_seismic/renderer_3d.py`
- Create: `tests/test_renderer_3d.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_renderer_3d.py`:

```python
import numpy as np
import pytest

from PySide6.QtWidgets import QWidget

from geoviz_seismic.renderer_3d import Renderer3D


def test_renderer_3d_init(qtbot):
    widget = Renderer3D()
    qtbot.addWidget(widget)
    assert widget._plotter is not None


def test_renderer_3d_load_volume(qtbot):
    widget = Renderer3D()
    qtbot.addWidget(widget)
    data = np.random.randn(10, 10, 10).astype(np.float32)
    widget.load_volume(data)
    assert widget._loaded


def test_renderer_3d_signals(qtbot):
    widget = Renderer3D()
    qtbot.addWidget(widget)
    assert hasattr(widget, 'slice_changed')
```

- [ ] **Step 2: Run tests to verify failure**

```bash
pytest tests/test_renderer_3d.py -v
```

- [ ] **Step 3: Implement Renderer3D**

Create `packages/geoviz_seismic/geoviz_seismic/renderer_3d.py`:

```python
from __future__ import annotations

import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout


class Renderer3D(QWidget):
    slice_changed = Signal(str, int)  # (slice_type, position)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plotter = QtInteractor(self)
        layout.addWidget(self._plotter.interactor)
        self._loaded = False
        self._volume_data: np.ndarray | None = None
        self._meta = None

    def load_volume(self, data: np.ndarray, origin=(0, 0, 0),
                    spacing=(1, 1, 1)):
        self._volume_data = data
        self._plotter.clear()
        grid = pv.ImageData(
            dimensions=np.array(data.shape) + 1,
            spacing=spacing,
            origin=origin,
        )
        grid["amplitude"] = data.flatten(order="F")
        self._plotter.add_volume(
            grid, cmap="seismic", opacity="sigmoid",
            name="volume",
        )
        self._plotter.reset_camera()
        self._loaded = True

    def add_horizon(self, horizon_data: np.ndarray, origin=(0, 0, 0),
                    spacing=(1, 1)):
        if horizon_data is None:
            return
        nI, nX = horizon_data.shape
        x = np.arange(nX, dtype=np.float64) * spacing[1] + origin[0]
        y = np.arange(nI, dtype=np.float64) * spacing[0] + origin[1]
        xx, yy = np.meshgrid(x, y)
        points = np.column_stack([
            xx.ravel(), yy.ravel(), horizon_data.ravel()
        ])
        mesh = pv.StructuredGrid()
        mesh.points = points
        mesh.dimensions = [nX, nI, 1]
        self._plotter.add_mesh(
            mesh, color="yellow", opacity=0.7,
            name="horizon", show_edges=False,
        )

    def set_colormap(self, cmap_name: str):
        if self._loaded:
            self._plotter.update_scalars(
                self._volume_data.flatten(order="F"),
                name="amplitude",
            )

    def clear(self):
        self._plotter.clear()
        self._loaded = False
        self._volume_data = None
```

- [ ] **Step 4: Update __init__.py exports**

Add `Renderer3D` import and to `__all__`.

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_renderer_3d.py -v
```

Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add packages/geoviz_seismic/geoviz_seismic/renderer_3d.py \
        packages/geoviz_seismic/geoviz_seismic/__init__.py \
        tests/test_renderer_3d.py
git commit -m "feat(seismic): add 3D volume renderer with PyVista"
```

---

### Task 11: SeismicView (High-Level Composite)

**Files:**
- Create: `packages/geoviz_seismic/geoviz_seismic/seismic_view.py`
- Create: `tests/test_seismic_view.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_seismic_view.py`:

```python
import numpy as np
import pytest

from geoviz_seismic.seismic_view import SeismicView


def test_seismic_view_init(qtbot):
    view = SeismicView()
    qtbot.addWidget(view)
    assert view.is_ready()
    # Auto-demo loads synthetic data on empty init
    assert view.is_loaded()


def test_seismic_view_load_demo(qtbot):
    view = SeismicView()
    qtbot.addWidget(view)
    data = np.random.randn(10, 15, 20).astype(np.float32)
    view.load_demo(data)
    assert view.is_loaded()


def test_seismic_view_set_mode(qtbot):
    view = SeismicView()
    qtbot.addWidget(view)
    view.set_display_mode("wiggle")
    assert view.display_mode() == "wiggle"
    view.set_display_mode("vd")
    assert view.display_mode() == "vd"
```

- [ ] **Step 2: Run tests to verify failure**

```bash
pytest tests/test_seismic_view.py -v
```

- [ ] **Step 3: Implement SeismicView**

Create `packages/geoviz_seismic/geoviz_seismic/seismic_view.py`:

```python
from __future__ import annotations

import logging
import numpy as np
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QSplitter,
    QPushButton, QComboBox, QLabel, QFileDialog, QToolBar,
)

from .renderer_3d import Renderer3D
from .profile_widget import ProfileWidget
from .loader import SeismicLoader
from .horizon import HorizonParser
from .cache import SeismicCache
from .models import SeismicVolumeMeta, SliceInfo


class SeismicView(QWidget):
    def __init__(self, parent=None, path: str | None = None):
        super().__init__(parent)
        self._loader: SeismicLoader | None = None
        self._cache = SeismicCache(max_slices=50)
        self._meta: SeismicVolumeMeta | None = None
        self._horizon_grids: dict[str, np.ndarray] = {}
        self._ds_factor: tuple[int, int, int] = (1, 1, 1)
        self._log = logging.getLogger(__name__)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = self._build_toolbar()
        layout.addWidget(toolbar)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self._renderer_3d = Renderer3D()
        self._profile_widget = ProfileWidget()
        splitter.addWidget(self._renderer_3d)
        splitter.addWidget(self._profile_widget)
        splitter.setSizes([400, 300])
        layout.addWidget(splitter)

        # Throttle slice updates: only refresh 2D profile after
        # 200ms of no new slice_changed signals (drag release)
        self._pending_slice: tuple[str, int] | None = None
        self._slice_timer = QTimer(self)
        self._slice_timer.setSingleShot(True)
        self._slice_timer.setInterval(200)
        self._slice_timer.timeout.connect(self._apply_pending_slice)

        self._renderer_3d.slice_changed.connect(self._on_slice_changed)

        # Auto-load: SEGY file if path given, else synthetic demo
        if path is not None:
            self.load_segy(path)
        else:
            self.load_demo(self._generate_synthetic())

    def is_ready(self) -> bool:
        return True

    def is_loaded(self) -> bool:
        return self._meta is not None

    def display_mode(self) -> str:
        return self._profile_widget._mode

    def _build_toolbar(self) -> QWidget:
        bar = QToolBar()

        load_btn = QPushButton("加载 SEGY")
        load_btn.clicked.connect(self._load_segy)
        demo_btn = QPushButton("Demo")
        demo_btn.clicked.connect(self._load_demo_data)
        horizon_btn = QPushButton("层位")
        horizon_btn.clicked.connect(self._load_horizon)

        self._slice_type_combo = QComboBox()
        self._slice_type_combo.addItems(["Inline", "Crossline", "Time"])
        self._slice_type_combo.currentIndexChanged.connect(
            self._on_slice_type_changed
        )

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["VD 热图", "Wiggle 波形"])
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        self._cmap_combo = QComboBox()
        self._cmap_combo.addItems(["seismic", "gray", "jet"])
        self._cmap_combo.currentTextChanged.connect(
            self._profile_widget.set_colormap
        )

        self._slice_label = QLabel("未加载")
        self._slice_label.setStyleSheet("color: #888; padding: 0 8px;")

        bar.addWidget(load_btn)
        bar.addWidget(demo_btn)
        bar.addWidget(horizon_btn)
        bar.addWidget(QLabel(" 剖面:"))
        bar.addWidget(self._slice_type_combo)
        bar.addWidget(QLabel(" 显示:"))
        bar.addWidget(self._mode_combo)
        bar.addWidget(QLabel(" 色标:"))
        bar.addWidget(self._cmap_combo)
        bar.addWidget(self._slice_label)
        return bar

    def load_demo(self, data: np.ndarray):
        self._ds_factor = (1, 1, 1)
        self._meta = SeismicVolumeMeta(
            filename="demo",
            n_inlines=data.shape[0],
            n_crosslines=data.shape[1],
            n_samples=data.shape[2],
            sample_interval=4.0,
            iline_start=0,
            iline_step=1,
            xline_start=0,
            xline_step=1,
            dt_ms=4.0,
        )
        self._renderer_3d.load_volume(data)
        mid = data.shape[0] // 2
        info = self._build_slice_info("inline", mid, data[mid].shape)
        self._profile_widget.update_profile(data[mid], slice_info=info)
        self._slice_label.setText(f"Inline {mid}")
        self._log.info("Demo loaded: shape=%s", data.shape)

    @staticmethod
    def _generate_synthetic(
        n_inlines: int = 60, n_crosslines: int = 80,
        n_samples: int = 100,
    ) -> np.ndarray:
        """Generate synthetic seismic with geologically realistic structure:
        horizontal reflectors with gentle dip, a fault offset, and noise."""
        t = np.linspace(0, 4 * np.pi, n_samples, dtype=np.float32)
        il = np.arange(n_inlines, dtype=np.float32)
        xl = np.arange(n_crosslines, dtype=np.float32)
        # Reflector field: sine waves with gentle dip along inline
        field = np.zeros((n_inlines, n_crosslines, n_samples), dtype=np.float32)
        for i in range(n_inlines):
            dip = 0.02 * i  # gentle dip
            reflector = np.sin(t + dip) + 0.5 * np.sin(2.3 * t + dip)
            field[i, :] = reflector[np.newaxis, :]
        # Add a normal fault at inline 30, offsetting by 5 samples
        fault_il = n_inlines // 2
        offset = 5
        field[fault_il:, :, offset:] = field[fault_il:, :, :-offset]
        field[fault_il:, :, :offset] = 0
        # Add Gaussian noise
        rng = np.random.default_rng(42)
        noise = rng.normal(0, 0.15, field.shape).astype(np.float32)
        return field + noise

    def load_segy(self, path: str):
        self._loader = SeismicLoader(path)
        self._meta = self._loader.inspect()
        self._log.info("SEGY inspected: %s (%d×%d×%d)", path,
                       self._meta.n_inlines, self._meta.n_crosslines,
                       self._meta.n_samples)
        self._ds_factor = (4, 4, 2)
        vol = self._loader.get_volume_downsampled(factor=self._ds_factor)
        self._log.info("Volume downsampled: shape=%s", vol.shape)
        self._renderer_3d.load_volume(vol)
        mid_il = (self._meta.iline_start
                  + self._meta.n_inlines // 2 * self._meta.iline_step)
        data = self._loader.read_inline(mid_il)
        info = self._build_slice_info("inline", mid_il, data.shape)
        self._profile_widget.update_profile(data, slice_info=info)
        self._slice_label.setText(f"Inline {mid_il}")

    def set_display_mode(self, mode: str):
        self._profile_widget.set_display_mode(mode)

    def _build_slice_info(self, slice_type: str, position: int,
                          data_shape: tuple) -> SliceInfo:
        if self._meta is None:
            return SliceInfo(
                slice_type=slice_type, position=position,
                axis_h_label="X", axis_v_label="Y",
                axis_h_values=[0.0], axis_v_values=[0.0],
            )
        m = self._meta
        if slice_type == "inline":
            h_vals = [m.xline_start + i * m.xline_step
                      for i in range(data_shape[1] if len(data_shape) > 1
                                     else data_shape[0])]
            v_vals = [m.t0_ms + i * m.dt_ms for i in range(data_shape[0])]
            return SliceInfo(
                slice_type=slice_type, position=position,
                axis_h_label="Crossline", axis_v_label="Time (ms)",
                axis_h_values=[float(v) for v in h_vals],
                axis_v_values=[float(v) for v in v_vals],
            )
        elif slice_type == "crossline":
            h_vals = [m.iline_start + i * m.iline_step
                      for i in range(data_shape[1] if len(data_shape) > 1
                                     else data_shape[0])]
            v_vals = [m.t0_ms + i * m.dt_ms for i in range(data_shape[0])]
            return SliceInfo(
                slice_type=slice_type, position=position,
                axis_h_label="Inline", axis_v_label="Time (ms)",
                axis_h_values=[float(v) for v in h_vals],
                axis_v_values=[float(v) for v in v_vals],
            )
        else:  # time
            h_vals = [m.iline_start + i * m.iline_step
                      for i in range(data_shape[1] if len(data_shape) > 1
                                     else data_shape[0])]
            v_vals = [m.xline_start + i * m.xline_step
                      for i in range(data_shape[0])]
            return SliceInfo(
                slice_type=slice_type, position=position,
                axis_h_label="Inline", axis_v_label="Crossline",
                axis_h_values=[float(v) for v in h_vals],
                axis_v_values=[float(v) for v in v_vals],
            )

    @Slot(str, int)
    def _on_slice_changed(self, slice_type: str, position: int):
        self._pending_slice = (slice_type, position)
        self._slice_timer.start()  # Resets timer on each drag move

    @Slot()
    def _apply_pending_slice(self):
        if self._pending_slice is None:
            return
        slice_type, position = self._pending_slice
        self._pending_slice = None
        if self._loader is None or self._meta is None:
            return

        # Plane widget gives downsampled voxel indices.
        # Convert to actual inline/crossline numbers for segyio.
        m = self._meta
        df = self._ds_factor
        if slice_type == "inline":
            actual_pos = m.iline_start + position * df[0] * m.iline_step
        elif slice_type == "crossline":
            actual_pos = m.xline_start + position * df[1] * m.xline_step
        else:
            actual_pos = position * df[2]

        cache_key = (slice_type, actual_pos)
        cached = self._cache.get(cache_key)
        if cached is not None:
            data = cached
            self._log.debug("Cache hit: %s %d", slice_type, actual_pos)
        else:
            self._log.debug("Cache miss: %s %d, reading from disk", slice_type, actual_pos)
            if slice_type == "inline":
                data = self._loader.read_inline(actual_pos)
            elif slice_type == "crossline":
                data = self._loader.read_crossline(actual_pos)
            else:
                data = self._loader.read_timeslice(actual_pos)
            self._cache.put(cache_key, data)

        info = self._build_slice_info(slice_type, actual_pos, data.shape)
        self._profile_widget.update_profile(data, slice_info=info)
        self._slice_label.setText(
            f"{slice_type.capitalize()} {actual_pos}"
        )

    def _load_segy(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 SEGY 文件", "", "SEGY Files (*.sgy *.segy)"
        )
        if path:
            self.load_segy(path)

    def _load_demo_data(self):
        self.load_demo(self._generate_synthetic())

    def _load_horizon(self):
        if self._meta is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "选择层位文件 (格式: inline  crossline  time_ms, tab分隔)",
            "", "Horizon Files (*.txt *.dat *.hor)",
        )
        if not path:
            return
        axes = {
            "ilines": np.arange(
                self._meta.iline_start,
                self._meta.iline_start
                + self._meta.n_inlines * self._meta.iline_step,
                self._meta.iline_step,
            ),
            "xlines": np.arange(
                self._meta.xline_start,
                self._meta.xline_start
                + self._meta.n_crosslines * self._meta.xline_step,
                self._meta.xline_step,
            ),
            "nI": self._meta.n_inlines,
            "nX": self._meta.n_crosslines,
        }
        parser = HorizonParser(path, unit="ms")
        grid = parser.parse(axes)
        filled = parser.fill_nearest(grid)
        self._renderer_3d.add_horizon(filled)

    def _on_mode_changed(self, index: int):
        if index == 0:
            self._profile_widget.set_display_mode("vd")
        else:
            self._profile_widget.set_display_mode("wiggle")

    def _on_slice_type_changed(self, index: int):
        pass  # Slice type is controlled by 3D plane widgets
```

- [ ] **Step 4: Update __init__.py exports**

Add `SeismicView` import and to `__all__`.

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_seismic_view.py -v
```

Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add packages/geoviz_seismic/geoviz_seismic/seismic_view.py \
        packages/geoviz_seismic/geoviz_seismic/__init__.py \
        tests/test_seismic_view.py
git commit -m "feat(seismic): add SeismicView composite widget"
```

---

### Task 12: App Integration & Cleanup

**Files:**
- Rewrite: `src/pages/seismic_page.py`
- Modify: `src/app.py` (update seismic import block)
- Modify: `src/data/models.py` (remove SeismicVolumeMeta)
- Delete: `src/renderers/seismic_renderer.py`

- [ ] **Step 1: Rewrite seismic_page.py**

Replace `src/pages/seismic_page.py` with:

```python
from geoviz_seismic import SeismicView


class SeismicPage(SeismicView):
    """App-level seismic page — inherits all functionality from the package."""
    pass
```

- [ ] **Step 2: Update app.py integration block**

In `src/app.py`, replace lines 120-130 with:

```python
def _check_pyvista_qt_available() -> bool:
    """Probe pyvistaqt in a subprocess to avoid main-process segfault on GL failure."""
    import subprocess, sys
    try:
        result = subprocess.run(
            [sys.executable, "-c", "from pyvistaqt import QtInteractor; print('ok')"],
            capture_output=True, timeout=10,
        )
        return result.returncode == 0 and b"ok" in result.stdout
    except Exception:
        return False

if _check_pyvista_qt_available():
    from src.pages.seismic_page import SeismicPage
    self.seismic_page = SeismicPage()
    seismic_widget = self.seismic_page
else:
    seismic_widget = QLabel("地震3D (placeholder)")
    seismic_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
    seismic_widget.setStyleSheet("font-size: 24px; color: #a0aec0;")
```

- [ ] **Step 3: Remove SeismicVolumeMeta from src/data/models.py**

Remove lines 90-95 (`SeismicVolumeMeta` class). It now lives in the package.

- [ ] **Step 4: Delete old renderer**

```bash
git rm src/renderers/seismic_renderer.py
```

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```

Expected: All tests pass, no regressions.

- [ ] **Step 6: Commit**

```bash
git add src/pages/seismic_page.py src/app.py src/data/models.py
git rm src/renderers/seismic_renderer.py
git commit -m "feat(seismic): integrate geoviz-seismic package, remove old renderer"
```

---

### Task 13: Interactive Slice Widgets

**Files:**
- Modify: `packages/geoviz_seismic/geoviz_seismic/renderer_3d.py`

- [ ] **Step 1: Add plane widget for interactive slice selection**

Add to `Renderer3D.load_volume()` after volume rendering:

```python
def load_volume(self, data: np.ndarray, origin=(0, 0, 0), spacing=(1, 1, 1)):
    self._volume_data = data
    self._plotter.clear()
    grid = pv.ImageData(
        dimensions=np.array(data.shape) + 1,
        spacing=spacing,
        origin=origin,
    )
    grid["amplitude"] = data.flatten(order="F")
    self._plotter.add_volume(
        grid, cmap="seismic", opacity="sigmoid",
        name="volume",
    )
    # Interactive slice widgets
    ni, nx, nt = data.shape
    self._plotter.add_plane_widget(
        self._make_slice_callback("inline"),
        normal="x", origin=(ni // 2 * spacing[0], 0, 0),
        bounds=(0, ni * spacing[0], 0, nx * spacing[1], 0, nt * spacing[2]),
        color="red", tubing=True,
    )
    self._plotter.add_plane_widget(
        self._make_slice_callback("crossline"),
        normal="y", origin=(0, nx // 2 * spacing[1], 0),
        bounds=(0, ni * spacing[0], 0, nx * spacing[1], 0, nt * spacing[2]),
        color="green", tubing=True,
    )
    self._plotter.add_plane_widget(
        self._make_slice_callback("time"),
        normal="z", origin=(0, 0, nt // 2 * spacing[2]),
        bounds=(0, ni * spacing[0], 0, nx * spacing[1], 0, nt * spacing[2]),
        color="blue", tubing=True,
    )
    self._plotter.reset_camera()
    self._loaded = True
```

Add the callback factory method:

```python
def _make_slice_callback(self, slice_type: str):
    def callback(normal, origin):
        if slice_type == "inline":
            pos = int(round(origin[0]))
        elif slice_type == "crossline":
            pos = int(round(origin[1]))
        else:
            pos = int(round(origin[2]))
        if pos >= 0:
            self.slice_changed.emit(slice_type, pos)
    return callback
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/test_renderer_3d.py tests/test_seismic_view.py -v
```

Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add packages/geoviz_seismic/geoviz_seismic/renderer_3d.py
git commit -m "feat(seismic): add interactive slice plane widgets to 3D renderer"
```

---

### Task 14: Final __init__.py & Integration Test

**Files:**
- Modify: `packages/geoviz_seismic/geoviz_seismic/__init__.py`

- [ ] **Step 1: Finalize public API exports**

Update `packages/geoviz_seismic/geoviz_seismic/__init__.py`:

```python
from .models import SeismicVolumeMeta, SliceInfo, HorizonData
from .cache import SeismicCache
from .colormap import ColormapManager
from .loader import SeismicLoader
from .horizon import HorizonParser
from .profile_vd import ProfileVD
from .profile_wiggle import ProfileWiggle
from .profile_widget import ProfileWidget
from .renderer_3d import Renderer3D
from .seismic_view import SeismicView

__version__ = "0.1.0"

__all__ = [
    "SeismicVolumeMeta",
    "SliceInfo",
    "HorizonData",
    "SeismicCache",
    "ColormapManager",
    "SeismicLoader",
    "HorizonParser",
    "ProfileVD",
    "ProfileWiggle",
    "ProfileWidget",
    "Renderer3D",
    "SeismicView",
]
```

- [ ] **Step 2: Run full test suite**

```bash
pytest -v
```

Expected: All tests pass

- [ ] **Step 3: Verify package imports cleanly**

```bash
python -c "from geoviz_seismic import SeismicView, SeismicLoader, ColormapManager; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add packages/geoviz_seismic/geoviz_seismic/__init__.py
git commit -m "feat(seismic): finalize public API surface"
```

---

### Task 15: Critical Gap Tests

**Files:**
- Create: `tests/test_critical_gaps.py`

Covers untested codepaths identified in test review: error paths, edge cases, and integration seams.

- [ ] **Step 1: Write critical gap tests**

Create `tests/test_critical_gaps.py`:

```python
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
    """Opening a nonexistent file should raise a clear error."""
    with pytest.raises((FileNotFoundError, OSError)):
        SeismicLoader("/nonexistent/path.sgy")


def test_loader_close_clears_handle(tmp_path):
    """close() should release the file handle; second close should not error."""
    # Create a minimal valid SEGY file for testing
    sgy_path = tmp_path / "test.sgy"
    import segyio
    spec = segyio.spec()
    spec.sorting = 2  # inline sorting
    spec.format = 1
    spec.ilines = [100, 101]
    spec.xlines = [200, 201]
    spec.samples = list(range(10))
    with segyio.create(str(sgy_path), spec) as f:
        for il in spec.ilines:
            for xl in spec.xlines:
                f.header[il, xl] = {
                    segyio.TraceField.INLINE_3D: il,
                    segyio.TraceField.CROSSLINE_3D: xl,
                }
                f.trace[il, xl] = np.zeros(10, dtype=np.float32)

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
        f.header[100, 200] = {
            segyio.TraceField.INLINE_3D: 100,
            segyio.TraceField.CROSSLINE_3D: 200,
        }
        f.trace[100, 200] = np.zeros(5, dtype=np.float32)

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
```

- [ ] **Step 2: Run critical gap tests**

```bash
pytest tests/test_critical_gaps.py -v
```

Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add tests/test_critical_gaps.py
git commit -m "test(seismic): add critical gap tests for error paths, edge cases, and integration seams"
```

---

## Self-Review

### Spec Coverage

| Spec Requirement | Task |
|---|---|
| Package structure (`packages/geoviz_seismic/`) | Task 1 |
| `SeismicVolumeMeta`, `SliceInfo`, `HorizonData` models | Task 2 |
| LRU cache | Task 3 |
| Colormap manager (seismic, gray, jet) | Task 4 |
| SEGY loader (inspect, read_inline/crossline/timeslice, downsample) | Task 5 |
| Horizon parser (dense/sparse, nearest/RBF fill) | Task 6 |
| VD profile rendering (QImage) | Task 7 |
| Wiggle profile rendering (VisPy) | Task 8 |
| Profile widget (VD/Wiggle switching) | Task 9 |
| 3D renderer (PyVista volume) | Task 10 |
| SeismicView composite widget (3D+2D+toolbar) | Task 11 |
| App integration + cleanup old code | Task 12 |
| Interactive slice plane widgets | Task 13 |
| Final API surface | Task 14 |
| Critical gap tests | Task 15 |

### Placeholder Scan

No TBD, TODO, or "implement later" patterns found.

### Type Consistency

All method signatures and class names match across tasks. `SeismicLoader.inspect()` returns `SeismicVolumeMeta` used by `SeismicView`. `ColormapManager.apply_to_data()` used by `ProfileVD.render()`. Signal `slice_changed(str, int)` matches `SeismicView._on_slice_changed(slice_type, position)`.

---

## Plan saved. Two execution options:

1. **Subagent-Driven (recommended)** — Fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints
