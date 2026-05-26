# MapPage QPainter Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace MapPage's QWebEngineView + MapLibre GL renderer with a native QPainter pipeline in a new `packages/geoviz_map/` independent package, achieving 1:1 visual/interaction parity.

**Architecture:** New independent package mirrors `geoviz_well_log` / `geoviz_seismic` structure. `MapCanvas(QWidget)` composes 6 layers (background, graticule, world polygons, china polygons, reference labels, wells) sharing a `MapViewport` that does Web Mercator projection. `ZoomPanHandler` drives viewport state. Hit-test runs reverse-order across layers; `WellsLayer` emits the well name. Spec: `docs/superpowers/specs/2026-05-27-map-page-qpainter-migration-design.md`.

**Tech Stack:** PySide6 (`QPainter`, `QPainterPath`, `QPointF`, `Signal`), pydantic (data models), Python `math` (Web Mercator), pytest + pytest-qt.

---

## File Structure

**Create:**
- `packages/geoviz_map/pyproject.toml`
- `packages/geoviz_map/geoviz_map/__init__.py`
- `packages/geoviz_map/geoviz_map/models.py`
- `packages/geoviz_map/geoviz_map/projection.py`
- `packages/geoviz_map/geoviz_map/viewport.py`
- `packages/geoviz_map/geoviz_map/zoom_pan.py`
- `packages/geoviz_map/geoviz_map/canvas.py`
- `packages/geoviz_map/geoviz_map/layers/__init__.py`
- `packages/geoviz_map/geoviz_map/layers/base.py`
- `packages/geoviz_map/geoviz_map/layers/background.py`
- `packages/geoviz_map/geoviz_map/layers/graticule.py`
- `packages/geoviz_map/geoviz_map/layers/geojson_polygon.py`
- `packages/geoviz_map/geoviz_map/layers/reference.py`
- `packages/geoviz_map/geoviz_map/layers/wells.py`
- `tests/map/__init__.py`
- `tests/map/test_projection.py`
- `tests/map/test_viewport.py`
- `tests/map/test_zoom_pan.py`
- `tests/map/test_layer_background.py`
- `tests/map/test_layer_graticule.py`
- `tests/map/test_layer_polygon.py`
- `tests/map/test_layer_reference.py`
- `tests/map/test_layer_wells.py`
- `tests/test_map_canvas.py`
- `tests/test_map_visual_parity.py`
- `tests/golden/map_canvas_default.png` (generated, committed)

**Modify:**
- `pyproject.toml` — register new workspace member
- `src/pages/map/page.py` — swap MapRenderer for MapCanvas
- `CLAUDE.md` — update architecture + project layout
- `README.md` — update project structure
- `CHANGELOG.md` — `[Unreleased]` entry

**Delete (Phase 4):**
- `src/pages/map/renderer.py`
- `src/pages/map/assets/maplibre-gl.js`
- `src/pages/map/assets/maplibre-gl.css`

---

## Phase 1 — Package skeleton, projection, viewport, interaction

### Task 1: Scaffold `geoviz_map` package and register workspace

**Files:**
- Create: `packages/geoviz_map/pyproject.toml`
- Create: `packages/geoviz_map/geoviz_map/__init__.py`
- Modify: `pyproject.toml` (root) — add workspace member + source

- [ ] **Step 1: Create `packages/geoviz_map/pyproject.toml`**

```toml
[project]
name = "geoviz-map"
version = "0.1.0"
description = "QPainter-based geographic map visualization package for PySide6"
readme = "README.md"
license = "MIT"
authors = [{ name = "Kevin", email = "kevin@example.com" }]
requires-python = ">=3.10"
dependencies = [
    "PySide6",
    "pydantic",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-qt"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["geoviz_map"]

[tool.hatch.build.targets.sdist]
include = ["/geoviz_map"]
```

- [ ] **Step 2: Create `packages/geoviz_map/geoviz_map/__init__.py`** (empty for now; populated in later tasks)

```python
"""geoviz_map — QPainter-based geographic map visualization for PySide6."""
```

- [ ] **Step 3: Register workspace member in root `pyproject.toml`**

In root `pyproject.toml`, modify the `[tool.uv.workspace]` section:

```toml
[tool.uv.workspace]
members = [
    "packages/geoviz_well_log",
    "packages/geoviz_seismic",
    "packages/geoviz_map",
]
```

And modify the `[tool.uv.sources]` section:

```toml
[tool.uv.sources]
geoviz-well-log = { workspace = true }
geoviz-seismic = { workspace = true }
geoviz-map = { workspace = true }
```

And modify the `[project] dependencies` list to add `"geoviz-map",` after `"geoviz-seismic",`.

- [ ] **Step 4: Reinstall workspace**

Run: `source .venv/bin/activate && pip install -e ".[dev]"`
Expected: `Successfully installed geoviz-map-0.1.0 ...` (among others)

- [ ] **Step 5: Sanity-import the new package**

Run: `source .venv/bin/activate && python -c "import geoviz_map; print(geoviz_map.__doc__)"`
Expected: `geoviz_map — QPainter-based geographic map visualization for PySide6.`

- [ ] **Step 6: Commit**

```bash
git add packages/geoviz_map/ pyproject.toml
git commit -m "feat(map): scaffold geoviz_map package and register workspace"
```

---

### Task 2: Data models — `WellMarker` and `ReferenceLabel`

**Files:**
- Create: `packages/geoviz_map/geoviz_map/models.py`
- Create: `tests/map/__init__.py` (empty)
- Test: `tests/map/test_models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/map/__init__.py` as an empty file.

Create `tests/map/test_models.py`:

```python
import pytest

from geoviz_map.models import ReferenceLabel, WellMarker


def test_well_marker_holds_name_color_data_flag():
    m = WellMarker(name="HZ19-1", lng=114.5, lat=20.1, color="#ef4444", has_data=True)
    assert m.name == "HZ19-1"
    assert m.lng == 114.5
    assert m.lat == 20.1
    assert m.color == "#ef4444"
    assert m.has_data is True


def test_well_marker_has_data_defaults_false():
    m = WellMarker(name="X", lng=100.0, lat=20.0, color="#000000")
    assert m.has_data is False


def test_reference_label_kind_must_be_city_or_capital_or_sea():
    ReferenceLabel(name="北京", lng=116.4, lat=39.9, kind="capital")
    ReferenceLabel(name="上海", lng=121.5, lat=31.2, kind="city")
    ReferenceLabel(name="南海", lng=115.5, lat=20.2, kind="sea")
    with pytest.raises(ValueError):
        ReferenceLabel(name="X", lng=0, lat=0, kind="invalid")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/map/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'geoviz_map.models'`

- [ ] **Step 3: Write implementation**

Create `packages/geoviz_map/geoviz_map/models.py`:

```python
"""Data models for geoviz_map."""
from typing import Literal

from pydantic import BaseModel


class WellMarker(BaseModel):
    """A single well point on the map."""

    name: str
    lng: float
    lat: float
    color: str  # CSS-style hex, e.g. "#ef4444"
    has_data: bool = False


class ReferenceLabel(BaseModel):
    """A non-interactive geographic reference label (city, sea, capital)."""

    name: str
    lng: float
    lat: float
    kind: Literal["city", "capital", "sea"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/map/test_models.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_map/geoviz_map/models.py tests/map/__init__.py tests/map/test_models.py
git commit -m "feat(map): add WellMarker and ReferenceLabel models"
```

---

### Task 3: Web Mercator projection

**Files:**
- Create: `packages/geoviz_map/geoviz_map/projection.py`
- Test: `tests/map/test_projection.py`

- [ ] **Step 1: Write the failing test**

Create `tests/map/test_projection.py`:

```python
import math

import pytest

from geoviz_map.projection import (
    MAX_LAT,
    R_EARTH,
    lnglat_to_world,
    world_to_lnglat,
)


def test_zero_lng_lat_maps_to_origin():
    x, y = lnglat_to_world(0.0, 0.0)
    assert x == pytest.approx(0.0, abs=1e-6)
    assert y == pytest.approx(0.0, abs=1e-6)


def test_round_trip_known_point_huizhou():
    # Huizhou ~114.4°E, 23.1°N
    lng, lat = 114.4158, 23.1109
    x, y = lnglat_to_world(lng, lat)
    lng2, lat2 = world_to_lnglat(x, y)
    assert lng2 == pytest.approx(lng, abs=1e-9)
    assert lat2 == pytest.approx(lat, abs=1e-9)


def test_one_degree_lng_equals_R_times_radian():
    x, _ = lnglat_to_world(1.0, 0.0)
    assert x == pytest.approx(math.radians(1.0) * R_EARTH, rel=1e-12)


def test_polar_latitude_raises():
    with pytest.raises(ValueError):
        lnglat_to_world(0.0, MAX_LAT + 0.01)
    with pytest.raises(ValueError):
        lnglat_to_world(0.0, -MAX_LAT - 0.01)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/map/test_projection.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'geoviz_map.projection'`

