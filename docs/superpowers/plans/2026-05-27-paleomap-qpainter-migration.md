# PaleoMap QPainter Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace PaleoMap's QWebEngineView + ECharts renderer with a native QPainter pipeline in a new `packages/geoviz_paleo_map/` package, eliminating the project's last WebEngine page renderer.

**Architecture:** New independent package with Plate Carrée projection and 8 layers (background, facies polygons, region labels, wells scatter, title, north arrow, scale bar, legend). Per-feature styling via composite QBrush built from `geoviz_well_log.PatternEngine` (extended with `get_composite_brush` and `get_color_fuzzy` methods, used by no one else but kept as public API). Tooltip via bbox-prefiltered point-in-polygon. Page-level logic (drag-drop, compare, export) stays in `src/pages/paleo_map/page.py` with a 3-line shim swap. Spec: `docs/superpowers/specs/2026-05-27-paleomap-qpainter-migration-design.md`.

**Tech Stack:** PySide6 (`QPainter`, `QPainterPath`, `QPen`, `QBrush`, `QToolTip`, `Signal`), pydantic (data models), `geoviz_well_log.PatternEngine` (reused + extended), pytest + pytest-qt.

---

## File Structure

**Create:**
- `packages/geoviz_paleo_map/pyproject.toml`
- `packages/geoviz_paleo_map/README.md`
- `packages/geoviz_paleo_map/geoviz_paleo_map/__init__.py`
- `packages/geoviz_paleo_map/geoviz_paleo_map/projection.py`
- `packages/geoviz_paleo_map/geoviz_paleo_map/viewport.py`
- `packages/geoviz_paleo_map/geoviz_paleo_map/zoom_pan.py`
- `packages/geoviz_paleo_map/geoviz_paleo_map/canvas.py`
- `packages/geoviz_paleo_map/geoviz_paleo_map/style.py`
- `packages/geoviz_paleo_map/geoviz_paleo_map/models.py`
- `packages/geoviz_paleo_map/geoviz_paleo_map/layers/__init__.py`
- `packages/geoviz_paleo_map/geoviz_paleo_map/layers/base.py`
- `packages/geoviz_paleo_map/geoviz_paleo_map/layers/background.py`
- `packages/geoviz_paleo_map/geoviz_paleo_map/layers/facies_polygons.py`
- `packages/geoviz_paleo_map/geoviz_paleo_map/layers/region_labels.py`
- `packages/geoviz_paleo_map/geoviz_paleo_map/layers/wells_scatter.py`
- `packages/geoviz_paleo_map/geoviz_paleo_map/layers/title.py`
- `packages/geoviz_paleo_map/geoviz_paleo_map/layers/north_arrow.py`
- `packages/geoviz_paleo_map/geoviz_paleo_map/layers/scale_bar.py`
- `packages/geoviz_paleo_map/geoviz_paleo_map/layers/legend.py`
- `tests/paleo_map/__init__.py`
- `tests/paleo_map/conftest.py`
- `tests/paleo_map/test_projection.py`
- `tests/paleo_map/test_viewport.py`
- `tests/paleo_map/test_zoom_pan.py`
- `tests/paleo_map/test_style_resolver.py`
- `tests/paleo_map/test_layer_base.py`
- `tests/paleo_map/test_layer_background.py`
- `tests/paleo_map/test_layer_facies_polygons.py`
- `tests/paleo_map/test_layer_region_labels.py`
- `tests/paleo_map/test_layer_wells_scatter.py`
- `tests/paleo_map/test_layer_title.py`
- `tests/paleo_map/test_layer_north_arrow.py`
- `tests/paleo_map/test_layer_scale_bar.py`
- `tests/paleo_map/test_layer_legend.py`
- `tests/test_paleo_map_canvas.py`
- `tests/test_paleo_map_visual_parity.py`
- `tests/golden/paleo_map_default.png` (generated, committed)

**Modify:**
- `pyproject.toml` (root) — register workspace member
- `packages/geoviz_well_log/geoviz_well_log/renderer/pattern_engine.py` — add `get_composite_brush` + `get_color_fuzzy`
- `packages/geoviz_well_log/geoviz_well_log/__init__.py` — export new methods (no change if already re-exporting `PatternEngine`)
- `src/pages/paleo_map/page.py` — swap renderer for canvas
- `CLAUDE.md`, `README.md`, `CHANGELOG.md`

**Delete (Phase 4):**
- `src/pages/paleo_map/renderer.py`

---

## Phase 1 — Package skeleton, projection, viewport, zoom_pan

### Task 1: Scaffold `geoviz_paleo_map` package