- [ ] **Step 3: Write implementation**

Create `packages/geoviz_map/geoviz_map/projection.py`:

```python
"""Web Mercator projection (matches MapLibre GL internal projection)."""
import math

R_EARTH = 6378137.0  # WGS84 / Web Mercator earth radius (meters)
MAX_LAT = 85.05112878  # Web Mercator latitude clamp


def lnglat_to_world(lng: float, lat: float) -> tuple[float, float]:
    """Convert lng/lat (degrees) to Web Mercator world coordinates (meters)."""
    if not -MAX_LAT <= lat <= MAX_LAT:
        raise ValueError(f"latitude {lat} outside Web Mercator range ±{MAX_LAT}")
    x = math.radians(lng) * R_EARTH
    y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * R_EARTH
    return x, y


def world_to_lnglat(x: float, y: float) -> tuple[float, float]:
    """Inverse of lnglat_to_world."""
    lng = math.degrees(x / R_EARTH)
    lat = math.degrees(2 * math.atan(math.exp(y / R_EARTH)) - math.pi / 2)
    return lng, lat
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/map/test_projection.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_map/geoviz_map/projection.py tests/map/test_projection.py
git commit -m "feat(map): add Web Mercator projection"
```

---

### Task 4: `MapViewport` — center + zoom + screen mapping

**Files:**
- Create: `packages/geoviz_map/geoviz_map/viewport.py`
- Test: `tests/map/test_viewport.py`

- [ ] **Step 1: Write the failing test**

Create `tests/map/test_viewport.py`:

```python
import math

import pytest

from geoviz_map.viewport import MapViewport


def test_center_maps_to_screen_center():
    vp = MapViewport(center_lng=118.0, center_lat=25.0, zoom=7.5,
                     width=1200, height=800)
    pt = vp.lnglat_to_screen(118.0, 25.0)
    assert pt.x() == pytest.approx(600.0)
    assert pt.y() == pytest.approx(400.0)


def test_zoom_plus_one_doubles_pixel_distance():
    vp_a = MapViewport(118.0, 25.0, zoom=6.0, width=1200, height=800)
    vp_b = MapViewport(118.0, 25.0, zoom=7.0, width=1200, height=800)
    pa = vp_a.lnglat_to_screen(119.0, 25.0)
    pb = vp_b.lnglat_to_screen(119.0, 25.0)
    dx_a = pa.x() - 600.0
    dx_b = pb.x() - 600.0
    assert dx_b == pytest.approx(dx_a * 2.0, rel=1e-9)


def test_screen_to_lnglat_inverts_lnglat_to_screen():
    vp = MapViewport(118.0, 25.0, zoom=7.5, width=1200, height=800)
    src_lng, src_lat = 115.0, 22.0
    pt = vp.lnglat_to_screen(src_lng, src_lat)
    lng2, lat2 = vp.screen_to_lnglat(pt)
    assert lng2 == pytest.approx(src_lng, abs=1e-6)
    assert lat2 == pytest.approx(src_lat, abs=1e-6)


def test_pan_world_shifts_center():
    vp = MapViewport(118.0, 25.0, zoom=7.5, width=1200, height=800)
    initial_center_x = vp.center_world[0]
    vp.pan_world(dx=1000.0, dy=0.0)
    assert vp.center_world[0] == pytest.approx(initial_center_x + 1000.0)


def test_world_bbox_is_within_lng_range():
    vp = MapViewport(118.0, 25.0, zoom=7.5, width=1200, height=800)
    bbox = vp.world_bbox()
    # bbox is (min_x, min_y, max_x, max_y)
    assert bbox[0] < bbox[2]
    assert bbox[1] < bbox[3]
    # Center should be inside
    cx, cy = vp.center_world
    assert bbox[0] <= cx <= bbox[2]
    assert bbox[1] <= cy <= bbox[3]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/map/test_viewport.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'geoviz_map.viewport'`

- [ ] **Step 3: Write implementation**

Create `packages/geoviz_map/geoviz_map/viewport.py`:

```python
"""MapViewport — center + zoom + screen-pixel mapping (MapLibre-compatible)."""
import math

from PySide6.QtCore import QPointF

from geoviz_map.projection import R_EARTH, lnglat_to_world, world_to_lnglat


class MapViewport:
    """Tracks the visible world region.

    Coordinate systems:
      lng/lat   — geographic (WGS84 degrees)
      world     — Web Mercator meters (continuous)
      screen    — widget pixels (origin top-left, y-down)

    Zoom convention matches MapLibre GL: at zoom z, the world is rendered
    at 256 * 2^z pixels per world circumference (2π * R).
    """

    def __init__(self, center_lng: float, center_lat: float, zoom: float,
                 width: int, height: int):
        self.center_world = lnglat_to_world(center_lng, center_lat)
        self.zoom = zoom
        self.width = width
        self.height = height

    @property
    def scale(self) -> float:
        """Pixels per world meter."""
        return 256.0 * (2 ** self.zoom) / (2 * math.pi * R_EARTH)

    def world_to_screen(self, x: float, y: float) -> QPointF:
        s = self.scale
        sx = (x - self.center_world[0]) * s + self.width / 2
        sy = (self.center_world[1] - y) * s + self.height / 2  # y flipped
        return QPointF(sx, sy)

    def screen_to_world(self, pt: QPointF) -> tuple[float, float]:
        s = self.scale
        x = (pt.x() - self.width / 2) / s + self.center_world[0]
        y = self.center_world[1] - (pt.y() - self.height / 2) / s
        return x, y

    def lnglat_to_screen(self, lng: float, lat: float) -> QPointF:
        return self.world_to_screen(*lnglat_to_world(lng, lat))

    def screen_to_lnglat(self, pt: QPointF) -> tuple[float, float]:
        x, y = self.screen_to_world(pt)
        return world_to_lnglat(x, y)

    def pan_world(self, dx: float, dy: float) -> None:
        """Shift the center by world-meter delta."""
        cx, cy = self.center_world
        self.center_world = (cx + dx, cy + dy)

    def pan_pixels(self, dx_px: float, dy_px: float) -> None:
        """Shift the center by screen-pixel delta (drag-pan)."""
        s = self.scale
        self.pan_world(-dx_px / s, dy_px / s)  # drag right → world left

    def world_bbox(self) -> tuple[float, float, float, float]:
        """(min_x, min_y, max_x, max_y) of currently visible world region."""
        s = self.scale
        half_w = self.width / 2 / s
        half_h = self.height / 2 / s
        cx, cy = self.center_world
        return (cx - half_w, cy - half_h, cx + half_w, cy + half_h)

    def resize(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/map/test_viewport.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_map/geoviz_map/viewport.py tests/map/test_viewport.py
git commit -m "feat(map): add MapViewport with Web Mercator screen mapping"
```

---

### Task 5: `ZoomPanHandler` — drag pan + cursor-anchored wheel zoom

**Files:**
- Create: `packages/geoviz_map/geoviz_map/zoom_pan.py`
- Test: `tests/map/test_zoom_pan.py`

- [ ] **Step 1: Write the failing test**

Create `tests/map/test_zoom_pan.py`:

```python
import pytest
from PySide6.QtCore import QPointF

from geoviz_map.viewport import MapViewport
from geoviz_map.zoom_pan import ZoomPanHandler


def test_drag_pan_moves_center_opposite_to_drag():
    vp = MapViewport(118.0, 25.0, zoom=7.5, width=1200, height=800)
    initial_lng = 118.0
    handler = ZoomPanHandler(vp)
    handler.start_drag(QPointF(600, 400))
    handler.update_drag(QPointF(500, 400))  # drag left 100 px
    # Drag left → map moves left → center longitude increases
    new_lng = handler.viewport.screen_to_lnglat(QPointF(600, 400))[0]
    assert new_lng > initial_lng


def test_wheel_zoom_anchors_at_cursor():
    vp = MapViewport(118.0, 25.0, zoom=7.0, width=1200, height=800)
    handler = ZoomPanHandler(vp)
    cursor = QPointF(900, 300)  # off-center
    before = vp.screen_to_lnglat(cursor)
    handler.wheel_zoom(cursor, delta_steps=1.0)  # zoom in by 1 level
    after = handler.viewport.screen_to_lnglat(cursor)
    assert after[0] == pytest.approx(before[0], abs=1e-6)
    assert after[1] == pytest.approx(before[1], abs=1e-6)
    assert handler.viewport.zoom == pytest.approx(8.0)


def test_zoom_clamps_to_min_max():
    vp = MapViewport(118.0, 25.0, zoom=5.0, width=1200, height=800)
    handler = ZoomPanHandler(vp, min_zoom=4.0, max_zoom=10.0)
    handler.wheel_zoom(QPointF(600, 400), delta_steps=-20.0)
    assert handler.viewport.zoom == 4.0
    handler.wheel_zoom(QPointF(600, 400), delta_steps=20.0)
    assert handler.viewport.zoom == 10.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/map/test_zoom_pan.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'geoviz_map.zoom_pan'`