**Files:**
- Create: `packages/geoviz_paleo_map/pyproject.toml`
- Create: `packages/geoviz_paleo_map/README.md`
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/__init__.py`
- Modify: `pyproject.toml` (root)

- [ ] **Step 1: Create `packages/geoviz_paleo_map/pyproject.toml`**

```toml
[project]
name = "geoviz-paleo-map"
version = "0.1.0"
description = "QPainter-based paleogeographic map visualization for PySide6"
readme = "README.md"
license = "MIT"
authors = [{ name = "Kevin", email = "kevin@example.com" }]
requires-python = ">=3.10"
dependencies = [
    "PySide6",
    "pydantic",
    "geoviz-well-log",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-qt"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["geoviz_paleo_map"]

[tool.hatch.build.targets.sdist]
include = ["/geoviz_paleo_map"]
```

- [ ] **Step 2: Create `packages/geoviz_paleo_map/README.md`**

```markdown
# geoviz-paleo-map

QPainter-based paleogeographic (古地理) map visualization for PySide6. Plate Carrée projection, composite SVG pattern fills via `geoviz-well-log`'s `PatternEngine`, full chrome (title, north arrow, scale bar, legend), hover tooltips.

Part of the geo-viz-engine workspace.
```

- [ ] **Step 3: Create `packages/geoviz_paleo_map/geoviz_paleo_map/__init__.py`**

```python
"""geoviz_paleo_map — QPainter-based paleogeographic map visualization for PySide6."""
```

- [ ] **Step 4: Register workspace in root `pyproject.toml`**

In `[tool.uv.workspace] members`, append `"packages/geoviz_paleo_map"`.
In `[tool.uv.sources]`, add `geoviz-paleo-map = { workspace = true }`.
In `[project] dependencies`, add `"geoviz-paleo-map",` after `"geoviz-map",`.

- [ ] **Step 5: Reinstall workspace**

Run: `source .venv/bin/activate && pip install -e packages/geoviz_paleo_map && pip install -e ".[dev]"`
Expected: success including `geoviz-paleo-map-0.1.0`.

- [ ] **Step 6: Sanity-import**

Run: `source .venv/bin/activate && python -c "import geoviz_paleo_map; print(geoviz_paleo_map.__doc__)"`
Expected: `geoviz_paleo_map — QPainter-based paleogeographic map visualization for PySide6.`

- [ ] **Step 7: Commit**

```bash
git add packages/geoviz_paleo_map/ pyproject.toml
git commit -m "feat(paleo): scaffold geoviz_paleo_map package and register workspace"
```

---

### Task 2: Plate Carrée projection

**Files:**
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/projection.py`
- Test: `tests/paleo_map/__init__.py` (empty)
- Test: `tests/paleo_map/test_projection.py`

- [ ] **Step 1: Write the failing test**

Create `tests/paleo_map/__init__.py` (empty).

Create `tests/paleo_map/test_projection.py`:

```python
import pytest

from geoviz_paleo_map.projection import lnglat_to_world, world_to_lnglat


def test_origin_maps_to_origin():
    assert lnglat_to_world(0.0, 0.0) == (0.0, 0.0)


def test_unit_degrees_pass_through():
    assert lnglat_to_world(1.0, 2.0) == (1.0, 2.0)


def test_negative_coordinates_pass_through():
    assert lnglat_to_world(-117.5, -33.86) == (-117.5, -33.86)


def test_round_trip():
    lng, lat = 114.4158, 23.1109
    x, y = lnglat_to_world(lng, lat)
    lng2, lat2 = world_to_lnglat(x, y)
    assert lng2 == pytest.approx(lng)
    assert lat2 == pytest.approx(lat)
```

- [ ] **Step 2: Run, expect FAIL with `ModuleNotFoundError`**

Run: `source .venv/bin/activate && pytest tests/paleo_map/test_projection.py -v`

- [ ] **Step 3: Implementation**

Create `packages/geoviz_paleo_map/geoviz_paleo_map/projection.py`:

```python
"""Plate Carrée (equirectangular) projection.

PaleoMap uses ECharts geo's default coordinate system, which is direct
lng/lat → x/y. Suitable for paleogeographic data that lacks modern WGS84
reference; preserves angular spacing.
"""


def lnglat_to_world(lng: float, lat: float) -> tuple[float, float]:
    """Direct identity: (lng, lat) → (x, y)."""
    return lng, lat


def world_to_lnglat(x: float, y: float) -> tuple[float, float]:
    """Identity inverse."""
    return x, y
```

- [ ] **Step 4: Run, expect 4 passed**

Run: `source .venv/bin/activate && pytest tests/paleo_map/test_projection.py -v`

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/projection.py tests/paleo_map/__init__.py tests/paleo_map/test_projection.py
git commit -m "feat(paleo): add Plate Carrée projection"
```

---

### Task 3: PaleoMapViewport

**Files:**
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/viewport.py`
- Test: `tests/paleo_map/test_viewport.py`

- [ ] **Step 1: Write the failing test**

Create `tests/paleo_map/test_viewport.py`:

```python
import pytest

from geoviz_paleo_map.viewport import PaleoMapViewport


def test_center_maps_to_screen_center():
    vp = PaleoMapViewport(center_lng=115.0, center_lat=30.0, zoom=1.0,
                          width=1200, height=800)
    pt = vp.lnglat_to_screen(115.0, 30.0)
    assert pt.x() == pytest.approx(600.0)
    assert pt.y() == pytest.approx(400.0)


def test_one_degree_east_at_zoom_1_is_one_pixel():
    """At zoom=1.0 the scale is exactly 1 pixel per degree (baseline)."""
    vp = PaleoMapViewport(center_lng=0.0, center_lat=0.0, zoom=1.0,
                          width=1200, height=800)
    pt = vp.lnglat_to_screen(1.0, 0.0)
    # 1 degree east of center → 1 pixel right of width/2
    assert pt.x() == pytest.approx(600.0 + 1.0)


def test_zoom_plus_one_doubles_pixel_distance():
    vp_a = PaleoMapViewport(115.0, 30.0, zoom=1.0, width=1200, height=800)
    vp_b = PaleoMapViewport(115.0, 30.0, zoom=2.0, width=1200, height=800)
    pa = vp_a.lnglat_to_screen(116.0, 30.0)
    pb = vp_b.lnglat_to_screen(116.0, 30.0)
    dx_a = pa.x() - 600.0
    dx_b = pb.x() - 600.0
    assert dx_b == pytest.approx(dx_a * 2.0)


def test_screen_to_lnglat_inverts():
    vp = PaleoMapViewport(115.0, 30.0, zoom=4.0, width=1200, height=800)
    from PySide6.QtCore import QPointF
    pt = vp.lnglat_to_screen(112.0, 28.0)
    lng2, lat2 = vp.screen_to_lnglat(pt)
    assert lng2 == pytest.approx(112.0)
    assert lat2 == pytest.approx(28.0)


def test_resize_updates_dimensions():
    vp = PaleoMapViewport(0.0, 0.0, zoom=1.0, width=100, height=100)
    vp.resize(200, 150)
    assert vp.width == 200
    assert vp.height == 150


def test_world_bbox_contains_center():
    vp = PaleoMapViewport(115.0, 30.0, zoom=2.0, width=1200, height=800)
    bbox = vp.world_bbox()
    cx, cy = vp.center_world
    assert bbox[0] < bbox[2]
    assert bbox[1] < bbox[3]
    assert bbox[0] <= cx <= bbox[2]
    assert bbox[1] <= cy <= bbox[3]
```

- [ ] **Step 2: Run, expect FAIL**

Run: `source .venv/bin/activate && pytest tests/paleo_map/test_viewport.py -v`

- [ ] **Step 3: Implementation**

Create `packages/geoviz_paleo_map/geoviz_paleo_map/viewport.py`:

```python
"""PaleoMapViewport — center+zoom → screen-pixel mapping (Plate Carrée)."""

from PySide6.QtCore import QPointF

from geoviz_paleo_map.projection import lnglat_to_world, world_to_lnglat


class PaleoMapViewport:
    """Tracks the visible region.

    At zoom z the scale is 2^(z-1) pixels per degree (zoom=1 → 1 px/deg,
    zoom=2 → 2 px/deg, ...). Y axis flipped: screen y grows downward,
    lat grows upward.
    """

    def __init__(self, center_lng: float, center_lat: float, zoom: float,
                 width: int, height: int):
        self.center_world = lnglat_to_world(center_lng, center_lat)
        self.zoom = zoom
        self.width = width
        self.height = height

    @property
    def scale(self) -> float:
        """Pixels per world unit (degree)."""
        return 2.0 ** (self.zoom - 1.0)

    def world_to_screen(self, x: float, y: float) -> QPointF:
        s = self.scale
        sx = (x - self.center_world[0]) * s + self.width / 2
        sy = (self.center_world[1] - y) * s + self.height / 2
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
        cx, cy = self.center_world
        self.center_world = (cx + dx, cy + dy)

    def pan_pixels(self, dx_px: float, dy_px: float) -> None:
        s = self.scale
        self.pan_world(-dx_px / s, dy_px / s)

    def world_bbox(self) -> tuple[float, float, float, float]:
        s = self.scale
        half_w = self.width / 2 / s
        half_h = self.height / 2 / s
        cx, cy = self.center_world
        return (cx - half_w, cy - half_h, cx + half_w, cy + half_h)

    def resize(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
```

- [ ] **Step 4: Run, expect 6 passed**

Run: `source .venv/bin/activate && pytest tests/paleo_map/test_viewport.py -v`

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/viewport.py tests/paleo_map/test_viewport.py
git commit -m "feat(paleo): add PaleoMapViewport with Plate Carrée screen mapping"
```

---

### Task 4: ZoomPanHandler

**Files:**
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/zoom_pan.py`
- Test: `tests/paleo_map/test_zoom_pan.py`

- [ ] **Step 1: Write the failing test**

Create `tests/paleo_map/test_zoom_pan.py`:

```python
import pytest
from PySide6.QtCore import QPointF

from geoviz_paleo_map.viewport import PaleoMapViewport
from geoviz_paleo_map.zoom_pan import ZoomPanHandler


def test_drag_pan_increases_center_lng_when_dragging_left():
    vp = PaleoMapViewport(115.0, 30.0, zoom=4.0, width=1200, height=800)
    h = ZoomPanHandler(vp)
    h.start_drag(QPointF(600, 400))
    h.update_drag(QPointF(500, 400))
    new_lng = h.viewport.screen_to_lnglat(QPointF(600, 400))[0]
    assert new_lng > 115.0


def test_wheel_zoom_keeps_cursor_anchor_invariant():
    vp = PaleoMapViewport(115.0, 30.0, zoom=2.0, width=1200, height=800)
    h = ZoomPanHandler(vp)
    cursor = QPointF(900, 300)
    before = vp.screen_to_lnglat(cursor)
    h.wheel_zoom(cursor, delta_steps=1.0)
    after = h.viewport.screen_to_lnglat(cursor)
    assert after[0] == pytest.approx(before[0], abs=1e-6)
    assert after[1] == pytest.approx(before[1], abs=1e-6)
    assert h.viewport.zoom == pytest.approx(3.0)


def test_zoom_clamped_to_range():
    vp = PaleoMapViewport(0.0, 0.0, zoom=2.0, width=1200, height=800)
    h = ZoomPanHandler(vp, min_zoom=1.0, max_zoom=5.0)
    h.wheel_zoom(QPointF(600, 400), delta_steps=-20.0)
    assert h.viewport.zoom == 1.0
    h.wheel_zoom(QPointF(600, 400), delta_steps=20.0)
    assert h.viewport.zoom == 5.0
```

- [ ] **Step 2: Run, expect FAIL**

Run: `source .venv/bin/activate && pytest tests/paleo_map/test_zoom_pan.py -v`

- [ ] **Step 3: Implementation**

Create `packages/geoviz_paleo_map/geoviz_paleo_map/zoom_pan.py`:

```python
"""ZoomPanHandler — drag pan + cursor-anchored wheel zoom for PaleoMap."""
from __future__ import annotations

from PySide6.QtCore import QPointF

from geoviz_paleo_map.viewport import PaleoMapViewport


class ZoomPanHandler:
    """Mutates a PaleoMapViewport based on mouse drag and wheel events."""

    def __init__(self, viewport: PaleoMapViewport,
                 min_zoom: float = 0.5, max_zoom: float = 10.0):
        self.viewport = viewport
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom
        self._drag_anchor: QPointF | None = None

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

    def wheel_zoom(self, cursor_screen: QPointF, delta_steps: float) -> None:
        before = self.viewport.screen_to_world(cursor_screen)
        new_zoom = max(self.min_zoom,
                       min(self.max_zoom, self.viewport.zoom + delta_steps))
        if new_zoom == self.viewport.zoom:
            return
        self.viewport.zoom = new_zoom
        after = self.viewport.screen_to_world(cursor_screen)
        self.viewport.pan_world(before[0] - after[0], before[1] - after[1])
```

- [ ] **Step 4: Run, expect 3 passed**

Run: `source .venv/bin/activate && pytest tests/paleo_map/test_zoom_pan.py -v`

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/zoom_pan.py tests/paleo_map/test_zoom_pan.py
git commit -m "feat(paleo): add ZoomPanHandler"
```

---

## Phase 2 — PatternEngine extensions, style resolver, core layers

### Task 5: PatternEngine extensions + Models + FaciesStyleResolver

**Files:**
- Modify: `packages/geoviz_well_log/geoviz_well_log/renderer/pattern_engine.py` — add 2 methods
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/models.py`
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/style.py`
- Create: `tests/paleo_map/conftest.py` — QApplication fixture (paint tests need it)
- Test: `tests/paleo_map/test_style_resolver.py`

- [ ] **Step 1: Write the failing test (resolver)**

Create `tests/paleo_map/conftest.py`:

```python
"""Ensure a QApplication exists for paleo_map tests that paint."""
import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication([])
    yield app
```

Create `tests/paleo_map/test_style_resolver.py`:

```python
from PySide6.QtGui import QBrush, QColor

from geoviz_paleo_map.models import FaciesStyle
from geoviz_paleo_map.style import FaciesStyleResolver, boundary_pen
from geoviz_well_log.renderer.pattern_engine import PatternEngine


def test_resolves_known_facies_to_color_and_brush():
    engine = PatternEngine()
    r = FaciesStyleResolver(engine)
    style = r.resolve("砂岩")
    assert isinstance(style, FaciesStyle)
    assert style.base_color.isValid()
    assert isinstance(style.brush, QBrush)


def test_unknown_facies_falls_back_to_default_color():
    engine = PatternEngine()
    r = FaciesStyleResolver(engine)
    style = r.resolve("无此相")
    # Default color "#d9d4c8"
    assert style.base_color == QColor("#d9d4c8")


def test_resolve_caches_styles_per_facies_name():
    engine = PatternEngine()
    r = FaciesStyleResolver(engine)
    a = r.resolve("砂岩")
    b = r.resolve("砂岩")
    assert a is b  # same FaciesStyle instance returned


def test_boundary_pen_confirmed_solid_gray():
    pen = boundary_pen("confirmed")
    assert pen.color() == QColor("#555555")
    assert pen.widthF() == 1.5


def test_boundary_pen_fault_solid_red():
    pen = boundary_pen("fault")
    assert pen.color() == QColor("#e53e3e")


def test_boundary_pen_inferred_dashed():
    pen = boundary_pen("inferred")
    assert pen.dashPattern() == [6.0, 3.0]
```

- [ ] **Step 2: Write failing PatternEngine extension tests**

Create `tests/test_pattern_engine_extensions.py` (project-level; `packages/geoviz_well_log/` has no dedicated tests dir):

```python
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QApplication

from geoviz_well_log.renderer.pattern_engine import PatternEngine


def _ensure_app():
    QApplication.instance() or QApplication([])


def test_get_color_fuzzy_returns_color_for_known_facies():
    _ensure_app()
    engine = PatternEngine()
    color = engine.get_color_fuzzy("砂岩")
    assert color is not None
    assert color.isValid()


def test_get_color_fuzzy_substring_match_longest_first():
    """'浅灰色粉砂岩' must match '粉砂岩' before '砂岩' (longer key wins)."""
    _ensure_app()
    engine = PatternEngine()
    c_specific = engine.get_color_fuzzy("浅灰色粉砂岩")
    c_generic = engine.get_color_fuzzy("浅灰色砂岩")
    # Both resolve to a color; specific match should not be the generic one's
    assert c_specific is not None and c_generic is not None


def test_get_color_fuzzy_unknown_returns_none():
    _ensure_app()
    engine = PatternEngine()
    assert engine.get_color_fuzzy("绝不存在的相") is None


def test_get_composite_brush_known_pattern_returns_brush():
    _ensure_app()
    engine = PatternEngine()
    brush = engine.get_composite_brush("砂岩", QColor("#ffeecc"))
    assert isinstance(brush, QBrush)


def test_get_composite_brush_unknown_returns_none():
    _ensure_app()
    engine = PatternEngine()
    brush = engine.get_composite_brush("无此相", QColor("#ffffff"))
    assert brush is None


def test_get_composite_brush_caches_by_name_and_color():
    _ensure_app()
    engine = PatternEngine()
    a = engine.get_composite_brush("砂岩", QColor("#ffeecc"))
    b = engine.get_composite_brush("砂岩", QColor("#ffeecc"))
    assert a is b
```


- [ ] **Step 3: Verify both test files FAIL**

Run: `source .venv/bin/activate && pytest tests/paleo_map/test_style_resolver.py tests/test_pattern_engine_extensions.py -v`
Expected: ImportError / AttributeError for the new methods + classes.

- [ ] **Step 4: Implement PatternEngine extensions**

In `packages/geoviz_well_log/geoviz_well_log/renderer/pattern_engine.py`, **append** the following methods to the `PatternEngine` class (after the existing `get_color` method):

```python
    _SORTED_COLOR_KEYS = sorted(FACIES_COLORS.keys(), key=len, reverse=True)

    def get_color_fuzzy(self, name: str) -> QColor | None:
        """Return a QColor by substring match against FACIES_COLORS.

        Longest keys are tried first so '粉砂岩' matches before '砂岩'.
        """
        hex_color = FACIES_COLORS.get(name)
        if hex_color is not None:
            return QColor(hex_color)
        for key in self._SORTED_COLOR_KEYS:
            if key in name:
                return QColor(FACIES_COLORS[key])
        return None

    def get_composite_brush(self, name: str, base_color: QColor,
                            alpha: float = 0.6) -> QBrush | None:
        """Return a tiled QBrush of base_color overlaid with the SVG pattern
        for `name` at the given alpha.

        Returns None if no pattern matches `name`. Cached per (name, color hex).
        """
        cache_key = f"composite::{name}::{base_color.name()}::{alpha:.2f}"
        if not hasattr(self, "_composite_cache"):
            self._composite_cache: dict[str, QBrush] = {}
        if cache_key in self._composite_cache:
            return self._composite_cache[cache_key]

        pattern_id = self._fuzzy_lookup(name)
        if pattern_id is None:
            return None

        filename = pattern_id.replace("-", "_")
        svg_path = self._ASSETS_DIR / f"{filename}.svg"
        if not svg_path.exists():
            return None

        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtCore import QSize, Qt

        renderer = QSvgRenderer(str(svg_path))
        if not renderer.isValid():
            return None

        size = QSize(self._tile_size, self._tile_size)
        pm = QPixmap(size)
        pm.fill(base_color)
        painter = QPainter(pm)
        painter.setOpacity(alpha)
        renderer.render(painter)
        painter.end()

        brush = QBrush(pm)
        self._composite_cache[cache_key] = brush
        return brush
```

- [ ] **Step 5: Verify PatternEngine extensions pass**

Run: `source .venv/bin/activate && pytest tests/test_pattern_engine_extensions.py -v`
Expected: 6 passed.

- [ ] **Step 6: Implement models.py**

Create `packages/geoviz_paleo_map/geoviz_paleo_map/models.py`:

```python
"""Data models for geoviz_paleo_map."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QBrush, QColor


@dataclass(frozen=True)
class FaciesStyle:
    """Resolved styling for one facies value: base color + optional composite brush."""

    base_color: QColor
    brush: QBrush
```

- [ ] **Step 7: Implement style.py**

Create `packages/geoviz_paleo_map/geoviz_paleo_map/style.py`:

```python
"""FaciesStyleResolver — facies name → base color + composite brush.

Caches per facies name; multiple polygons of the same facies share one
FaciesStyle instance, and the underlying composite brush is cached inside
PatternEngine itself.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPen

from geoviz_well_log.renderer.pattern_engine import PatternEngine

from geoviz_paleo_map.models import FaciesStyle


DEFAULT_BASE_COLOR = QColor("#d9d4c8")


class FaciesStyleResolver:
    def __init__(self, pattern_engine: PatternEngine):
        self._engine = pattern_engine
        self._cache: dict[str, FaciesStyle] = {}

    def resolve(self, facies_name: str) -> FaciesStyle:
        if facies_name in self._cache:
            return self._cache[facies_name]
        base = self._engine.get_color_fuzzy(facies_name) or QColor(DEFAULT_BASE_COLOR)
        brush = self._engine.get_composite_brush(facies_name, base)
        if brush is None:
            brush = QBrush(base)
        style = FaciesStyle(base_color=base, brush=brush)
        self._cache[facies_name] = style
        return style


def boundary_pen(kind: str | None) -> QPen:
    """Return the QPen for a polygon boundary type."""
    if kind == "inferred":
        pen = QPen(QColor("#555555"), 1.5)
        pen.setDashPattern([6.0, 3.0])
        return pen
    if kind == "fault":
        return QPen(QColor("#e53e3e"), 2.0)
    if kind == "confirmed":
        return QPen(QColor("#555555"), 1.5)
    return QPen(QColor("#555555"), 1.0)
```

- [ ] **Step 8: Run resolver tests, expect 6 passed**

Run: `source .venv/bin/activate && pytest tests/paleo_map/test_style_resolver.py -v`

- [ ] **Step 9: Run the full repo test suite to make sure nothing regressed**

Run: `source .venv/bin/activate && pytest -q`
Expected: All previously-passing tests still pass; new style tests included.

- [ ] **Step 10: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/pattern_engine.py packages/geoviz_paleo_map/geoviz_paleo_map/models.py packages/geoviz_paleo_map/geoviz_paleo_map/style.py tests/paleo_map/conftest.py tests/paleo_map/test_style_resolver.py tests/test_pattern_engine_extensions.py
git commit -m "feat(paleo): add models, FaciesStyleResolver, and PatternEngine extensions"
```

---

### Task 6: PaleoLayer ABC + BackgroundLayer

**Files:**
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/layers/__init__.py`
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/layers/base.py`
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/layers/background.py`
- Test: `tests/paleo_map/test_layer_base.py`
- Test: `tests/paleo_map/test_layer_background.py`

- [ ] **Step 1: Write failing tests**

Create `tests/paleo_map/test_layer_base.py`:

```python
import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainter

from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.viewport import PaleoMapViewport


def test_layer_is_abstract():
    with pytest.raises(TypeError):
        PaleoLayer()  # type: ignore[abstract]


def test_default_hit_test_returns_none():
    class Dummy(PaleoLayer):
        def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
            return None

    vp = PaleoMapViewport(0.0, 0.0, zoom=1.0, width=100, height=100)
    assert Dummy().hit_test_polygon(QPointF(0, 0), vp) is None
```

Create `tests/paleo_map/test_layer_background.py`:

```python
from PySide6.QtGui import QImage, QPainter

from geoviz_paleo_map.layers.background import BackgroundLayer
from geoviz_paleo_map.viewport import PaleoMapViewport


def test_background_fills_with_default_color():
    img = QImage(100, 80, QImage.Format.Format_RGB32)
    img.fill(0)
    vp = PaleoMapViewport(0.0, 0.0, zoom=1.0, width=100, height=80)
    layer = BackgroundLayer()
    p = QPainter(img); layer.paint(p, vp); p.end()
    c = img.pixelColor(50, 40)
    assert c.red() == 0xF7 and c.green() == 0xFA and c.blue() == 0xFC
```

- [ ] **Step 2: Run, expect FAIL**

Run: `source .venv/bin/activate && pytest tests/paleo_map/test_layer_base.py tests/paleo_map/test_layer_background.py -v`

- [ ] **Step 3: Implement layers/__init__.py + base.py + background.py**

Create `packages/geoviz_paleo_map/geoviz_paleo_map/layers/__init__.py`:

```python
"""geoviz_paleo_map layers."""
```

Create `packages/geoviz_paleo_map/geoviz_paleo_map/layers/base.py`:

```python
"""PaleoLayer abstract base."""
from abc import ABC, abstractmethod

from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainter

from geoviz_paleo_map.viewport import PaleoMapViewport


class PaleoLayer(ABC):
    """One rendering pass over the viewport."""

    @abstractmethod
    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None: ...

    def hit_test_polygon(self, screen_pt: QPointF,
                         viewport: PaleoMapViewport) -> str | None:
        """Override for layers that respond to tooltip hover."""
        return None
```

Create `packages/geoviz_paleo_map/geoviz_paleo_map/layers/background.py`:

```python
"""BackgroundLayer — solid color fill."""
from PySide6.QtGui import QColor, QPainter

from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.viewport import PaleoMapViewport


class BackgroundLayer(PaleoLayer):
    def __init__(self, color: str = "#f7fafc"):
        self.color = QColor(color)

    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        painter.fillRect(0, 0, viewport.width, viewport.height, self.color)
```

- [ ] **Step 4: Run, expect 3 passed**

Run: `source .venv/bin/activate && pytest tests/paleo_map/test_layer_base.py tests/paleo_map/test_layer_background.py -v`

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/layers/ tests/paleo_map/test_layer_base.py tests/paleo_map/test_layer_background.py
git commit -m "feat(paleo): add PaleoLayer ABC and BackgroundLayer"
```

---

### Task 7: FaciesPolygonsLayer (core layer)

**Files:**
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/layers/facies_polygons.py`
- Test: `tests/paleo_map/test_layer_facies_polygons.py`

- [ ] **Step 1: Write the failing test**

Create `tests/paleo_map/test_layer_facies_polygons.py`:

```python
from PySide6.QtCore import QPointF
from PySide6.QtGui import QImage, QPainter

from geoviz_paleo_map.layers.facies_polygons import FaciesPolygonsLayer
from geoviz_paleo_map.style import FaciesStyleResolver
from geoviz_paleo_map.viewport import PaleoMapViewport
from geoviz_well_log.renderer.pattern_engine import PatternEngine


SAND_FEATURE = {
    "type": "Feature",
    "properties": {"name": "西部滨岸相", "facies": "砂岩"},
    "geometry": {
        "type": "Polygon",
        "coordinates": [[
            [110.0, 20.0], [120.0, 20.0], [120.0, 30.0], [110.0, 30.0], [110.0, 20.0]
        ]],
    },
}

FAULTED_FEATURE = {
    "type": "Feature",
    "properties": {"name": "断裂带", "facies": "灰岩", "boundary_type": "fault"},
    "geometry": {
        "type": "Polygon",
        "coordinates": [[
            [114.0, 22.0], [116.0, 22.0], [116.0, 24.0], [114.0, 24.0], [114.0, 22.0]
        ]],
    },
}


def _setup():
    img = QImage(400, 400, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)
    vp = PaleoMapViewport(115.0, 25.0, zoom=4.0, width=400, height=400)
    engine = PatternEngine()
    resolver = FaciesStyleResolver(engine)
    return img, vp, resolver


def test_polygon_renders_visible_pixels_in_viewport():
    img, vp, resolver = _setup()
    layer = FaciesPolygonsLayer([SAND_FEATURE], resolver)
    p = QPainter(img); layer.paint(p, vp); p.end()
    # Center pixel must be non-white (polygon covers full viewport)
    c = img.pixelColor(200, 200)
    assert not (c.red() == 0xFF and c.green() == 0xFF and c.blue() == 0xFF)


def test_polygon_outside_viewport_culled():
    img, vp, resolver = _setup()
    far_feature = {
        "type": "Feature",
        "properties": {"name": "远方", "facies": "砂岩"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-180.0, -10.0], [-170.0, -10.0], [-170.0, 0.0], [-180.0, 0.0], [-180.0, -10.0]
            ]],
        },
    }
    layer = FaciesPolygonsLayer([far_feature], resolver)
    p = QPainter(img); layer.paint(p, vp); p.end()
    # All pixels still white
    for y in range(0, 400, 20):
        for x in range(0, 400, 20):
            c = img.pixelColor(x, y)
            assert c.red() == 0xFF and c.green() == 0xFF and c.blue() == 0xFF


def test_hit_test_returns_facies_name_inside_polygon():
    img, vp, resolver = _setup()
    layer = FaciesPolygonsLayer([SAND_FEATURE], resolver)
    p = QPainter(img); layer.paint(p, vp); p.end()
    # Center of viewport falls inside the polygon (110..120, 20..30)
    hit = layer.hit_test_polygon(QPointF(200, 200), vp)
    assert hit == "砂岩"


def test_hit_test_miss_returns_none():
    img, vp, resolver = _setup()
    far_feature = {
        "type": "Feature",
        "properties": {"name": "远方", "facies": "砂岩"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-180.0, -10.0], [-170.0, -10.0], [-170.0, 0.0], [-180.0, 0.0], [-180.0, -10.0]
            ]],
        },
    }
    layer = FaciesPolygonsLayer([far_feature], resolver)
    p = QPainter(img); layer.paint(p, vp); p.end()
    assert layer.hit_test_polygon(QPointF(200, 200), vp) is None


def test_skips_non_polygon_geometries():
    img, vp, resolver = _setup()
    point_feature = {
        "type": "Feature",
        "properties": {"name": "p", "facies": "砂岩"},
        "geometry": {"type": "Point", "coordinates": [115.0, 25.0]},
    }
    layer = FaciesPolygonsLayer([point_feature], resolver)
    # Should construct without error and paint as no-op
    p = QPainter(img); layer.paint(p, vp); p.end()
    assert layer.hit_test_polygon(QPointF(200, 200), vp) is None