- [ ] **Step 3: Write implementation**

Create `packages/geoviz_map/geoviz_map/zoom_pan.py`:

```python
"""ZoomPanHandler — mouse drag pan + cursor-anchored wheel zoom."""
from __future__ import annotations

from PySide6.QtCore import QPointF

from geoviz_map.viewport import MapViewport


class ZoomPanHandler:
    """Stateless wrt Qt events — call from widget event handlers."""

    def __init__(self, viewport: MapViewport, min_zoom: float = 2.0,
                 max_zoom: float = 18.0):
        self.viewport = viewport
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom
        self._drag_anchor: QPointF | None = None

    # Drag pan -----------------------------------------------------------
    def start_drag(self, pt: QPointF) -> None:
        self._drag_anchor = QPointF(pt)

    def update_drag(self, pt: QPointF) -> None:
        if self._drag_anchor is None:
            return
        dx = pt.x() - self._drag_anchor.x()
        dy = pt.y() - self._drag_anchor.y()
        self.viewport.pan_pixels(dx, dy)
        self._drag_anchor = QPointF(pt)

    def end_drag(self) -> None:
        self._drag_anchor = None

    def is_dragging(self) -> bool:
        return self._drag_anchor is not None

    # Wheel zoom ---------------------------------------------------------
    def wheel_zoom(self, cursor_screen: QPointF, delta_steps: float) -> None:
        """Zoom by `delta_steps` levels (positive = zoom in), anchored at cursor.

        The lng/lat under `cursor_screen` is invariant before and after.
        """
        before_world = self.viewport.screen_to_world(cursor_screen)
        new_zoom = max(self.min_zoom,
                       min(self.max_zoom, self.viewport.zoom + delta_steps))
        if new_zoom == self.viewport.zoom:
            return
        self.viewport.zoom = new_zoom
        # Re-anchor: shift center so cursor stays over the same world point
        after_world = self.viewport.screen_to_world(cursor_screen)
        dx = before_world[0] - after_world[0]
        dy = before_world[1] - after_world[1]
        self.viewport.pan_world(dx, dy)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/map/test_zoom_pan.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_map/geoviz_map/zoom_pan.py tests/map/test_zoom_pan.py
git commit -m "feat(map): add ZoomPanHandler with cursor-anchored wheel zoom"
```

---

## Phase 2 — Rendering layers

### Task 6: `MapLayer` abstract base + layers package

**Files:**
- Create: `packages/geoviz_map/geoviz_map/layers/__init__.py`
- Create: `packages/geoviz_map/geoviz_map/layers/base.py`
- Test: `tests/map/test_layer_base.py`

- [ ] **Step 1: Write the failing test**

Create `tests/map/test_layer_base.py`:

```python
import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainter

from geoviz_map.layers.base import MapLayer
from geoviz_map.viewport import MapViewport


def test_layer_is_abstract_paint_required():
    with pytest.raises(TypeError):
        MapLayer()  # type: ignore[abstract]


def test_default_hit_test_returns_none():
    class Dummy(MapLayer):
        def paint(self, painter: QPainter, viewport: MapViewport) -> None:
            return None

    vp = MapViewport(118.0, 25.0, zoom=7.5, width=1200, height=800)
    assert Dummy().hit_test(QPointF(0, 0), vp) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/map/test_layer_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'geoviz_map.layers'`

- [ ] **Step 3: Write implementation**

Create `packages/geoviz_map/geoviz_map/layers/__init__.py`:

```python
"""geoviz_map layers — composable rendering units."""
```

Create `packages/geoviz_map/geoviz_map/layers/base.py`:

```python
"""MapLayer abstract base."""
from abc import ABC, abstractmethod

from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainter

from geoviz_map.viewport import MapViewport


class MapLayer(ABC):
    """One rendering pass over the viewport.

    Layers are painted in registration order; hit-test runs reverse order
    (topmost first), so interactive layers should be appended last.
    """

    @abstractmethod
    def paint(self, painter: QPainter, viewport: MapViewport) -> None: ...

    def hit_test(self, screen_pt: QPointF,
                 viewport: MapViewport) -> str | None:
        """Override for interactive layers. Default: no hit."""
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/map/test_layer_base.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_map/geoviz_map/layers/ tests/map/test_layer_base.py
git commit -m "feat(map): add MapLayer abstract base"
```

---

### Task 7: `BackgroundLayer` — solid fill color

**Files:**
- Create: `packages/geoviz_map/geoviz_map/layers/background.py`
- Test: `tests/map/test_layer_background.py`

- [ ] **Step 1: Write the failing test**

Create `tests/map/test_layer_background.py`:

```python
from PySide6.QtGui import QImage, QPainter

from geoviz_map.layers.background import BackgroundLayer
from geoviz_map.viewport import MapViewport


def test_background_fills_with_specified_color():
    img = QImage(100, 80, QImage.Format.Format_RGB32)
    img.fill(0)
    vp = MapViewport(118.0, 25.0, zoom=7.5, width=100, height=80)
    layer = BackgroundLayer(color="#cbebfb")
    painter = QPainter(img)
    layer.paint(painter, vp)
    painter.end()

    center = img.pixelColor(50, 40)
    assert center.red() == 0xCB
    assert center.green() == 0xEB
    assert center.blue() == 0xFB
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/map/test_layer_background.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'geoviz_map.layers.background'`

- [ ] **Step 3: Write implementation**

Create `packages/geoviz_map/geoviz_map/layers/background.py`:

```python
"""BackgroundLayer — solid color fill (e.g. ocean blue)."""
from PySide6.QtGui import QColor, QPainter

from geoviz_map.layers.base import MapLayer
from geoviz_map.viewport import MapViewport


class BackgroundLayer(MapLayer):
    def __init__(self, color: str = "#cbebfb"):
        self.color = QColor(color)

    def paint(self, painter: QPainter, viewport: MapViewport) -> None:
        painter.fillRect(0, 0, viewport.width, viewport.height, self.color)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/map/test_layer_background.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_map/geoviz_map/layers/background.py tests/map/test_layer_background.py
git commit -m "feat(map): add BackgroundLayer"
```

---

### Task 8: `GraticuleLayer` — lng/lat dashed grid

**Files:**
- Create: `packages/geoviz_map/geoviz_map/layers/graticule.py`
- Test: `tests/map/test_layer_graticule.py`

The current MapLibre implementation draws lines every 2° from 104°→126° E and 14°→42° N with `#0284c7` opacity 0.12, width 0.8, dasharray [4, 4]. Replicate.

- [ ] **Step 1: Write the failing test**

Create `tests/map/test_layer_graticule.py`:

```python
from PySide6.QtGui import QImage, QPainter

from geoviz_map.layers.graticule import GraticuleLayer
from geoviz_map.viewport import MapViewport


def test_graticule_paints_lines_at_2deg_steps():
    """Centered at (115°E, 28°N) zoom 7.5 — graticule lines should appear."""
    img = QImage(1200, 800, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)  # white background
    vp = MapViewport(115.0, 28.0, zoom=7.5, width=1200, height=800)
    layer = GraticuleLayer()
    painter = QPainter(img)
    layer.paint(painter, vp)
    painter.end()

    # At least one non-white pixel must exist (a graticule line was drawn)
    non_white = 0
    for y in range(0, 800, 10):
        for x in range(0, 1200, 10):
            c = img.pixelColor(x, y)
            if c.red() < 255 or c.green() < 255 or c.blue() < 255:
                non_white += 1
                break
    assert non_white > 0


def test_graticule_uses_configured_lng_lat_range():
    layer = GraticuleLayer(lng_min=100, lng_max=130, lng_step=5,
                           lat_min=10, lat_max=40, lat_step=5)
    # Expected lng lines: 100, 105, 110, 115, 120, 125, 130 → 7
    assert layer.lng_lines() == [100, 105, 110, 115, 120, 125, 130]
    assert layer.lat_lines() == [10, 15, 20, 25, 30, 35, 40]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/map/test_layer_graticule.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create `packages/geoviz_map/geoviz_map/layers/graticule.py`:

```python
"""GraticuleLayer — lng/lat dashed grid."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen

from geoviz_map.layers.base import MapLayer
from geoviz_map.viewport import MapViewport


class GraticuleLayer(MapLayer):
    def __init__(self,
                 lng_min: float = 104, lng_max: float = 126, lng_step: float = 2,
                 lat_min: float = 14, lat_max: float = 42, lat_step: float = 2,
                 color: str = "#0284c7", opacity: float = 0.12,
                 width: float = 0.8):
        self.lng_min = lng_min
        self.lng_max = lng_max
        self.lng_step = lng_step
        self.lat_min = lat_min
        self.lat_max = lat_max
        self.lat_step = lat_step
        self.color = QColor(color)
        self.color.setAlphaF(opacity)
        self.width = width

    def lng_lines(self) -> list[float]:
        out: list[float] = []
        v = self.lng_min
        while v <= self.lng_max + 1e-9:
            out.append(round(v, 6))
            v += self.lng_step
        return out

    def lat_lines(self) -> list[float]:
        out: list[float] = []
        v = self.lat_min
        while v <= self.lat_max + 1e-9:
            out.append(round(v, 6))
            v += self.lat_step
        return out

    def paint(self, painter: QPainter, viewport: MapViewport) -> None:
        pen = QPen(self.color, self.width)
        pen.setStyle(Qt.PenStyle.CustomDashLine)
        pen.setDashPattern([4.0, 4.0])
        painter.setPen(pen)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Vertical (lng) lines span lat_min..lat_max
        for lng in self.lng_lines():
            p1 = viewport.lnglat_to_screen(lng, self.lat_min)
            p2 = viewport.lnglat_to_screen(lng, self.lat_max)
            painter.drawLine(p1, p2)

        # Horizontal (lat) lines span lng_min..lng_max
        for lat in self.lat_lines():
            p1 = viewport.lnglat_to_screen(self.lng_min, lat)
            p2 = viewport.lnglat_to_screen(self.lng_max, lat)
            painter.drawLine(p1, p2)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/map/test_layer_graticule.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_map/geoviz_map/layers/graticule.py tests/map/test_layer_graticule.py
git commit -m "feat(map): add GraticuleLayer with dashed lng/lat grid"
```

---

### Task 9: `GeoJsonPolygonLayer` — World/China filled polygons with viewport culling

**Files:**
- Create: `packages/geoviz_map/geoviz_map/layers/geojson_polygon.py`
- Test: `tests/map/test_layer_polygon.py`

- [ ] **Step 1: Write the failing test**

Create `tests/map/test_layer_polygon.py`:

```python
from PySide6.QtGui import QImage, QPainter

from geoviz_map.layers.geojson_polygon import GeoJsonPolygonLayer
from geoviz_map.viewport import MapViewport


SQUARE_AROUND_HUIZHOU = {
    "type": "FeatureCollection",
    "features": [{
        "type": "Feature",
        "properties": {"ISO_A3": "CHN"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [114.0, 22.0], [115.0, 22.0],
                [115.0, 23.5], [114.0, 23.5], [114.0, 22.0],
            ]],
        },
    }],
}

POLYGON_FAR_AWAY = {
    "type": "FeatureCollection",
    "features": [{
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-180.0, -10.0], [-170.0, -10.0],
                [-170.0, 0.0], [-180.0, 0.0], [-180.0, -10.0],
            ]],
        },
    }],
}


def test_polygon_in_viewport_fills_center_pixels():
    img = QImage(400, 400, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)
    vp = MapViewport(114.5, 22.75, zoom=8.0, width=400, height=400)
    layer = GeoJsonPolygonLayer(SQUARE_AROUND_HUIZHOU,
                                fill_color="#f3f1ec",
                                border_color="#cbd5e1",
                                border_width=0.8)
    painter = QPainter(img)
    layer.paint(painter, vp)
    painter.end()

    center = img.pixelColor(200, 200)
    assert center.red() == 0xF3
    assert center.green() == 0xF1
    assert center.blue() == 0xEC


def test_polygon_outside_viewport_is_culled():
    """Polygon far away should not produce any visible pixels."""
    img = QImage(400, 400, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)
    vp = MapViewport(114.5, 22.75, zoom=8.0, width=400, height=400)
    layer = GeoJsonPolygonLayer(POLYGON_FAR_AWAY, fill_color="#ff0000",
                                border_color="#000000", border_width=1.0)
    painter = QPainter(img)
    layer.paint(painter, vp)
    painter.end()

    # No red pixels anywhere
    for y in range(0, 400, 20):
        for x in range(0, 400, 20):
            c = img.pixelColor(x, y)
            assert not (c.red() > 200 and c.green() < 50 and c.blue() < 50)


def test_feature_filter_excludes_iso_a3():
    """`feature_filter` callable can exclude features by properties."""
    img = QImage(400, 400, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)
    vp = MapViewport(114.5, 22.75, zoom=8.0, width=400, height=400)
    layer = GeoJsonPolygonLayer(
        SQUARE_AROUND_HUIZHOU,
        fill_color="#f3f1ec", border_color="#cbd5e1", border_width=0.8,
        feature_filter=lambda props: props.get("ISO_A3") != "CHN",
    )
    painter = QPainter(img)
    layer.paint(painter, vp)
    painter.end()
    center = img.pixelColor(200, 200)
    # Should be unchanged white
    assert center.red() == 0xFF
    assert center.green() == 0xFF
    assert center.blue() == 0xFF
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/map/test_layer_polygon.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create `packages/geoviz_map/geoviz_map/layers/geojson_polygon.py`:

```python
"""GeoJsonPolygonLayer — fill + stroke for Polygon / MultiPolygon features.

Builds a single QPainterPath per feature at init time (in world coords),
then transforms to screen at paint time. Skips features whose world bbox
is entirely outside the viewport.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

from geoviz_map.layers.base import MapLayer
from geoviz_map.projection import lnglat_to_world
from geoviz_map.viewport import MapViewport


FeatureFilter = Callable[[dict], bool]


class GeoJsonPolygonLayer(MapLayer):
    def __init__(self, geojson: dict,
                 fill_color: str,
                 border_color: str,
                 border_width: float,
                 feature_filter: FeatureFilter | None = None):
        self.fill_color = QColor(fill_color)
        self.border_color = QColor(border_color)
        self.border_width = border_width
        # Per-feature: (world_path, world_bbox)
        self._features: list[tuple[QPainterPath, tuple[float, float, float, float]]] = []
        for feat in geojson.get("features", []):
            if feature_filter is not None and not feature_filter(feat.get("properties", {})):
                continue
            geom = feat.get("geometry") or {}
            gtype = geom.get("type")
            if gtype == "Polygon":
                rings = [geom["coordinates"]]
            elif gtype == "MultiPolygon":
                rings = geom["coordinates"]
            else:
                continue
            for poly in rings:
                path, bbox = self._build_path(poly)
                if path is not None:
                    self._features.append((path, bbox))

    @staticmethod
    def _build_path(poly: list[list[list[float]]]) -> tuple[QPainterPath | None,
                                                            tuple[float, float, float, float]]:
        """Build a QPainterPath for one Polygon (outer ring + inner rings)."""
        path = QPainterPath()
        min_x = float("inf")
        min_y = float("inf")
        max_x = float("-inf")
        max_y = float("-inf")
        for ring in poly:
            if not ring:
                continue
            world_pts: list[QPointF] = []
            for lng, lat in ring:
                lat_c = max(-85.05112878, min(85.05112878, lat))
                x, y = lnglat_to_world(lng, lat_c)
                world_pts.append(QPointF(x, y))
                if x < min_x: min_x = x
                if x > max_x: max_x = x
                if y < min_y: min_y = y
                if y > max_y: max_y = y
            if not world_pts:
                continue
            path.moveTo(world_pts[0])
            for p in world_pts[1:]:
                path.lineTo(p)
            path.closeSubpath()
        if path.isEmpty():
            return None, (0, 0, 0, 0)
        path.setFillRule(Qt.FillRule.OddEvenFill)
        return path, (min_x, min_y, max_x, max_y)

    @staticmethod
    def _bbox_overlaps(a: tuple[float, float, float, float],
                       b: tuple[float, float, float, float]) -> bool:
        return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])

    def paint(self, painter: QPainter, viewport: MapViewport) -> None:
        vp_bbox = viewport.world_bbox()
        s = viewport.scale
        cx, cy = viewport.center_world
        ox = viewport.width / 2
        oy = viewport.height / 2

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.save()
        # Build a transform: world (x,y) → screen
        # sx = (x - cx) * s + ox
        # sy = (cy - y) * s + oy   (y flipped)
        # Equivalent: translate(ox, oy); scale(s, -s); translate(-cx, -cy)
        painter.translate(ox, oy)
        painter.scale(s, -s)
        painter.translate(-cx, -cy)

        pen = QPen(self.border_color, self.border_width)
        pen.setCosmetic(True)  # width stays constant in screen pixels
        painter.setPen(pen)
        painter.setBrush(self.fill_color)

        for path, bbox in self._features:
            if not self._bbox_overlaps(vp_bbox, bbox):
                continue
            painter.drawPath(path)

        painter.restore()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/map/test_layer_polygon.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_map/geoviz_map/layers/geojson_polygon.py tests/map/test_layer_polygon.py
git commit -m "feat(map): add GeoJsonPolygonLayer with viewport culling"
```

---

### Task 10: `ReferenceLabelsLayer` — city points + sea italic labels

**Files:**
- Create: `packages/geoviz_map/geoviz_map/layers/reference.py`
- Test: `tests/map/test_layer_reference.py`

- [ ] **Step 1: Write the failing test**

Create `tests/map/test_layer_reference.py`:

```python
from PySide6.QtGui import QImage, QPainter