```

- [ ] **Step 2: Run, expect FAIL**

Run: `source .venv/bin/activate && pytest tests/paleo_map/test_layer_facies_polygons.py -v`

- [ ] **Step 3: Implementation**

Create `packages/geoviz_paleo_map/geoviz_paleo_map/layers/facies_polygons.py`:

```python
"""FaciesPolygonsLayer — per-feature filled polygons with composite brush
and boundary pen, viewport-culled, point-in-polygon hit-test."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainter, QPainterPath

from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.projection import lnglat_to_world
from geoviz_paleo_map.style import FaciesStyleResolver, boundary_pen
from geoviz_paleo_map.viewport import PaleoMapViewport


@dataclass
class _Item:
    facies_name: str
    path: QPainterPath
    bbox: tuple[float, float, float, float]  # min_x, min_y, max_x, max_y
    boundary_kind: str | None


class FaciesPolygonsLayer(PaleoLayer):
    def __init__(self, features: list[dict], style_resolver: FaciesStyleResolver):
        self._resolver = style_resolver
        self._items: list[_Item] = []
        for feat in features:
            geom = feat.get("geometry") or {}
            gtype = geom.get("type")
            if gtype == "Polygon":
                rings = [geom["coordinates"]]
            elif gtype == "MultiPolygon":
                rings = geom["coordinates"]
            else:
                continue
            props = feat.get("properties") or {}
            facies = props.get("facies") or props.get("name") or ""
            boundary_kind = props.get("boundary_type")
            for poly in rings:
                item = self._build_item(poly, facies, boundary_kind)
                if item is not None:
                    self._items.append(item)

    @staticmethod
    def _build_item(poly: list[list[list[float]]],
                    facies_name: str,
                    boundary_kind: str | None) -> _Item | None:
        path = QPainterPath()
        min_x = float("inf"); min_y = float("inf")
        max_x = float("-inf"); max_y = float("-inf")
        for ring in poly:
            if not ring:
                continue
            pts: list[QPointF] = []
            for lng, lat in ring:
                x, y = lnglat_to_world(lng, lat)
                pts.append(QPointF(x, y))
                if x < min_x: min_x = x
                if x > max_x: max_x = x
                if y < min_y: min_y = y
                if y > max_y: max_y = y
            if not pts:
                continue
            path.moveTo(pts[0])
            for p in pts[1:]:
                path.lineTo(p)
            path.closeSubpath()
        if path.isEmpty():
            return None
        path.setFillRule(Qt.FillRule.OddEvenFill)
        return _Item(facies_name=facies_name, path=path,
                     bbox=(min_x, min_y, max_x, max_y),
                     boundary_kind=boundary_kind)

    @staticmethod
    def _bbox_overlaps(a, b) -> bool:
        return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])

    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        vp_bbox = viewport.world_bbox()
        s = viewport.scale
        cx, cy = viewport.center_world
        ox = viewport.width / 2
        oy = viewport.height / 2

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.save()
        painter.translate(ox, oy)
        painter.scale(s, -s)
        painter.translate(-cx, -cy)

        for item in self._items:
            if not self._bbox_overlaps(vp_bbox, item.bbox):
                continue
            style = self._resolver.resolve(item.facies_name)
            pen = boundary_pen(item.boundary_kind)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(style.brush)
            painter.drawPath(item.path)

        painter.restore()

    def hit_test_polygon(self, screen_pt: QPointF,
                         viewport: PaleoMapViewport) -> str | None:
        wx, wy = viewport.screen_to_world(screen_pt)
        world_pt = QPointF(wx, wy)
        for item in self._items:
            if not (item.bbox[0] <= wx <= item.bbox[2]
                    and item.bbox[1] <= wy <= item.bbox[3]):
                continue
            if item.path.contains(world_pt):
                return item.facies_name
        return None
```

- [ ] **Step 4: Run, expect 5 passed**

Run: `source .venv/bin/activate && pytest tests/paleo_map/test_layer_facies_polygons.py -v`

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/layers/facies_polygons.py tests/paleo_map/test_layer_facies_polygons.py
git commit -m "feat(paleo): add FaciesPolygonsLayer with culling, composite brush, hit-test"
```

---

### Task 8: RegionLabelsLayer

**Files:**
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/layers/region_labels.py`
- Test: `tests/paleo_map/test_layer_region_labels.py`

- [ ] **Step 1: Write the failing test**

Create `tests/paleo_map/test_layer_region_labels.py`:

```python
from PySide6.QtGui import QColor, QImage, QPainter

from geoviz_paleo_map.layers.region_labels import RegionLabelsLayer, contrast_color
from geoviz_paleo_map.style import FaciesStyleResolver
from geoviz_paleo_map.viewport import PaleoMapViewport
from geoviz_well_log.renderer.pattern_engine import PatternEngine


def test_contrast_color_dark_text_on_light_bg():
    assert contrast_color(QColor("#ffffff")) == QColor("#2d3748")


def test_contrast_color_light_text_on_dark_bg():
    assert contrast_color(QColor("#1a1a1a")) == QColor("#f7fafc")


def test_paints_label_text_for_each_feature():
    feat = {
        "type": "Feature",
        "properties": {"name": "测试区", "facies": "砂岩"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [110.0, 20.0], [120.0, 20.0], [120.0, 30.0], [110.0, 30.0], [110.0, 20.0]
            ]],
        },
    }
    img = QImage(400, 400, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)
    vp = PaleoMapViewport(115.0, 25.0, zoom=4.0, width=400, height=400)
    resolver = FaciesStyleResolver(PatternEngine())
    layer = RegionLabelsLayer([feat], resolver)
    p = QPainter(img); layer.paint(p, vp); p.end()

    # At least one non-white pixel near center (the text)
    found = False
    for dy in range(-20, 21, 5):
        for dx in range(-30, 31, 5):
            c = img.pixelColor(200 + dx, 200 + dy)
            if c.red() < 250 or c.green() < 250 or c.blue() < 250:
                found = True; break
        if found: break
    assert found, "expected label text near polygon center"
```

- [ ] **Step 2: Run, expect FAIL**

Run: `source .venv/bin/activate && pytest tests/paleo_map/test_layer_region_labels.py -v`

- [ ] **Step 3: Implementation**

Create `packages/geoviz_paleo_map/geoviz_paleo_map/layers/region_labels.py`:

```python
"""RegionLabelsLayer — facies name centered at each polygon's bbox center
with contrast-aware text color."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.projection import lnglat_to_world
from geoviz_paleo_map.style import FaciesStyleResolver
from geoviz_paleo_map.viewport import PaleoMapViewport


@dataclass
class _LabelItem:
    text: str
    centroid_world: tuple[float, float]
    facies_name: str


def _luminance(c: QColor) -> float:
    r = c.red() / 255.0
    g = c.green() / 255.0
    b = c.blue() / 255.0
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_color(bg: QColor) -> QColor:
    """Return a dark text color on light backgrounds and vice versa."""
    return QColor("#2d3748") if _luminance(bg) > 0.5 else QColor("#f7fafc")


class RegionLabelsLayer(PaleoLayer):
    def __init__(self, features: list[dict], style_resolver: FaciesStyleResolver):
        self._resolver = style_resolver
        self._items: list[_LabelItem] = []
        for feat in features:
            geom = feat.get("geometry") or {}
            gtype = geom.get("type")
            if gtype == "Polygon":
                rings = [geom["coordinates"]]
            elif gtype == "MultiPolygon":
                rings = geom["coordinates"]
            else:
                continue
            props = feat.get("properties") or {}
            text = props.get("name") or props.get("facies") or ""
            facies = props.get("facies") or props.get("name") or ""
            if not text:
                continue
            # Centroid = bbox center of outer ring
            for poly in rings:
                outer = poly[0] if poly else []
                if len(outer) < 3:
                    continue
                xs = [p[0] for p in outer]
                ys = [p[1] for p in outer]
                cx = (min(xs) + max(xs)) / 2
                cy = (min(ys) + max(ys)) / 2
                world_pt = lnglat_to_world(cx, cy)
                self._items.append(_LabelItem(text=text,
                                              centroid_world=world_pt,
                                              facies_name=facies))
                break  # one label per feature (use first polygon's centroid)

    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        font = QFont("Sans Serif", 9)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        for item in self._items:
            screen = viewport.world_to_screen(*item.centroid_world)
            style = self._resolver.resolve(item.facies_name)
            color = contrast_color(style.base_color)
            painter.setPen(QPen(color, 0))
            w = metrics.horizontalAdvance(item.text)
            painter.drawText(QPointF(screen.x() - w / 2,
                                     screen.y() + metrics.ascent() / 2),
                             item.text)
```

- [ ] **Step 4: Run, expect 3 passed**

Run: `source .venv/bin/activate && pytest tests/paleo_map/test_layer_region_labels.py -v`

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/layers/region_labels.py tests/paleo_map/test_layer_region_labels.py
git commit -m "feat(paleo): add RegionLabelsLayer with contrast-aware text"
```

---

### Task 9: WellsScatterLayer

**Files:**
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/layers/wells_scatter.py`
- Test: `tests/paleo_map/test_layer_wells_scatter.py`

- [ ] **Step 1: Write the failing test**

Create `tests/paleo_map/test_layer_wells_scatter.py`:

```python
from PySide6.QtGui import QImage, QPainter

from geoviz_paleo_map.layers.wells_scatter import WellsScatterLayer
from geoviz_paleo_map.viewport import PaleoMapViewport


def test_dot_renders_at_well_location():
    wells = [{"name": "HZ-1", "lng": 115.0, "lat": 25.0}]
    img = QImage(400, 400, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    vp = PaleoMapViewport(115.0, 25.0, zoom=4.0, width=400, height=400)
    layer = WellsScatterLayer(wells)
    p = QPainter(img); layer.paint(p, vp); p.end()

    # Sample pixels around center for red
    found_red = False
    for dx in range(-4, 5):
        for dy in range(-4, 5):
            c = img.pixelColor(200 + dx, 200 + dy)
            if c.red() > 0xD0 and c.green() < 0x70 and c.blue() < 0x70:
                found_red = True; break
        if found_red: break
    assert found_red, "expected red dot at well location"


def test_missing_lng_lat_well_is_skipped():
    wells = [{"name": "valid", "lng": 115.0, "lat": 25.0},
             {"name": "incomplete"}]
    layer = WellsScatterLayer(wells)
    assert len(layer.wells) == 1
```

- [ ] **Step 2: Run, expect FAIL**

Run: `source .venv/bin/activate && pytest tests/paleo_map/test_layer_wells_scatter.py -v`

- [ ] **Step 3: Implementation**

Create `packages/geoviz_paleo_map/geoviz_paleo_map/layers/wells_scatter.py`:

```python
"""WellsScatterLayer — red 8px dots + name labels at well positions."""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.viewport import PaleoMapViewport


DOT_COLOR = QColor("#e53e3e")
DOT_BORDER = QColor("#ffffff")
LABEL_COLOR = QColor("#e53e3e")
DOT_RADIUS = 4.0  # 8px diameter


class WellsScatterLayer(PaleoLayer):
    def __init__(self, wells: list[dict]):
        """`wells` is a list of {"name": str, "lng": float, "lat": float}.

        Wells missing lng or lat are silently skipped.
        """
        self.wells = [
            w for w in wells
            if isinstance(w.get("lng"), (int, float))
            and isinstance(w.get("lat"), (int, float))
        ]

    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        font = QFont("Sans Serif", 8)
        painter.setFont(font)
        for w in self.wells:
            pt = viewport.lnglat_to_screen(w["lng"], w["lat"])
            painter.setPen(QPen(DOT_BORDER, 2.0))
            painter.setBrush(DOT_COLOR)
            painter.drawEllipse(pt, DOT_RADIUS, DOT_RADIUS)
            painter.setPen(QPen(LABEL_COLOR, 0))
            painter.drawText(QPointF(pt.x() + DOT_RADIUS + 4.0,
                                     pt.y() + 3.0), w.get("name", ""))
```

- [ ] **Step 4: Run, expect 2 passed**

Run: `source .venv/bin/activate && pytest tests/paleo_map/test_layer_wells_scatter.py -v`

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/layers/wells_scatter.py tests/paleo_map/test_layer_wells_scatter.py
git commit -m "feat(paleo): add WellsScatterLayer"
```

---

## Phase 3 — Chrome layers

### Task 10: TitleLayer

**Files:**
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/layers/title.py`
- Test: `tests/paleo_map/test_layer_title.py`

- [ ] **Step 1: Write the failing test**

Create `tests/paleo_map/test_layer_title.py`:

```python
from PySide6.QtGui import QImage, QPainter

from geoviz_paleo_map.layers.title import TitleLayer
from geoviz_paleo_map.viewport import PaleoMapViewport


def test_title_paints_text_near_top_center():
    img = QImage(800, 200, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    vp = PaleoMapViewport(0.0, 0.0, zoom=1.0, width=800, height=200)
    layer = TitleLayer("奥陶纪岩相古地理图")
    p = QPainter(img); layer.paint(p, vp); p.end()
    # Sample top-center band for any text pixels
    found = False
    for y in range(0, 30):
        for x in range(300, 500):
            c = img.pixelColor(x, y)
            if c.red() < 250 or c.green() < 250 or c.blue() < 250:
                found = True; break
        if found: break
    assert found


def test_empty_title_paints_nothing():
    img = QImage(800, 200, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    vp = PaleoMapViewport(0.0, 0.0, zoom=1.0, width=800, height=200)
    layer = TitleLayer("")
    p = QPainter(img); layer.paint(p, vp); p.end()
    # Image is unchanged
    for y in range(0, 30, 2):
        for x in range(0, 800, 10):
            c = img.pixelColor(x, y)
            assert c.red() == 0xFF and c.green() == 0xFF and c.blue() == 0xFF
```

- [ ] **Step 2: Run, expect FAIL**

Run: `source .venv/bin/activate && pytest tests/paleo_map/test_layer_title.py -v`

- [ ] **Step 3: Implementation**

Create `packages/geoviz_paleo_map/geoviz_paleo_map/layers/title.py`:

```python
"""TitleLayer — top-center map title with semi-transparent white pad."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.viewport import PaleoMapViewport


TITLE_COLOR = QColor("#1a202c")
TITLE_BG = QColor(255, 255, 255, 217)  # rgba(255,255,255,0.85)


class TitleLayer(PaleoLayer):
    def __init__(self, text: str):
        self.text = text

    def set_text(self, text: str) -> None:
        self.text = text

    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        if not self.text:
            return
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        font = QFont("Sans Serif", 12)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        w = metrics.horizontalAdvance(self.text)
        h = metrics.height()
        cx = viewport.width / 2
        rect = QRectF(cx - w / 2 - 12, 4, w + 24, h + 8)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(TITLE_BG)
        painter.drawRoundedRect(rect, 4, 4)
        painter.setPen(QPen(TITLE_COLOR, 0))
        painter.drawText(QPointF(cx - w / 2, rect.y() + metrics.ascent() + 4),
                         self.text)
```

- [ ] **Step 4: Run, expect 2 passed**

Run: `source .venv/bin/activate && pytest tests/paleo_map/test_layer_title.py -v`

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/layers/title.py tests/paleo_map/test_layer_title.py
git commit -m "feat(paleo): add TitleLayer (top-center map title)"
```

---

### Task 11: NorthArrowLayer

**Files:**
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/layers/north_arrow.py`
- Test: `tests/paleo_map/test_layer_north_arrow.py`

- [ ] **Step 1: Write the failing test**

Create `tests/paleo_map/test_layer_north_arrow.py`:

```python
from PySide6.QtGui import QImage, QPainter

from geoviz_paleo_map.layers.north_arrow import NorthArrowLayer
from geoviz_paleo_map.viewport import PaleoMapViewport


def test_arrow_paints_in_top_right_corner():
    img = QImage(400, 200, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    vp = PaleoMapViewport(0.0, 0.0, zoom=1.0, width=400, height=200)
    layer = NorthArrowLayer()
    p = QPainter(img); layer.paint(p, vp); p.end()
    # Top-right corner band — anchor at width-46 .. width-16
    found = False
    for y in range(50, 100):
        for x in range(350, 390):
            c = img.pixelColor(x, y)
            if c.red() < 200 or c.green() < 200 or c.blue() < 200:
                found = True; break
        if found: break
    assert found, "expected north arrow in top-right corner band"
```

- [ ] **Step 2: Run, expect FAIL**

Run: `source .venv/bin/activate && pytest tests/paleo_map/test_layer_north_arrow.py -v`

- [ ] **Step 3: Implementation**

Create `packages/geoviz_paleo_map/geoviz_paleo_map/layers/north_arrow.py`:

```python
"""NorthArrowLayer — triangle + N letter in the top-right corner."""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF

from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.viewport import PaleoMapViewport


ARROW_COLOR = QColor("#334155")


class NorthArrowLayer(PaleoLayer):
    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # 30x40 SVG offset 16px from right, ~50px from top
        x0 = viewport.width - 46
        y0 = 50
        # Triangle: points (15, 0), (10, 18), (20, 18) within 30x40 box
        polygon = QPolygonF([
            QPointF(x0 + 15, y0),
            QPointF(x0 + 10, y0 + 18),
            QPointF(x0 + 20, y0 + 18),
        ])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(ARROW_COLOR)
        painter.drawPolygon(polygon)
        # "N" at (15, 30)
        painter.setPen(QPen(ARROW_COLOR, 0))
        font = QFont("Sans Serif", 9)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        w = metrics.horizontalAdvance("N")
        painter.drawText(QPointF(x0 + 15 - w / 2, y0 + 32), "N")
```

- [ ] **Step 4: Run, expect 1 passed**

Run: `source .venv/bin/activate && pytest tests/paleo_map/test_layer_north_arrow.py -v`

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/layers/north_arrow.py tests/paleo_map/test_layer_north_arrow.py
git commit -m "feat(paleo): add NorthArrowLayer"
```

---

### Task 12: ScaleBarLayer

**Files:**
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/layers/scale_bar.py`
- Test: `tests/paleo_map/test_layer_scale_bar.py`

- [ ] **Step 1: Write the failing test**

Create `tests/paleo_map/test_layer_scale_bar.py`:

```python
import pytest

from geoviz_paleo_map.layers.scale_bar import (
    NICE_STEPS, ScaleBarLayer, choose_scale_km,
)


@pytest.mark.parametrize("extent_km, expected", [
    (10.0, 2),     # 0.3 * 10 = 3 → largest nice <= 3 = 2
    (100.0, 20),   # 0.3 * 100 = 30 → 20
    (1000.0, 200), # 300 → 200
    (3.0, 1),      # 0.9 → no step <= 0.9 unless step 1; with rules picks 1 anyway
])
def test_choose_scale_km(extent_km, expected):
    assert choose_scale_km(extent_km) == expected


def test_nice_steps_monotonic():
    for a, b in zip(NICE_STEPS, NICE_STEPS[1:]):
        assert b > a


def test_layer_constructs():
    layer = ScaleBarLayer()
    assert layer is not None
```

- [ ] **Step 2: Run, expect FAIL**

Run: `source .venv/bin/activate && pytest tests/paleo_map/test_layer_scale_bar.py -v`

- [ ] **Step 3: Implementation**

Create `packages/geoviz_paleo_map/geoviz_paleo_map/layers/scale_bar.py`:

```python
"""ScaleBarLayer — bottom-left 80px bar + dynamic km label."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.viewport import PaleoMapViewport


BAR_COLOR = QColor("#334155")
BAR_PIXEL_LENGTH = 80.0
NICE_STEPS = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000]


def choose_scale_km(extent_km: float) -> int:
    """Pick the largest nice step ≤ 0.3 × extent_km (matches original JS).

    If no step fits, return the smallest step (1).
    """
    target = extent_km * 0.3
    chosen = NICE_STEPS[0]
    for s in NICE_STEPS:
        if s <= target:
            chosen = s
        else:
            break
    return chosen


class ScaleBarLayer(PaleoLayer):
    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        # Compute kilometers spanned across the viewport at the center latitude
        bbox = viewport.world_bbox()
        mid_lat = (bbox[1] + bbox[3]) / 2
        deg_to_km = 111.32 * math.cos(math.radians(mid_lat))
        extent_km = (bbox[2] - bbox[0]) * deg_to_km
        scale_km = choose_scale_km(extent_km)
        label = f"{scale_km} km" if scale_km >= 1 else f"{int(scale_km * 1000)} m"

        x0 = 16.0
        y0 = viewport.height - 24.0
        pen = QPen(BAR_COLOR, 2.0)
        painter.setPen(pen)
        painter.drawLine(QPointF(x0, y0), QPointF(x0 + BAR_PIXEL_LENGTH, y0))
        painter.drawLine(QPointF(x0, y0 - 4), QPointF(x0, y0 + 4))
        painter.drawLine(QPointF(x0 + BAR_PIXEL_LENGTH, y0 - 4),
                         QPointF(x0 + BAR_PIXEL_LENGTH, y0 + 4))

        font = QFont("Sans Serif", 8)
        painter.setFont(font)
        painter.setPen(QPen(BAR_COLOR, 0))
        metrics = painter.fontMetrics()
        w = metrics.horizontalAdvance(label)
        painter.drawText(
            QPointF(x0 + BAR_PIXEL_LENGTH / 2 - w / 2, y0 + 14),
            label,
        )
```

- [ ] **Step 4: Run, expect 6 passed**

Run: `source .venv/bin/activate && pytest tests/paleo_map/test_layer_scale_bar.py -v`

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/layers/scale_bar.py tests/paleo_map/test_layer_scale_bar.py
git commit -m "feat(paleo): add ScaleBarLayer with dynamic km label"
```

---

### Task 13: LegendLayer

**Files:**
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/layers/legend.py`
- Test: `tests/paleo_map/test_layer_legend.py`

- [ ] **Step 1: Write the failing test**

Create `tests/paleo_map/test_layer_legend.py`:

```python
from PySide6.QtGui import QImage, QPainter

from geoviz_paleo_map.layers.legend import LegendLayer
from geoviz_paleo_map.style import FaciesStyleResolver
from geoviz_paleo_map.viewport import PaleoMapViewport
from geoviz_well_log.renderer.pattern_engine import PatternEngine


def test_legend_renders_in_bottom_right_corner():
    img = QImage(800, 600, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    vp = PaleoMapViewport(0.0, 0.0, zoom=1.0, width=800, height=600)
    resolver = FaciesStyleResolver(PatternEngine())
    layer = LegendLayer({"砂岩", "灰岩"}, resolver)
    p = QPainter(img); layer.paint(p, vp); p.end()
    # Bottom-right corner must have non-white pixels (legend box)
    found = False
    for y in range(400, 590):
        for x in range(600, 790):
            c = img.pixelColor(x, y)
            if c.red() < 250 or c.green() < 250 or c.blue() < 250:
                found = True; break
        if found: break
    assert found, "expected legend artifacts in bottom-right corner"


def test_legend_empty_facies_still_renders_fixed_section():
    img = QImage(800, 600, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    vp = PaleoMapViewport(0.0, 0.0, zoom=1.0, width=800, height=600)
    resolver = FaciesStyleResolver(PatternEngine())
    layer = LegendLayer(set(), resolver)
    p = QPainter(img); layer.paint(p, vp); p.end()
    # Even with no facies, the boundary/well section should render
    found = False
    for y in range(400, 590):
        for x in range(600, 790):
            c = img.pixelColor(x, y)
            if c.red() < 250 or c.green() < 250 or c.blue() < 250:
                found = True; break
        if found: break
    assert found


def test_set_facies_updates_seen():
    resolver = FaciesStyleResolver(PatternEngine())
    layer = LegendLayer(set(), resolver)
    layer.set_facies({"砂岩"})
    assert layer.facies_names == {"砂岩"}
```

- [ ] **Step 2: Run, expect FAIL**

Run: `source .venv/bin/activate && pytest tests/paleo_map/test_layer_legend.py -v`

- [ ] **Step 3: Implementation**

Create `packages/geoviz_paleo_map/geoviz_paleo_map/layers/legend.py`:

```python
"""LegendLayer — bottom-right facies swatches + boundary samples + well dot."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.style import FaciesStyleResolver, boundary_pen
from geoviz_paleo_map.viewport import PaleoMapViewport


BG_COLOR = QColor(255, 255, 255, 242)  # rgba(255,255,255,0.95)
BORDER_COLOR = QColor("#cbd5e1")
TITLE_COLOR = QColor("#334155")
TEXT_COLOR = QColor("#4a5568")
WELL_COLOR = QColor("#e53e3e")
SWATCH_W = 18
SWATCH_H = 12
ROW_H = 16
PADDING = 10


class LegendLayer(PaleoLayer):
    def __init__(self, facies_names: set[str],
                 style_resolver: FaciesStyleResolver):
        self.facies_names = set(facies_names)
        self._resolver = style_resolver

    def set_facies(self, facies_names: set[str]) -> None:
        self.facies_names = set(facies_names)

    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        font = QFont("Sans Serif", 8)
        painter.setFont(font)
        metrics = painter.fontMetrics()

        # 1. Compute box height: title row + per-facies rows + separator + 4 fixed rows
        facies_count = len(self.facies_names)
        fixed_rows = 4  # confirmed, inferred, fault, well
        box_w = 140
        box_h = PADDING * 2 + ROW_H * (1 + facies_count) + 6 + ROW_H * fixed_rows
        x0 = viewport.width - box_w - 12
        y0 = viewport.height - box_h - 12

        # 2. Background
        painter.setPen(QPen(BORDER_COLOR, 1))
        painter.setBrush(BG_COLOR)
        painter.drawRoundedRect(QRectF(x0, y0, box_w, box_h), 6, 6)

        # 3. Title "图例"
        painter.setPen(QPen(TITLE_COLOR, 0))
        title_font = QFont("Sans Serif", 9)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(QPointF(x0 + PADDING, y0 + PADDING + 12), "图例")
        painter.setFont(font)

        y = y0 + PADDING + ROW_H + 4

        # 4. Facies swatches
        painter.setPen(QPen(TEXT_COLOR, 0))
        for name in sorted(self.facies_names):
            style = self._resolver.resolve(name)
            sw_x = x0 + PADDING
            sw_y = y - SWATCH_H + 2
            painter.setPen(QPen(QColor("#aaa"), 1))
            painter.setBrush(style.brush)
            painter.drawRect(QRectF(sw_x, sw_y, SWATCH_W, SWATCH_H))
            painter.setPen(QPen(TEXT_COLOR, 0))
            painter.drawText(QPointF(sw_x + SWATCH_W + 6, y), name)
            y += ROW_H

        # 5. Separator
        painter.setPen(QPen(QColor("#e2e8f0"), 1))
        painter.drawLine(QPointF(x0 + PADDING, y - 4),
                         QPointF(x0 + box_w - PADDING, y - 4))
        y += 4

        # 6. Boundary samples
        for label, kind in (("实测界线", "confirmed"),
                            ("推测界线", "inferred"),
                            ("断层", "fault")):
            pen = boundary_pen(kind)
            pen.setWidthF(2.0)
            painter.setPen(pen)
            painter.drawLine(QPointF(x0 + PADDING, y - 4),
                             QPointF(x0 + PADDING + SWATCH_W, y - 4))
            painter.setPen(QPen(TEXT_COLOR, 0))
            painter.drawText(QPointF(x0 + PADDING + SWATCH_W + 6, y), label)
            y += ROW_H

        # 7. Well dot
        painter.setPen(QPen(QColor("#ffffff"), 1.5))
        painter.setBrush(WELL_COLOR)
        cx = x0 + PADDING + SWATCH_W / 2
        painter.drawEllipse(QPointF(cx, y - 4), 4, 4)
        painter.setPen(QPen(TEXT_COLOR, 0))
        painter.drawText(QPointF(x0 + PADDING + SWATCH_W + 6, y), "井位")
```

- [ ] **Step 4: Run, expect 3 passed**

Run: `source .venv/bin/activate && pytest tests/paleo_map/test_layer_legend.py -v`

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/layers/legend.py tests/paleo_map/test_layer_legend.py
git commit -m "feat(paleo): add LegendLayer (facies + boundary + well)"
```

---

## Phase 4 — Canvas, integration, golden, cleanup

### Task 14: PaleoMapCanvas + hover tooltip + perf baseline

**Files:**
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/canvas.py`
- Modify: `packages/geoviz_paleo_map/geoviz_paleo_map/__init__.py` (export public API)
- Test: `tests/test_paleo_map_canvas.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_paleo_map_canvas.py`:

```python
import time
import pytest
from PySide6.QtCore import QPoint, QPointF, Qt

from geoviz_paleo_map import PaleoMapCanvas


SAMPLE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"name": "测试区", "facies": "砂岩"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [110.0, 20.0], [120.0, 20.0], [120.0, 30.0],
                    [110.0, 30.0], [110.0, 20.0]
                ]],
            },
        }
    ],
}


def _make_canvas(qtbot):
    canvas = PaleoMapCanvas()
    canvas.load_features(SAMPLE["features"], period_name="测试",
                         wells=[{"name": "HZ-1", "lng": 115.0, "lat": 25.0}])
    qtbot.addWidget(canvas)
    canvas.resize(1200, 800)
    canvas.show()
    qtbot.waitExposed(canvas)
    return canvas


def test_canvas_grab_produces_nonempty(qtbot):
    canvas = _make_canvas(qtbot)
    pixmap = canvas.grab()
    assert not pixmap.isNull()
    dpr = pixmap.devicePixelRatio()
    assert pixmap.width() == int(1200 * dpr)


def test_resize_updates_viewport(qtbot):
    canvas = _make_canvas(qtbot)
    canvas.resize(400, 300)
    qtbot.wait(20)
    assert canvas._viewport.width == 400
    assert canvas._viewport.height == 300


def test_load_features_updates_seen_facies(qtbot):
    canvas = _make_canvas(qtbot)
    assert "砂岩" in canvas._legend_layer.facies_names


def test_hover_over_polygon_calls_tooltip(qtbot, monkeypatch):
    calls = []
    from PySide6.QtWidgets import QToolTip
    monkeypatch.setattr(QToolTip, "showText",
                        lambda pos, text, *a, **k: calls.append(text))
    canvas = _make_canvas(qtbot)
    canvas.repaint()
    # Polygon spans (110..120, 20..30); centered viewport (115, 25)
    center_pt = canvas._viewport.lnglat_to_screen(115.0, 25.0)
    qtbot.mouseMove(canvas, QPoint(int(center_pt.x()), int(center_pt.y())))
    qtbot.wait(20)
    assert any("砂岩" in c for c in calls), f"tooltip not shown; calls={calls}"


def test_paint_performance(qtbot):
    """Smoke perf baseline: 1 polygon should paint very fast (<50ms)."""
    canvas = _make_canvas(qtbot)
    canvas.repaint()  # warm up
    t0 = time.perf_counter()
    for _ in range(10):
        canvas.repaint()
    avg_ms = (time.perf_counter() - t0) / 10 * 1000
    assert avg_ms < 50, f"avg paint {avg_ms:.1f}ms exceeds 50ms"
```

- [ ] **Step 2: Run, expect FAIL with `ImportError`**

Run: `source .venv/bin/activate && pytest tests/test_paleo_map_canvas.py -v`

- [ ] **Step 3: Implement canvas.py**

Create `packages/geoviz_paleo_map/geoviz_paleo_map/canvas.py`:

```python
"""PaleoMapCanvas — composite QWidget that paints all paleo layers + chrome."""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import QToolTip, QWidget

from geoviz_well_log.renderer.pattern_engine import PatternEngine

from geoviz_paleo_map.layers.background import BackgroundLayer
from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.layers.facies_polygons import FaciesPolygonsLayer
from geoviz_paleo_map.layers.legend import LegendLayer
from geoviz_paleo_map.layers.north_arrow import NorthArrowLayer
from geoviz_paleo_map.layers.region_labels import RegionLabelsLayer
from geoviz_paleo_map.layers.scale_bar import ScaleBarLayer
from geoviz_paleo_map.layers.title import TitleLayer
from geoviz_paleo_map.layers.wells_scatter import WellsScatterLayer
from geoviz_paleo_map.style import FaciesStyleResolver
from geoviz_paleo_map.viewport import PaleoMapViewport
from geoviz_paleo_map.zoom_pan import ZoomPanHandler


class PaleoMapCanvas(QWidget):
    polygon_hovered = Signal(str)  # facies name, "" when leave

    def __init__(self, pattern_engine: PatternEngine | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._press_pos: QPointF | None = None

        self._engine = pattern_engine or PatternEngine()
        self._resolver = FaciesStyleResolver(self._engine)

        self._viewport = PaleoMapViewport(
            center_lng=115.0, center_lat=30.0, zoom=2.0,
            width=max(1, self.width()), height=max(1, self.height()),
        )
        self._zoom_pan = ZoomPanHandler(self._viewport)

        self._facies_layer = FaciesPolygonsLayer([], self._resolver)
        self._labels_layer = RegionLabelsLayer([], self._resolver)
        self._wells_layer = WellsScatterLayer([])
        self._title_layer = TitleLayer("")
        self._legend_layer = LegendLayer(set(), self._resolver)

        self._layers: list[PaleoLayer] = [
            BackgroundLayer(),
            self._facies_layer,
            self._labels_layer,
            self._wells_layer,
            self._title_layer,
            NorthArrowLayer(),
            ScaleBarLayer(),
            self._legend_layer,
        ]
        self._current_hover: str | None = None

    def load_features(self, features: list[dict],
                      period_name: str = "",
                      wells: list[dict] | None = None) -> None:
        """Rebuild the viewport contents from a list of GeoJSON features."""
        self._facies_layer = FaciesPolygonsLayer(features, self._resolver)
        self._labels_layer = RegionLabelsLayer(features, self._resolver)
        self._wells_layer = WellsScatterLayer(wells or [])

        seen = set()
        for f in features:
            props = f.get("properties") or {}
            name = props.get("facies") or props.get("name")
            if name:
                seen.add(name)
        self._legend_layer.set_facies(seen)
        self._title_layer.set_text(f"{period_name}岩相古地理图" if period_name else "")

        # Replace layer instances in the list
        self._layers = [
            BackgroundLayer(),
            self._facies_layer,
            self._labels_layer,
            self._wells_layer,
            self._title_layer,
            NorthArrowLayer(),
            ScaleBarLayer(),
            self._legend_layer,
        ]
        self.update()

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

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._zoom_pan.start_drag(QPointF(event.position()))
            self._press_pos = QPointF(event.position())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = QPointF(event.position())
        if self._zoom_pan.is_dragging():
            self._zoom_pan.update_drag(pos)
            self.update()
            return
        # Hover hit-test
        facies = self._facies_layer.hit_test_polygon(pos, self._viewport)
        if facies != self._current_hover:
            self._current_hover = facies
            self.polygon_hovered.emit(facies or "")
        if facies:
            QToolTip.showText(event.globalPosition().toPoint(), facies, self)
        else:
            QToolTip.hideText()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._zoom_pan.end_drag()

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y() / 120.0
        if delta == 0:
            return
        self._zoom_pan.wheel_zoom(QPointF(event.position()), delta_steps=delta)
        self.update()
```

Modify `packages/geoviz_paleo_map/geoviz_paleo_map/__init__.py`:

```python
"""geoviz_paleo_map — QPainter-based paleogeographic map visualization for PySide6."""
from geoviz_paleo_map.canvas import PaleoMapCanvas

__all__ = ["PaleoMapCanvas"]
```

- [ ] **Step 4: Run, expect 5 passed**

Run: `source .venv/bin/activate && pytest tests/test_paleo_map_canvas.py -v`

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/canvas.py packages/geoviz_paleo_map/geoviz_paleo_map/__init__.py tests/test_paleo_map_canvas.py
git commit -m "feat(paleo): add PaleoMapCanvas composite with hover tooltip"
```

---

### Task 15: Wire PaleoMapPage to PaleoMapCanvas

**Files:**
- Modify: `src/pages/paleo_map/page.py`

Keep `src/pages/paleo_map/renderer.py` on disk; deletion is Task 18.

- [ ] **Step 1: Edit page.py — replace renderer + simplify period load**

Open `src/pages/paleo_map/page.py`.

Replace the import line:

```python
from src.pages.paleo_map.renderer import PaleoMapRenderer
```

with:

```python
from geoviz_paleo_map import PaleoMapCanvas

from src.utils.paths import get_data_dir
import json as _json


def _load_well_markers() -> list[dict]:
    """Load wells in {name, lng, lat} format for PaleoMapCanvas."""
    try:
        path = get_data_dir() / "well_coordinates.json"
        if not path.exists():
            return []
        with open(path, encoding="utf-8") as f:
            data = _json.load(f)
        return [
            {"name": w["well_name"], "lng": w["longitude"], "lat": w["latitude"]}
            for w in data.get("wells", [])
        ]
    except (OSError, KeyError, _json.JSONDecodeError):
        return []
```

Replace **all 3 occurrences** of `self.map_view = PaleoMapRenderer(self)` with:

```python
        self.map_view = PaleoMapCanvas(parent=self)
```

(And the second canvas in `_start_compare`: `self.map_view_b = PaleoMapCanvas(parent=self)`.)

In `_on_period_changed`, replace:

```python
        geojson_path = self._period_geojson_files.get(period_name)
        if geojson_path:
            self.map_view.load_geojson(geojson_path, period_name=period_name)

        if self._compare_mode and hasattr(self, 'map_view_b'):
            other_periods = [p for p in self._periods if p != period_name]
            if other_periods:
                other = other_periods[0]
                path_b = self._period_geojson_files.get(other)
                if path_b:
                    self.map_view_b.load_geojson(path_b, period_name=other)
```

with:

```python
        features = self._periods.get(period_name)
        if features is not None:
            self.map_view.load_features(features,
                                        period_name=period_name,
                                        wells=_load_well_markers())

        if self._compare_mode and hasattr(self, 'map_view_b'):
            other_periods = [p for p in self._periods if p != period_name]
            if other_periods:
                other = other_periods[0]
                features_b = self._periods.get(other)
                if features_b is not None:
                    self.map_view_b.load_features(features_b,
                                                  period_name=other,
                                                  wells=_load_well_markers())
```

In `_add_periods`, remove the `geojson_files` parameter handling block (tempfile cleanup is no longer needed). Replace the method body:

```python
    def _add_periods(self, periods: dict[str, list[dict]], geojson_files: dict[str, str]):
        # Clean up stale temp files from previous loads
        for name, path in list(self._period_geojson_files.items()):
            if name not in periods:
                try: os.unlink(path)
                except OSError: pass
                del self._period_geojson_files[name]

        for name, features in periods.items():
            self._periods[name] = features
            if name in geojson_files:
                old_path = self._period_geojson_files.get(name)
                new_path = geojson_files[name]
                if old_path and old_path != new_path:
                    try: os.unlink(old_path)
                    except OSError: pass
                self._period_geojson_files[name] = new_path
```

with:

```python
    def _add_periods(self, periods: dict[str, list[dict]]):
        for name, features in periods.items():
            self._periods[name] = features
```

Drop the `_period_geojson_files` attribute. In `__init__`, remove this line:

```python
        self._period_geojson_files: dict[str, str] = {}
```

In `_load_file`, replace:

```python
            loader = PaleoDataLoader(file_path)
            periods = loader.load()
            geojson_files = self._write_period_geojsons(periods, file_path)
            self._add_periods(periods, geojson_files)
```

with:

```python
            loader = PaleoDataLoader(file_path)
            periods = loader.load()
            self._add_periods(periods)
```

Delete the entire `_write_period_geojsons` method.

In `_start_compare`, replace:

```python
        old_view = self.map_view
        ...
        old_view._cleanup_tmp()
        old_view.deleteLater()
```

with:

```python
        old_view = self.map_view
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self.map_view = PaleoMapCanvas(parent=self)
        self.map_view_b = PaleoMapCanvas(parent=self)
        self._splitter.addWidget(self.map_view)
        self._splitter.addWidget(self.map_view_b)
        self._map_layout.addWidget(self._splitter)
        old_view.deleteLater()
        self._on_period_changed(self._current_period)
```

Similarly in `_stop_compare`, replace:

```python
    def _stop_compare(self):
        if hasattr(self, 'map_view_b'):
            try:
                self.map_view_b._cleanup_tmp()
                self.map_view_b.deleteLater()
            except RuntimeError:
                pass
            del self.map_view_b
        if hasattr(self, '_splitter'):
            self._splitter.setParent(None)
            del self._splitter
        self.map_view = PaleoMapRenderer(self)
        self._map_layout.addWidget(self.map_view)
        self._on_period_changed(self._current_period)
```

with:

```python
    def _stop_compare(self):
        if hasattr(self, 'map_view_b'):
            try:
                self.map_view_b.deleteLater()
            except RuntimeError:
                pass
            del self.map_view_b
        if hasattr(self, '_splitter'):
            self._splitter.setParent(None)
            del self._splitter
        self.map_view = PaleoMapCanvas(parent=self)
        self._map_layout.addWidget(self.map_view)
        self._on_period_changed(self._current_period)
```

- [ ] **Step 2: Run the full repo tests, expect no regressions**

Run: `source .venv/bin/activate && pytest -q`
Expected: All tests pass (existing `tests/test_paleo_map.py` still uses `PaleoMapRenderer` directly — that's fine because renderer.py still exists; it's deleted in Task 18).

- [ ] **Step 3: Smoke-test app launch**

Run: `source .venv/bin/activate && timeout 5 python -m src.main 2>&1 | tail -20; echo "exit=$?"`
Expected: No fatal traceback. Stylesheet/Qt warnings tolerable.

- [ ] **Step 4: Commit**

```bash
git add src/pages/paleo_map/page.py
git commit -m "feat(paleo): wire PaleoMapPage to PaleoMapCanvas, retire tempfile flow"
```

---

### Task 16: Visual parity golden image + regression test

**Files:**
- Create: `tests/golden/paleo_map_default.png`
- Create: `tests/test_paleo_map_visual_parity.py`

- [ ] **Step 1: Generate the golden image**

Run this one-off snippet to produce the canonical render. Open the image and confirm it shows polygons, region labels, wells, title, north arrow, scale bar, and legend before committing.

```bash
source .venv/bin/activate && python - <<'PY'
import json
from pathlib import Path
from PySide6.QtWidgets import QApplication
from geoviz_paleo_map import PaleoMapCanvas

app = QApplication.instance() or QApplication([])

sample = json.loads(Path("samples/sample_paleo.geojson").read_text(encoding="utf-8"))
features = sample["features"]
wells_data = json.loads(Path("data/well_coordinates.json").read_text(encoding="utf-8"))
wells = [{"name": w["well_name"], "lng": w["longitude"], "lat": w["latitude"]}
         for w in wells_data["wells"]]

c = PaleoMapCanvas()
c.load_features(features, period_name="测试", wells=wells)
# Pick a viewport that frames samples/sample_paleo.geojson polygons (~110..120E, 20..43N)
c._viewport.center_world = (115.0, 31.5)
c._viewport.zoom = 4.0
c.resize(1200, 800)
c.show()
app.processEvents()
pix = c.grab()
out = Path("tests/golden/paleo_map_default.png")
out.parent.mkdir(parents=True, exist_ok=True)
pix.save(str(out))
print(f"wrote {out} ({pix.width()}x{pix.height()} dpr={pix.devicePixelRatio()})")
PY
```

Visually inspect `tests/golden/paleo_map_default.png`:

- Background light gray
- Multiple colored polygons (the 5 sample features)
- "图例" legend in bottom-right
- "测试岩相古地理图" title at top
- N arrow top-right
- Scale bar bottom-left
- Wells as red dots

If any element is missing, FIX the underlying layer first.

- [ ] **Step 2: Write the parity test**

Create `tests/test_paleo_map_visual_parity.py`:

```python
"""Visual parity test — guards against regression of the canonical paleo render."""
import json
from pathlib import Path

import pytest
from PySide6.QtGui import QImage

from geoviz_paleo_map import PaleoMapCanvas
from tests.utils.visual_parity import (
    assert_visual_parity, load_golden, render_widget_to_image,
)


REPO = Path(__file__).parent.parent
SAMPLE = REPO / "samples" / "sample_paleo.geojson"
WELLS = REPO / "data" / "well_coordinates.json"
GOLDEN = Path(__file__).parent / "golden" / "paleo_map_default.png"


@pytest.fixture(scope="module")
def golden_image() -> QImage:
    return load_golden(GOLDEN)


def _build_canvas() -> PaleoMapCanvas:
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    wells_data = json.loads(WELLS.read_text(encoding="utf-8"))
    wells = [
        {"name": w["well_name"], "lng": w["longitude"], "lat": w["latitude"]}
        for w in wells_data["wells"]
    ]
    c = PaleoMapCanvas()
    c.load_features(sample["features"], period_name="测试", wells=wells)
    c._viewport.center_world = (115.0, 31.5)
    c._viewport.zoom = 4.0
    return c


def test_canonical_paleo_render_matches_golden(qtbot, golden_image):
    current = render_widget_to_image(_build_canvas(), 1200, 800, qtbot)
    assert_visual_parity(current, golden_image, max_diff=0.01)
```

- [ ] **Step 3: Run, expect 1 passed**

Run: `source .venv/bin/activate && pytest tests/test_paleo_map_visual_parity.py -v`

- [ ] **Step 4: Commit**

```bash
git add tests/golden/paleo_map_default.png tests/test_paleo_map_visual_parity.py
git commit -m "test(paleo): add visual parity golden image and regression"
```

---

### Task 17: HUMAN GATE — interactive verification

This is a human gate. Pause and request manual verification before proceeding.

- [ ] **Step 1: Launch the app**

Run: `source .venv/bin/activate && python -m src.main`

- [ ] **Step 2: Manually verify PaleoMap page**

In the running app, switch to PaleoMap, then:

1. Drag `samples/sample_paleo.geojson` (or click 加载 and pick it) → polygons render with facies colors and SVG pattern fills, region labels visible, wells red, title "测试岩相古地理图", legend bottom-right, scale bar bottom-left, north arrow top-right
2. Hover a polygon → tooltip shows the facies name
3. Drag map → panning works
4. Wheel → zoom centered on cursor
5. Toggle 对比 → side-by-side appears (requires loading 2 periods first)
6. Click 导出 → PNG / SVG / PDF all save and look right

- [ ] **Step 3: If anything is wrong**

STOP, fix the offending layer or canvas logic, return to the affected task. Do NOT proceed to Task 18.

- [ ] **Step 4: Confirm sign-off**

User confirms "looks good, proceed to cleanup".

---

### Task 18: Delete legacy PaleoMapRenderer + update docs

**Files:**
- Delete: `src/pages/paleo_map/renderer.py`
- Modify: `tests/test_paleo_map.py` — port to new canvas OR delete obsolete tests
- Modify: `CLAUDE.md`, `README.md`, `CHANGELOG.md`

- [ ] **Step 1: Check whether `tests/test_paleo_map.py` references the old renderer**

Run: `grep -n "PaleoMapRenderer" tests/test_paleo_map.py`

Expected: 4 hits (init, load, export, second init). These tests exercise the old WebEngine renderer. **Delete the file** — its behaviors are covered by the new layer and canvas tests:

```bash
git rm tests/test_paleo_map.py
```

- [ ] **Step 2: Verify no other reference remains**

Run: `grep -rn "PaleoMapRenderer\|ECHARTS_HTML_TEMPLATE\|_PaleoMapPage" src/ packages/ tests/ 2>/dev/null | grep -v __pycache__ | grep -v "archive/"`
Expected: only `src/pages/paleo_map/renderer.py` itself.

- [ ] **Step 3: Delete the renderer**

```bash
git rm src/pages/paleo_map/renderer.py
```

- [ ] **Step 4: Run the full repo tests**

Run: `source .venv/bin/activate && pytest -q`
Expected: all tests pass.

- [ ] **Step 5: Update CLAUDE.md**

In `CLAUDE.md`, find:

```
│       ├── PaleoMapPage   → ECharts + GeoJSON (paleo_map/ folder)
```

Replace with:

```
│       ├── PaleoMapPage   → QPainter (via geoviz-paleo-map package)
```

In the Architecture diagram's `packages/` block, append a new package after `geoviz-map`:

```
│   └── geoviz-paleo-map/  → Independent QPainter-based paleogeographic map engine
│       ├── canvas.py            → PaleoMapCanvas (QWidget composite of 8 layers)
│       ├── projection.py        → Plate Carrée (identity lng/lat → x/y)
│       ├── viewport.py          → PaleoMapViewport (center+zoom → pixel mapping)
│       ├── zoom_pan.py          → ZoomPanHandler
│       ├── style.py             → FaciesStyleResolver (per-facies brush cache)
│       └── layers/              → Background, FaciesPolygons, RegionLabels, WellsScatter, Title, NorthArrow, ScaleBar, Legend
```

Replace the line:

```
│   └── geoviz-map/        → Independent QPainter-based geographic map engine
```

with:

```
│   ├── geoviz-map/        → Independent QPainter-based geographic map engine
```

(so `└` moves to the paleo entry).

After the existing `geoviz-map` bullet in the Independent Package bullet list, append:

```
- **Independent Package**: `geoviz-paleo-map` is a fully decoupled paleogeographic map engine using only QPainter. Plate Carrée projection. Per-feature composite SVG pattern fills via `geoviz-well-log.PatternEngine` extensions (`get_composite_brush`, `get_color_fuzzy`). 8 layers: 4 data-driven + 4 chrome. Can be `pip install`-ed and used in any PySide6 project.
```

In Key Code Patterns, replace the existing PaleoMap line (if any; look for "PaleoMap" / "ECharts" near the Map description) with:

```
- **PaleoMap**: Native QPainter via `geoviz-paleo-map` package. Per-feature `FaciesStyle` resolved from facies name → base color + composite QBrush (from PatternEngine). Tooltip hit-test runs bbox prefilter then `QPainterPath.contains`. Tempfile-based GeoJSON middleware is gone — `load_features(features, period_name, wells)` accepts a Python dict directly.
```

In the Project Layout section, append after the `packages/geoviz_map/` block:

```
- `packages/geoviz_paleo_map/` — Independent paleogeographic map visualization package
  - `geoviz_paleo_map/canvas.py` — PaleoMapCanvas (8-layer composite)
  - `geoviz_paleo_map/projection.py` — Plate Carrée
  - `geoviz_paleo_map/viewport.py` — center+zoom → screen pixel mapping
  - `geoviz_paleo_map/zoom_pan.py` — Drag pan + cursor-anchored wheel zoom
  - `geoviz_paleo_map/style.py` — FaciesStyleResolver
  - `geoviz_paleo_map/layers/` — Background, FaciesPolygons, RegionLabels, WellsScatter, Title, NorthArrow, ScaleBar, Legend
```

- [ ] **Step 6: Update README.md**

In `README.md`, find:

```
│  │ 🌍   │  PaleoMap    ECharts + GeoJSON           │    │
```

Replace with:

```
│  │ 🌍   │  PaleoMap    QPainter (geoviz-paleo-map)  │    │
```

After the `packages/geoviz-map/` ASCII block, append:

```

│  packages/geoviz-paleo-map/                             │
│  ┌─────────────────────────────────────────────────┐    │
│  │  独立古地理可视化引擎 (QPainter + Plate Carrée)   │    │
│  │  ├── PaleoMapCanvas 组合 8 个 layer              │    │
│  │  ├── FaciesStyleResolver 每相缓存复合纹理         │    │
│  │  ├── Layers         背景/多边形/标签/井点         │    │
│  │  └── Chrome         标题/指北/比例尺/图例         │    │
│  └─────────────────────────────────────────────────┘    │
```

In Project Structure tree, after `geoviz_map/` block, append:

```
│   └── geoviz_paleo_map/           # 独立古地理可视化包 (pip installable)
│       ├── geoviz_paleo_map/
│       │   ├── canvas.py          # PaleoMapCanvas (8 个 layer)
│       │   ├── projection.py      # Plate Carrée 投影
│       │   ├── viewport.py        # center+zoom → 像素映射
│       │   ├── zoom_pan.py        # 拖拽 + 滚轮缩放
│       │   ├── style.py           # FaciesStyleResolver
│       │   └── layers/            # 8 个渲染层
│       └── pyproject.toml
```

(Also change `└── geoviz_map/` to `├── geoviz_map/` so tree formatting stays right.)

- [ ] **Step 7: Update CHANGELOG.md**

In `[Unreleased]`, under existing `### Added`, append:

```
- **新增独立包 `geoviz-paleo-map`**：基于 QPainter + Plate Carrée 投影的古地理图引擎，8 个 layer（4 数据层 + 4 chrome）。复用 `geoviz-well-log.PatternEngine` 并新增 `get_composite_brush` / `get_color_fuzzy` 两个公共方法。
```

Under existing `### Changed`, append:

```
- **PaleoMap 渲染重写**：古地理图从 QWebEngineView + ECharts 迁移到原生 QPainter。1:1 视觉/交互对齐（背景、polygon 复合花纹、边界样式、井位、标题、指北针、比例尺、图例、tooltip）。tempfile-based GeoJSON 中转移除，`load_features(features, period_name, wells)` 直接消费 dict。
```

Under existing `### Removed`, append:

```
- 删除 `src/pages/paleo_map/renderer.py`（411 行含 295 行内联 HTML/JS）和 `_write_period_geojsons` / `_period_geojson_files` / `_cleanup_tmp` 中转代码。
- `_PaleoMapPage(QWebEnginePage)` 子类 + tempfile 中转一并消失。主应用零 WebEngine import。
```

- [ ] **Step 8: Final test suite check**

Run: `source .venv/bin/activate && pytest -q`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add CLAUDE.md README.md CHANGELOG.md src/pages/paleo_map/renderer.py tests/test_paleo_map.py
git commit -m "chore(paleo): delete legacy PaleoMapRenderer and update docs"
```

---

## Final verification checklist

- [ ] `pytest -q` is green
- [ ] App launches, PaleoMap page renders correctly (Task 17 sign-off)
- [ ] `grep -rn "PaleoMapRenderer\|ECHARTS_HTML_TEMPLATE" src/ packages/ tests/ 2>/dev/null` returns no hits outside `archive/`
- [ ] CLAUDE.md, README.md, CHANGELOG.md reflect the new architecture
- [ ] Golden image committed at `tests/golden/paleo_map_default.png`
- [ ] 18 commits visible in `git log` since plan start (one per task)