from geoviz_map.layers.reference import ReferenceLabelsLayer
from geoviz_map.models import ReferenceLabel
from geoviz_map.viewport import MapViewport


def test_capital_renders_red_dot():
    labels = [ReferenceLabel(name="北京", lng=116.4, lat=39.9, kind="capital")]
    img = QImage(800, 800, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)
    vp = MapViewport(116.4, 39.9, zoom=7.5, width=800, height=800)
    layer = ReferenceLabelsLayer(labels)
    painter = QPainter(img)
    layer.paint(painter, vp)
    painter.end()

    # Capital dot is red (#ef4444) — sample near the dot location (center)
    found_red = False
    for dx in range(-5, 6):
        for dy in range(-5, 6):
            c = img.pixelColor(400 + dx, 400 + dy)
            if c.red() > 0xD0 and c.green() < 0x60 and c.blue() < 0x60:
                found_red = True
                break
        if found_red:
            break
    assert found_red, "expected red capital dot near image center"


def test_sea_label_has_no_dot_only_text():
    """Sea labels render italic blue text without an accompanying dot."""
    labels = [ReferenceLabel(name="南海", lng=115.5, lat=20.2, kind="sea")]
    img = QImage(800, 800, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)
    vp = MapViewport(115.5, 20.2, zoom=7.5, width=800, height=800)
    layer = ReferenceLabelsLayer(labels)
    painter = QPainter(img)
    layer.paint(painter, vp)
    painter.end()
    # Some non-white pixel must exist (the text)
    found_non_white = False
    for y in range(380, 420):
        for x in range(380, 420):
            c = img.pixelColor(x, y)
            if c.red() < 250 or c.green() < 250 or c.blue() < 250:
                found_non_white = True
                break
        if found_non_white:
            break
    assert found_non_white
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/map/test_layer_reference.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create `packages/geoviz_map/geoviz_map/layers/reference.py`:

```python
"""ReferenceLabelsLayer — city/capital dots and sea italic labels."""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from geoviz_map.layers.base import MapLayer
from geoviz_map.models import ReferenceLabel
from geoviz_map.viewport import MapViewport


CITY_DOT_COLOR = QColor("#94a3b8")
CAPITAL_DOT_COLOR = QColor("#ef4444")
DOT_BORDER = QColor("#ffffff")
LABEL_COLOR = QColor("#475569")
SEA_COLOR = QColor("#0284c7")
LABEL_HALO = QColor("#ffffff")


class ReferenceLabelsLayer(MapLayer):
    def __init__(self, labels: list[ReferenceLabel]):
        self.labels = labels

    def paint(self, painter: QPainter, viewport: MapViewport) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        for lbl in self.labels:
            pt = viewport.lnglat_to_screen(lbl.lng, lbl.lat)
            if lbl.kind == "sea":
                self._draw_sea(painter, pt, lbl.name)
            else:
                self._draw_city(painter, pt, lbl.name, lbl.kind == "capital")

    def _draw_city(self, painter: QPainter, pt: QPointF,
                   name: str, is_capital: bool) -> None:
        dot_color = CAPITAL_DOT_COLOR if is_capital else CITY_DOT_COLOR
        # 6 px dot with 1px white border
        painter.setPen(QPen(DOT_BORDER, 1.0))
        painter.setBrush(dot_color)
        painter.drawEllipse(pt, 3.0, 3.0)

        # Label text (11px, with white halo)
        font = QFont("Sans Serif", 8)
        if is_capital:
            font.setBold(True)
        painter.setFont(font)
        text_pt = QPointF(pt.x() + 8.0, pt.y() + 4.0)
        self._draw_text_with_halo(painter, text_pt, name, LABEL_COLOR)

    def _draw_sea(self, painter: QPainter, pt: QPointF, name: str) -> None:
        font = QFont("Sans Serif", 10)
        font.setBold(True)
        font.setItalic(True)
        painter.setFont(font)
        self._draw_text_with_halo(painter, pt, name, SEA_COLOR)

    @staticmethod
    def _draw_text_with_halo(painter: QPainter, pt: QPointF, text: str,
                             color: QColor) -> None:
        # Halo: draw text in white at 4 corner offsets, then draw final color on top
        painter.setPen(QPen(LABEL_HALO, 0))
        for dx, dy in ((-1.5, -1.5), (1.5, -1.5), (-1.5, 1.5), (1.5, 1.5)):
            painter.drawText(QPointF(pt.x() + dx, pt.y() + dy), text)
        painter.setPen(QPen(color, 0))
        painter.drawText(pt, text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/map/test_layer_reference.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_map/geoviz_map/layers/reference.py tests/map/test_layer_reference.py
git commit -m "feat(map): add ReferenceLabelsLayer for cities and seas"
```

---

### Task 11: `WellsLayer` — markers, halo labels, hover, hit-test

**Files:**
- Create: `packages/geoviz_map/geoviz_map/layers/wells.py`
- Test: `tests/map/test_layer_wells.py`

- [ ] **Step 1: Write the failing test**

Create `tests/map/test_layer_wells.py`:

```python
from PySide6.QtCore import QPointF
from PySide6.QtGui import QImage, QPainter

from geoviz_map.layers.wells import WellsLayer
from geoviz_map.models import WellMarker
from geoviz_map.viewport import MapViewport


def _setup(width: int = 800, height: int = 800):
    img = QImage(width, height, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    vp = MapViewport(114.5, 22.0, zoom=8.0, width=width, height=height)
    return img, vp


def test_well_dot_renders_at_center_with_specified_color():
    well = WellMarker(name="HZ-1", lng=114.5, lat=22.0, color="#ef4444",
                      has_data=True)
    layer = WellsLayer([well])
    img, vp = _setup()
    painter = QPainter(img)
    layer.paint(painter, vp)
    painter.end()
    # Center should be near red
    found_red = False
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            c = img.pixelColor(400 + dx, 400 + dy)
            if c.red() > 0xD0 and c.green() < 0x60 and c.blue() < 0x60:
                found_red = True
                break
        if found_red:
            break
    assert found_red


def test_hit_test_returns_well_name_at_dot_position():
    well = WellMarker(name="HZ-1", lng=114.5, lat=22.0, color="#ef4444",
                      has_data=True)
    layer = WellsLayer([well])
    img, vp = _setup()
    painter = QPainter(img)
    layer.paint(painter, vp)
    painter.end()
    assert layer.hit_test(QPointF(400, 400), vp) == "HZ-1"


def test_hit_test_miss_returns_none():
    well = WellMarker(name="HZ-1", lng=114.5, lat=22.0, color="#ef4444",
                      has_data=True)
    layer = WellsLayer([well])
    img, vp = _setup()
    painter = QPainter(img)
    layer.paint(painter, vp)
    painter.end()
    # 50 px away from any well
    assert layer.hit_test(QPointF(50, 50), vp) is None


def test_set_hovered_increases_hover_dot_size():
    well_a = WellMarker(name="A", lng=114.5, lat=22.0, color="#ef4444",
                        has_data=True)
    well_b = WellMarker(name="B", lng=115.5, lat=22.0, color="#ef4444",
                        has_data=True)
    layer = WellsLayer([well_a, well_b])
    layer.set_hovered("A")
    assert layer.hovered_name == "A"
    layer.set_hovered(None)
    assert layer.hovered_name is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/map/test_layer_wells.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create `packages/geoviz_map/geoviz_map/layers/wells.py`:

```python
"""WellsLayer — well markers (dot + halo'd label) with hover + click hit-test."""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from geoviz_map.layers.base import MapLayer
from geoviz_map.models import WellMarker
from geoviz_map.viewport import MapViewport


DOT_BORDER = QColor("#ffffff")
LABEL_HALO = QColor("#ffffff")
LABEL_WITH_DATA = QColor("#0f172a")
LABEL_NO_DATA = QColor("#64748b")
DOT_RADIUS = 7.0  # half of 14px
HOVER_SCALE = 1.2
HIT_RADIUS = 10.0  # generous click target


class WellsLayer(MapLayer):
    def __init__(self, wells: list[WellMarker]):
        self.wells = wells
        self.hovered_name: str | None = None
        # Updated each paint(): list of (name, screen_pt)
        self._screen_positions: list[tuple[str, QPointF]] = []

    def set_hovered(self, name: str | None) -> None:
        self.hovered_name = name

    def paint(self, painter: QPainter, viewport: MapViewport) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        positions: list[tuple[str, QPointF]] = []
        for w in self.wells:
            pt = viewport.lnglat_to_screen(w.lng, w.lat)
            positions.append((w.name, pt))

            r = DOT_RADIUS * (HOVER_SCALE if w.name == self.hovered_name else 1.0)
            painter.setPen(QPen(DOT_BORDER, 2.0))
            painter.setBrush(QColor(w.color))
            painter.drawEllipse(pt, r, r)

            # Label below dot
            font = QFont("Sans Serif", 9)
            font.setBold(True)
            painter.setFont(font)
            color = LABEL_WITH_DATA if w.has_data else LABEL_NO_DATA
            label_pt = QPointF(pt.x(), pt.y() + r + 14.0)
            metrics = painter.fontMetrics()
            text_width = metrics.horizontalAdvance(w.name)
            label_pt = QPointF(label_pt.x() - text_width / 2, label_pt.y())
            self._draw_text_with_halo(painter, label_pt, w.name, color)

        self._screen_positions = positions

    def hit_test(self, screen_pt: QPointF,
                 viewport: MapViewport) -> str | None:
        # If paint hasn't run yet, fall back to projecting now
        positions = self._screen_positions
        if not positions:
            positions = [(w.name, viewport.lnglat_to_screen(w.lng, w.lat))
                         for w in self.wells]
        r2 = HIT_RADIUS * HIT_RADIUS
        for name, pt in positions:
            dx = pt.x() - screen_pt.x()
            dy = pt.y() - screen_pt.y()
            if dx * dx + dy * dy <= r2:
                return name
        return None

    @staticmethod
    def _draw_text_with_halo(painter: QPainter, pt: QPointF, text: str,
                             color: QColor) -> None:
        painter.setPen(QPen(LABEL_HALO, 0))
        for dx, dy in ((-1.5, -1.5), (1.5, -1.5), (-1.5, 1.5), (1.5, 1.5)):
            painter.drawText(QPointF(pt.x() + dx, pt.y() + dy), text)
        painter.setPen(QPen(color, 0))
        painter.drawText(pt, text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/map/test_layer_wells.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_map/geoviz_map/layers/wells.py tests/map/test_layer_wells.py
git commit -m "feat(map): add WellsLayer with hover, halo labels, hit-test"
```

---

## Phase 3 — `MapCanvas` and app wiring

### Task 12: `MapCanvas` composite widget + `well_clicked` signal

**Files:**
- Create: `packages/geoviz_map/geoviz_map/canvas.py`
- Modify: `packages/geoviz_map/geoviz_map/__init__.py` (export public API)
- Test: `tests/test_map_canvas.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_map_canvas.py`:

```python
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from geoviz_map import MapCanvas, ReferenceLabel, WellMarker


WORLD_GEOJSON = {
    "type": "FeatureCollection",
    "features": [{
        "type": "Feature",
        "properties": {"ISO_A3": "ABC"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [110.0, 18.0], [120.0, 18.0],
                [120.0, 28.0], [110.0, 28.0], [110.0, 18.0],
            ]],
        },
    }],
}

CHINA_GEOJSON = {"type": "FeatureCollection", "features": []}


def _make_canvas(qtbot):
    wells = [WellMarker(name="HZ-1", lng=114.5, lat=22.0, color="#ef4444",
                        has_data=True)]
    labels = [ReferenceLabel(name="香港", lng=114.17, lat=22.32, kind="city")]
    canvas = MapCanvas(wells=wells, world_geojson=WORLD_GEOJSON,
                       china_geojson=CHINA_GEOJSON, reference_labels=labels,
                       initial_center=(114.5, 22.0), initial_zoom=8.0)
    qtbot.addWidget(canvas)
    canvas.resize(800, 800)
    canvas.show()
    qtbot.waitExposed(canvas)
    return canvas


def test_canvas_grab_produces_nonempty_image(qtbot):
    canvas = _make_canvas(qtbot)
    pixmap = canvas.grab()
    assert not pixmap.isNull()
    assert pixmap.width() == 800
    assert pixmap.height() == 800


def test_well_clicked_signal_fires_with_name(qtbot):
    canvas = _make_canvas(qtbot)
    canvas.repaint()  # ensure layers have cached screen positions
    well_pt = canvas._viewport.lnglat_to_screen(114.5, 22.0)
    received: list[str] = []
    canvas.well_clicked.connect(received.append)
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton,
                     pos=QPoint(int(well_pt.x()), int(well_pt.y())))
    assert received == ["HZ-1"]


def test_resize_updates_viewport_dimensions(qtbot):
    canvas = _make_canvas(qtbot)
    canvas.resize(400, 300)
    qtbot.wait(20)
    assert canvas._viewport.width == 400
    assert canvas._viewport.height == 300
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_map_canvas.py -v`
Expected: FAIL with `ImportError: cannot import name 'MapCanvas' from 'geoviz_map'`

- [ ] **Step 3: Write implementation**

Create `packages/geoviz_map/geoviz_map/canvas.py`:

```python
"""MapCanvas — composite QWidget that paints all layers and dispatches input."""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import QWidget

from geoviz_map.layers.background import BackgroundLayer
from geoviz_map.layers.base import MapLayer
from geoviz_map.layers.geojson_polygon import GeoJsonPolygonLayer
from geoviz_map.layers.graticule import GraticuleLayer
from geoviz_map.layers.reference import ReferenceLabelsLayer
from geoviz_map.layers.wells import WellsLayer
from geoviz_map.models import ReferenceLabel, WellMarker
from geoviz_map.viewport import MapViewport
from geoviz_map.zoom_pan import ZoomPanHandler


class MapCanvas(QWidget):
    well_clicked = Signal(str)
    well_hovered = Signal(str)  # emits empty string when hover leaves

    def __init__(self,
                 wells: list[WellMarker],
                 world_geojson: dict,
                 china_geojson: dict,
                 reference_labels: list[ReferenceLabel] | None = None,
                 initial_center: tuple[float, float] | None = None,
                 initial_zoom: float = 7.5,
                 background_color: str = "#cbebfb",
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setMouseTracking(True)
        if initial_center is None:
            if wells:
                avg_lng = sum(w.lng for w in wells) / len(wells)
                avg_lat = sum(w.lat for w in wells) / len(wells)
                initial_center = (avg_lng, avg_lat)
            else:
                initial_center = (117.0, 38.0)
        self._viewport = MapViewport(initial_center[0], initial_center[1],
                                     zoom=initial_zoom,
                                     width=max(1, self.width()),
                                     height=max(1, self.height()))
        self._zoom_pan = ZoomPanHandler(self._viewport)

        self._wells_layer = WellsLayer(wells)

        self._layers: list[MapLayer] = [
            BackgroundLayer(background_color),
            GraticuleLayer(),
            GeoJsonPolygonLayer(
                world_geojson,
                fill_color="#f3f1ec",
                border_color="#cbd5e1",
                border_width=0.8,
                feature_filter=lambda p: p.get("ISO_A3") not in ("CHN", "TWN"),
            ),
            GeoJsonPolygonLayer(
                china_geojson,
                fill_color="#f3f1ec",
                border_color="#cbd5e1",
                border_width=0.8,
            ),
            ReferenceLabelsLayer(reference_labels or []),
            self._wells_layer,
        ]

    # Painting -----------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            for layer in self._layers:
                layer.paint(painter, self._viewport)
        finally:
            painter.end()

    def resizeEvent(self, event: QResizeEvent) -> None:
        self._viewport.resize(max(1, event.size().width()),
                              max(1, event.size().height()))
        super().resizeEvent(event)

    # Input --------------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._zoom_pan.start_drag(QPointF(event.position()))
            self._press_pos = QPointF(event.position())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = QPointF(event.position())
        if self._zoom_pan.is_dragging():
            self._zoom_pan.update_drag(pos)
            self.update()
        else:
            # Hover hit-test
            name = self._wells_layer.hit_test(pos, self._viewport)
            if name != self._wells_layer.hovered_name:
                self._wells_layer.set_hovered(name)
                self.well_hovered.emit(name or "")
                self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        was_dragging = self._zoom_pan.is_dragging()
        release_pos = QPointF(event.position())
        # Distinguish click vs drag: if total drag is small, treat as click
        drag_distance = 0.0
        if hasattr(self, "_press_pos"):
            dx = release_pos.x() - self._press_pos.x()
            dy = release_pos.y() - self._press_pos.y()
            drag_distance = (dx * dx + dy * dy) ** 0.5
        self._zoom_pan.end_drag()
        if drag_distance < 4.0:
            # Hit-test top-down (wells layer is topmost interactive)
            for layer in reversed(self._layers):
                name = layer.hit_test(release_pos, self._viewport)
                if name:
                    self.well_clicked.emit(name)
                    return

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y() / 120.0  # one notch = 1.0
        if delta == 0:
            return
        self._zoom_pan.wheel_zoom(QPointF(event.position()), delta_steps=delta)
        self.update()
```

Modify `packages/geoviz_map/geoviz_map/__init__.py`:

```python
"""geoviz_map — QPainter-based geographic map visualization for PySide6."""
from geoviz_map.canvas import MapCanvas
from geoviz_map.models import ReferenceLabel, WellMarker

__all__ = ["MapCanvas", "WellMarker", "ReferenceLabel"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_map_canvas.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_map/geoviz_map/canvas.py packages/geoviz_map/geoviz_map/__init__.py tests/test_map_canvas.py
git commit -m "feat(map): add MapCanvas composite widget with well_clicked signal"
```

---

### Task 13: Wire MapPage to use MapCanvas

**Files:**
- Modify: `src/pages/map/page.py`

**Note:** Per the spec's Phase 3 plan, do not delete `src/pages/map/renderer.py` yet — that happens in Phase 4 after human verification.

- [ ] **Step 1: Update `src/pages/map/page.py`**

Replace the entire contents of `src/pages/map/page.py` with:

```python
"""MapPage — native QPainter-based geographic map for well coordinates."""
import json
from pathlib import Path

from PySide6.QtWidgets import QVBoxLayout, QWidget

from geoviz_map import MapCanvas, ReferenceLabel, WellMarker

from src.data.cache import DataCache
from src.data.well_registry import available_wells
from src.utils.paths import get_data_dir

DATA_DIR = get_data_dir()
WELL_COORDS_FILE = DATA_DIR / "well_coordinates.json"
WORLD_GEOJSON_FILE = DATA_DIR / "world.json"
CHINA_GEOJSON_FILE = DATA_DIR / "china_provinces.json"


# Reference labels (verbatim list from the legacy MapLibre implementation)
REFERENCE_LABELS: list[ReferenceLabel] = [
    ReferenceLabel(name="北京 (Beijing)", lng=116.4074, lat=39.9042, kind="capital"),
    ReferenceLabel(name="上海 (Shanghai)", lng=121.4737, lat=31.2304, kind="city"),
    ReferenceLabel(name="广州 (Guangzhou)", lng=113.2644, lat=23.1292, kind="city"),
    ReferenceLabel(name="深圳 (Shenzhen)", lng=114.0579, lat=22.5431, kind="city"),
    ReferenceLabel(name="香港 (Hong Kong)", lng=114.1694, lat=22.3193, kind="city"),
    ReferenceLabel(name="澳门 (Macau)", lng=113.5439, lat=22.1987, kind="city"),
    ReferenceLabel(name="惠州 (Huizhou)", lng=114.4158, lat=23.1109, kind="city"),
    ReferenceLabel(name="珠海 (Zhuhai)", lng=113.5767, lat=22.2707, kind="city"),
    ReferenceLabel(name="汕头 (Shantou)", lng=116.7084, lat=23.3718, kind="city"),
    ReferenceLabel(name="湛江 (Zhanjiang)", lng=110.3649, lat=21.2749, kind="city"),
    ReferenceLabel(name="海口 (Haikou)", lng=110.3308, lat=20.0221, kind="city"),
    ReferenceLabel(name="福州 (Fuzhou)", lng=119.3063, lat=26.0753, kind="city"),
    ReferenceLabel(name="台北 (Taipei)", lng=121.5654, lat=25.0330, kind="city"),
    ReferenceLabel(name="南宁 (Nanning)", lng=108.3200, lat=22.8240, kind="city"),
    ReferenceLabel(name="南海 (South China Sea)", lng=115.5, lat=20.2, kind="sea"),
]


def _load_json(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return {"type": "FeatureCollection", "features": []}


def _coords_to_markers(coords, data_wells: set[str]) -> list[WellMarker]:
    return [
        WellMarker(
            name=w.name,
            lng=w.longitude,
            lat=w.latitude,
            color="#ef4444" if w.name in data_wells else "#6b7280",
            has_data=w.name in data_wells,
        )
        for w in coords
    ]


class MapPage(QWidget):
    def __init__(self, cache: DataCache, well_click_callback=None):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        coords = cache.get_well_coordinates(WELL_COORDS_FILE)
        data_wells = available_wells()
        wells = _coords_to_markers(coords, data_wells)
        world = _load_json(WORLD_GEOJSON_FILE)
        china = _load_json(CHINA_GEOJSON_FILE)

        self.map_canvas = MapCanvas(
            wells=wells,
            world_geojson=world,
            china_geojson=china,
            reference_labels=REFERENCE_LABELS,
            initial_zoom=7.5,
        )
        if well_click_callback is not None:
            self.map_canvas.well_clicked.connect(well_click_callback)
        layout.addWidget(self.map_canvas)
```

- [ ] **Step 2: Verify the full test suite still passes**

Run: `source .venv/bin/activate && pytest -q`
Expected: All previously-passing tests still pass; new map tests also pass.

- [ ] **Step 3: Smoke test app launch**

Run: `source .venv/bin/activate && timeout 5 python -m src.main 2>&1 | head -30; echo "exit=$?"`
Expected: No fatal import errors, no traceback. App opens (timeout kills it after 5s; that's fine).

- [ ] **Step 4: Commit**

```bash
git add src/pages/map/page.py
git commit -m "feat(map): wire MapPage to MapCanvas, retire MapLibre at the page boundary"
```

---

### Task 14: Visual parity test with golden image

**Files:**
- Create: `tests/test_map_visual_parity.py`
- Create: `tests/golden/.gitkeep` (placeholder; image generated below)
- Create: `tests/golden/map_canvas_default.png` (binary, generated)

- [ ] **Step 1: Generate the golden image from the current QPainter implementation**

Create `tests/golden/.gitkeep` (empty file).

Run this one-off Python snippet to write the golden image. This is the **first** time we render at the canonical viewport; visually inspect the result before committing.

```bash
source .venv/bin/activate && python - <<'PY'
import json
from pathlib import Path
from PySide6.QtWidgets import QApplication
from geoviz_map import MapCanvas, ReferenceLabel, WellMarker

app = QApplication.instance() or QApplication([])
data_dir = Path("data")
world = json.loads((data_dir / "world.json").read_text(encoding="utf-8"))
china = json.loads((data_dir / "china_provinces.json").read_text(encoding="utf-8"))
coords = json.loads((data_dir / "well_coordinates.json").read_text(encoding="utf-8"))
wells = [WellMarker(name=w["name"], lng=w["longitude"], lat=w["latitude"],
                    color="#ef4444", has_data=True) for w in coords["wells"]]
labels = [
    ReferenceLabel(name="香港", lng=114.17, lat=22.32, kind="city"),
    ReferenceLabel(name="南海", lng=115.5, lat=20.2, kind="sea"),
]
c = MapCanvas(wells=wells, world_geojson=world, china_geojson=china,
              reference_labels=labels, initial_center=(118.0, 25.0),
              initial_zoom=7.5)
c.resize(1200, 800)
c.show()
app.processEvents()
pix = c.grab()
out = Path("tests/golden/map_canvas_default.png")
out.parent.mkdir(parents=True, exist_ok=True)
pix.save(str(out))
print(f"wrote {out}")
PY
```

Open `tests/golden/map_canvas_default.png` in an image viewer. Confirm:
- Background is light blue (`#cbebfb`)
- Land masses are sandy `#f3f1ec` with light gray borders
- Graticule dashed lines visible
- Well markers visible as red dots with labels
- Hong Kong city label rendered, "南海" italic blue label rendered

**If the image looks wrong**, FIX the underlying code first, regenerate, then proceed.

- [ ] **Step 2: Write the parity test**

Create `tests/test_map_visual_parity.py`:

```python
"""Visual parity test — guards against regression of the canonical render."""
import json
from pathlib import Path

import pytest
from PySide6.QtGui import QImage

from geoviz_map import MapCanvas, ReferenceLabel, WellMarker


DATA_DIR = Path(__file__).parent.parent / "data"
GOLDEN = Path(__file__).parent / "golden" / "map_canvas_default.png"


@pytest.fixture(scope="module")
def golden_image() -> QImage:
    img = QImage(str(GOLDEN))
    assert not img.isNull(), f"golden image missing: {GOLDEN}"
    return img.convertToFormat(QImage.Format.Format_ARGB32)


def _render_canonical(qtbot) -> QImage:
    world = json.loads((DATA_DIR / "world.json").read_text(encoding="utf-8"))
    china = json.loads((DATA_DIR / "china_provinces.json").read_text(encoding="utf-8"))
    coords = json.loads((DATA_DIR / "well_coordinates.json").read_text(encoding="utf-8"))
    wells = [WellMarker(name=w["name"], lng=w["longitude"], lat=w["latitude"],
                        color="#ef4444", has_data=True) for w in coords["wells"]]
    labels = [
        ReferenceLabel(name="香港", lng=114.17, lat=22.32, kind="city"),
        ReferenceLabel(name="南海", lng=115.5, lat=20.2, kind="sea"),
    ]
    c = MapCanvas(wells=wells, world_geojson=world, china_geojson=china,
                  reference_labels=labels, initial_center=(118.0, 25.0),
                  initial_zoom=7.5)
    qtbot.addWidget(c)
    c.resize(1200, 800)
    c.show()
    qtbot.waitExposed(c)
    return c.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32)


def _pixel_diff_ratio(a: QImage, b: QImage, threshold: int = 30) -> float:
    assert a.size() == b.size()
    w, h = a.width(), a.height()
    differing = 0
    total = 0
    step = 4  # sample 1/16th of pixels for speed
    for y in range(0, h, step):
        for x in range(0, w, step):
            ca = a.pixelColor(x, y)
            cb = b.pixelColor(x, y)
            total += 1
            if (abs(ca.red() - cb.red())
                    + abs(ca.green() - cb.green())
                    + abs(ca.blue() - cb.blue())) > threshold:
                differing += 1
    return differing / max(total, 1)


def test_canonical_render_matches_golden(qtbot, golden_image):
    current = _render_canonical(qtbot)
    ratio = _pixel_diff_ratio(current, golden_image)
    assert ratio < 0.005, f"visual parity diff {ratio*100:.2f}% exceeds 0.5%"
```

- [ ] **Step 3: Run parity test**

Run: `source .venv/bin/activate && pytest tests/test_map_visual_parity.py -v`
Expected: 1 passed

- [ ] **Step 4: Commit**

```bash
git add tests/golden/ tests/test_map_visual_parity.py
git commit -m "test(map): add visual parity golden image and regression test"
```

---

## Phase 4 — Manual verification, cleanup, docs

### Task 15: Manual verification of the live app

This is a **human gate** before deletion. The plan executor should pause and request human confirmation.

- [ ] **Step 1: Launch the app and verify Map page interactively**

Run: `source .venv/bin/activate && python -m src.main`

Manually verify on the Map page:
- Visual: background light blue, land sandy, gray borders, dashed grid visible
- Well markers: red dots for wells with data, gray for others; labels readable
- Hover: dot scales up 1.2x when cursor is over
- Click: clicking a well navigates to the well log page (existing callback)
- Pan: drag moves the map
- Zoom: scroll wheel zooms toward cursor

- [ ] **Step 2: If anything is wrong**

Open a fresh chat / brainstorming session for that specific bug. Do NOT proceed to Task 16 until everything is acceptable.

- [ ] **Step 3: Get user sign-off**

User confirms "looks good, proceed to cleanup".

---

### Task 16: Delete legacy MapRenderer and MapLibre assets

**Files:**
- Delete: `src/pages/map/renderer.py`
- Delete: `src/pages/map/assets/maplibre-gl.js`
- Delete: `src/pages/map/assets/maplibre-gl.css`

- [ ] **Step 1: Verify nothing references the deletion targets**

Run: `grep -rn "MapRenderer\|maplibre-gl\|MAPLIBRE_HTML\|build_geojson\|well://" src/ packages/ tests/ 2>/dev/null | grep -v "archive/" | grep -v __pycache__`
Expected: No hits except possibly in the file you're about to delete (`src/pages/map/renderer.py` itself).

If there is an unexpected hit, STOP and resolve it before deletion.

- [ ] **Step 2: Delete the files via git**

```bash
git rm src/pages/map/renderer.py
git rm src/pages/map/assets/maplibre-gl.js
git rm src/pages/map/assets/maplibre-gl.css
# If the assets/ directory is now empty, remove it too
[ -d src/pages/map/assets ] && [ -z "$(ls -A src/pages/map/assets 2>/dev/null)" ] && rmdir src/pages/map/assets
```

- [ ] **Step 3: Run the full test suite**

Run: `source .venv/bin/activate && pytest -q`
Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add -A src/pages/map/
git commit -m "chore(map): delete legacy MapRenderer and inline MapLibre assets"
```

---

### Task 17: Update docs (CLAUDE.md, README.md, CHANGELOG.md)

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update `CLAUDE.md` Architecture diagram**

In `CLAUDE.md`, find the line:

```
│       ├── MapPage        → QWebEngineView + MapLibre GL
```

Replace with:

```
│       ├── MapPage        → QPainter (via geoviz-map package)
```

In the `## Architecture` section, after the `geoviz-seismic` package block, add a new package block:

```
│   └── geoviz-map/        → Independent QPainter-based geographic map engine
│       ├── canvas.py            → MapCanvas (QWidget composite layers)
│       ├── projection.py        → Web Mercator math
│       ├── viewport.py          → MapViewport (center+zoom → pixel mapping)
│       ├── zoom_pan.py          → ZoomPanHandler (drag pan + wheel zoom)
│       └── layers/              → Background, Graticule, GeoJsonPolygon, Reference, Wells
```

In the bullet list below the diagram, add after the seismic package bullet:

```
- **Independent Package**: `geoviz-map` is a fully decoupled geographic map engine using only QPainter. Web Mercator projection compatible with MapLibre GL. Layer-based architecture for offline GeoJSON rendering. Can be `pip install`-ed and used in any PySide6 project.
```

In the `## Key Code Patterns` section, replace the line starting `**Map**: QWebEngineView embeds MapLibre GL JS` with:

```
- **Map**: Native QPainter via `geoviz-map` package. World/China GeoJSON loaded once at init into cached `QPainterPath` (per-feature), then painted with a single world→screen `QTransform` per frame. Well click events emitted via Qt `Signal(str)` (`MapCanvas.well_clicked`).
```

In the `## Project Layout` section, add a new package entry after `packages/geoviz_seismic/`:

```
- `packages/geoviz_map/` — Independent geographic map visualization package
  - `geoviz_map/canvas.py` — MapCanvas (QWidget composite of all layers)
  - `geoviz_map/projection.py` — Web Mercator projection
  - `geoviz_map/viewport.py` — center+zoom → screen pixel mapping
  - `geoviz_map/zoom_pan.py` — Drag pan + cursor-anchored wheel zoom
  - `geoviz_map/layers/` — Background, Graticule, GeoJsonPolygon, ReferenceLabels, Wells
  - `geoviz_map/models.py` — WellMarker, ReferenceLabel
```

- [ ] **Step 2: Update `README.md`**

In `README.md`, find the architecture ASCII box. Replace the line:

```
│  │ 🗺   │  MapPage     QWebEngineView + MapLibre   │    │
```

with:

```
│  │ 🗺   │  MapPage     QPainter (geoviz-map)        │    │
```

After the `packages/geoviz-seismic/` block in the same ASCII diagram, add:

```
│                                                         │
│  packages/geoviz-map/                                   │
│  ┌─────────────────────────────────────────────────┐    │
│  │  独立地图可视化引擎 (QPainter + Web Mercator)     │    │
│  │  ├── MapCanvas      组合 6 个 layer              │    │
│  │  ├── Projection     Web Mercator (MapLibre 兼容) │    │
│  │  ├── Viewport       center+zoom 像素映射         │    │
│  │  ├── ZoomPanHandler 拖拽+滚轮缩放                │    │
│  │  └── Layers         背景/网格/地块/标签/井点      │    │
│  └─────────────────────────────────────────────────┘    │
```

In the Tech Stack table, find the `地图 | MapLibre GL (QWebEngineView) | ...` row and replace with:

```
| 地图 | QPainter (geoviz-map) | 井位地图、Web Mercator 投影、交互选井 |
```

In the Project Structure tree, after the `geoviz_seismic/` block, add:

```
│   └── geoviz_map/                # 独立地图可视化包 (pip installable)
│       ├── geoviz_map/
│       │   ├── canvas.py          # MapCanvas (QWidget 组合 layers)
│       │   ├── projection.py      # Web Mercator 投影
│       │   ├── viewport.py        # center+zoom → 像素映射
│       │   ├── zoom_pan.py        # 拖拽 + 滚轮缩放
│       │   ├── layers/            # 6 个渲染层
│       │   └── models.py          # WellMarker, ReferenceLabel
│       └── pyproject.toml
```

- [ ] **Step 3: Update `CHANGELOG.md`**

In `CHANGELOG.md`, under the `## [Unreleased]` section, add a new subsection:

```markdown
### Changed
- **MapPage 渲染重写**：井位分布图从 QWebEngineView + MapLibre GL 迁移到原生 QPainter，新增独立包 `geoviz_map`。1:1 视觉/交互对齐，新增滚轮缩放向光标，视口剔除提升大 GeoJSON 渲染性能。

### Removed
- 删除 `src/pages/map/renderer.py`（394 行 MapLibre 嵌入实现）。
- 删除 `src/pages/map/assets/maplibre-gl.js` 与 `maplibre-gl.css`（~640 KB 内联资产）。
- `well://` 自定义 URL scheme 与 `QWebEnginePage` 子类一并消失。
```

If `### Changed` and `### Removed` sub-sections already exist under `[Unreleased]` from the earlier archive commit, append the new entries inside them rather than creating duplicates.

- [ ] **Step 4: Run the full test suite one last time**

Run: `source .venv/bin/activate && pytest -q`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md CHANGELOG.md
git commit -m "docs(map): update architecture docs and changelog for geoviz_map migration"
```

---

## Final verification checklist

- [ ] `pytest -q` is green
- [ ] App launches and Map page renders correctly (Task 15 sign-off)
- [ ] `grep -rn "MapRenderer\|maplibre-gl\|MAPLIBRE_HTML" src/ packages/ tests/ 2>/dev/null` returns no hits outside `archive/`
- [ ] CLAUDE.md, README.md, CHANGELOG.md reflect the new architecture
- [ ] Golden image committed at `tests/golden/map_canvas_default.png`
- [ ] 17 commits visible in `git log` since plan started (one per task)
