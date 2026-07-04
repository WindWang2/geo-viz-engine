# Map Rendering Performance Optimization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate jank during pan/zoom for both map renderers by adding 3-layer caching (pixmap buffer, update batching, screen-space paths).

**Architecture:** Each layer renders to an oversized QPixmap (2x viewport) that gets blit-shifted on pan. A PaintScheduler debounces rapid `update()` calls to 60fps. ScreenPathCache pre-computes screen-space QPainterPaths per zoom level to skip per-frame transforms.

**Tech Stack:** PySide6 (QPainter, QPixmap, QTimer, QTransform), pytest, pytest-qt

---

## File Structure

| New File | Package | Purpose |
|----------|---------|---------|
| `packages/geoviz_paleo_map/geoviz_paleo_map/paint_scheduler.py` | geoviz_paleo_map | PaintScheduler + LayerPixmapCache |
| `packages/geoviz_paleo_map/geoviz_paleo_map/screen_path_cache.py` | geoviz_paleo_map | ScreenPathCache for screen-space QPainterPaths |
| `packages/geoviz_map/geoviz_map/paint_scheduler.py` | geoviz_map | PaintScheduler + LayerPixmapCache |
| `packages/geoviz_map/geoviz_map/screen_path_cache.py` | geoviz_map | ScreenPathCache for screen-space QPainterPaths |
| `tests/test_paint_scheduler.py` | — | Unit tests for PaintScheduler, LayerPixmapCache, ScreenPathCache |

| Modified File | Changes |
|---------------|---------|
| `packages/geoviz_paleo_map/geoviz_paleo_map/canvas.py` | Add PaintScheduler, wrap layers in LayerPixmapCache, replace `self.update()` |
| `packages/geoviz_paleo_map/geoviz_paleo_map/layers/facies_polygons.py` | Add ScreenPathCache, use screen-space paths in paint() |
| `packages/geoviz_map/geoviz_map/canvas.py` | Add PaintScheduler, wrap layers in LayerPixmapCache, replace `self.update()` |
| `packages/geoviz_map/geoviz_map/layers/geojson_polygon.py` | Add ScreenPathCache, use screen-space paths in paint() |
| `packages/geoviz_paleo_map/geoviz_paleo_map/__init__.py` | Export PaintScheduler, LayerPixmapCache, ScreenPathCache |
| `packages/geoviz_map/geoviz_map/__init__.py` | Export PaintScheduler, LayerPixmapCache, ScreenPathCache |

---

### Task 1: PaintScheduler

**Files:**
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/paint_scheduler.py`
- Create: `packages/geoviz_map/geoviz_map/paint_scheduler.py`
- Create: `tests/test_paint_scheduler.py`

- [ ] **Step 1: Write tests for PaintScheduler**

```python
# tests/test_paint_scheduler.py
"""Tests for PaintScheduler, LayerPixmapCache, and ScreenPathCache."""
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QWidget


class TestPaintScheduler:
    def test_coalesces_multiple_schedule_calls(self, qtbot):
        """Multiple schedule() calls before timer fires should produce one update."""
        from geoviz_paleo_map.paint_scheduler import PaintScheduler

        widget = QWidget()
        qtbot.addWidget(widget)
        widget.resize(100, 100)
        widget.show()

        update_count = 0
        original_update = widget.update

        def counting_update():
            nonlocal update_count
            update_count += 1
            original_update()

        widget.update = counting_update
        scheduler = PaintScheduler(widget)

        # Schedule 5 times rapidly
        for _ in range(5):
            scheduler.schedule()

        # Wait for timer to fire
        qtbot.wait(50)
        assert update_count == 1

    def test_schedule_after_fire_allows_new_update(self, qtbot):
        """After timer fires, a new schedule() should work."""
        from geoviz_paleo_map.paint_scheduler import PaintScheduler

        widget = QWidget()
        qtbot.addWidget(widget)
        widget.resize(100, 100)
        widget.show()

        update_count = 0
        original_update = widget.update

        def counting_update():
            nonlocal update_count
            update_count += 1
            original_update()

        widget.update = counting_update
        scheduler = PaintScheduler(widget)

        scheduler.schedule()
        qtbot.wait(50)
        assert update_count == 1

        scheduler.schedule()
        qtbot.wait(50)
        assert update_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_paint_scheduler.py::TestPaintScheduler -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'geoviz_paleo_map.paint_scheduler'"

- [ ] **Step 3: Implement PaintScheduler for geoviz_paleo_map**

```python
# packages/geoviz_paleo_map/geoviz_paleo_map/paint_scheduler.py
"""PaintScheduler — debounces rapid update() calls into 60fps repaints.
LayerPixmapCache — per-layer oversized QPixmap buffer for pan headroom."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPainter, QPixmap, QTransform

from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.viewport import PaleoMapViewport


class PaintScheduler:
    """Coalesce rapid update() calls into ~60fps repaints."""

    def __init__(self, widget):
        self._widget = widget
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(16)  # ~60fps
        self._timer.timeout.connect(self._do_update)
        self._pending = False

    def schedule(self) -> None:
        """Request a repaint. Multiple calls before timer fires = one repaint."""
        if not self._pending:
            self._pending = True
            self._timer.start()

    def _do_update(self) -> None:
        self._pending = False
        self._widget.update()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_paint_scheduler.py::TestPaintScheduler -v`
Expected: 2 passed

- [ ] **Step 5: Create the same file for geoviz_map**

```python
# packages/geoviz_map/geoviz_map/paint_scheduler.py
"""PaintScheduler — debounces rapid update() calls into 60fps repaints.
LayerPixmapCache — per-layer oversized QPixmap buffer for pan headroom."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPainter, QPixmap, QTransform

from geoviz_map.layers.base import MapLayer
from geoviz_map.viewport import MapViewport


class PaintScheduler:
    """Coalesce rapid update() calls into ~60fps repaints."""

    def __init__(self, widget):
        self._widget = widget
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._do_update)
        self._pending = False

    def schedule(self) -> None:
        if not self._pending:
            self._pending = True
            self._timer.start()

    def _do_update(self) -> None:
        self._pending = False
        self._widget.update()
```

- [ ] **Step 6: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/paint_scheduler.py packages/geoviz_map/geoviz_map/paint_scheduler.py tests/test_paint_scheduler.py
git commit -m "feat: add PaintScheduler for 60fps update debouncing"
```

---

### Task 2: LayerPixmapCache

**Files:**
- Modify: `packages/geoviz_paleo_map/geoviz_paleo_map/paint_scheduler.py`
- Modify: `packages/geoviz_map/geoviz_map/paint_scheduler.py`
- Modify: `tests/test_paint_scheduler.py`

- [ ] **Step 1: Write tests for LayerPixmapCache**

Append to `tests/test_paint_scheduler.py`:

```python
class TestLayerPixmapCache:
    def test_first_paint_renders_layer(self, qtbot):
        """First paint call should render the layer into a pixmap."""
        from geoviz_paleo_map.paint_scheduler import LayerPixmapCache

        class StubLayer:
            painted = False
            def paint(self, painter, viewport):
                self.painted = True

        layer = StubLayer()
        cache = LayerPixmapCache(layer)

        widget = QWidget()
        qtbot.addWidget(widget)
        painter = QPainter(widget)
        vp = PaleoMapViewport(center_lng=115.0, center_lat=30.0,
                              zoom=2.0, width=400, height=300)
        cache.paint(painter, vp)
        painter.end()

        assert layer.painted

    def test_second_paint_uses_cache(self, qtbot):
        """Second paint with same viewport should NOT re-render layer."""
        from geoviz_paleo_map.paint_scheduler import LayerPixmapCache

        render_count = 0

        class StubLayer:
            def paint(self, painter, viewport):
                nonlocal render_count
                render_count += 1

        layer = StubLayer()
        cache = LayerPixmapCache(layer)

        widget = QWidget()
        qtbot.addWidget(widget)
        vp = PaleoMapViewport(center_lng=115.0, center_lat=30.0,
                              zoom=2.0, width=400, height=300)

        painter = QPainter(widget)
        cache.paint(painter, vp)
        painter.end()
        assert render_count == 1

        painter = QPainter(widget)
        cache.paint(painter, vp)
        painter.end()
        assert render_count == 1  # cached, no re-render

    def test_zoom_change_triggers_rerender(self, qtbot):
        from geoviz_paleo_map.paint_scheduler import LayerPixmapCache

        render_count = 0

        class StubLayer:
            def paint(self, painter, viewport):
                nonlocal render_count
                render_count += 1

        layer = StubLayer()
        cache = LayerPixmapCache(layer)

        widget = QWidget()
        qtbot.addWidget(widget)
        vp1 = PaleoMapViewport(center_lng=115.0, center_lat=30.0,
                               zoom=2.0, width=400, height=300)
        vp2 = PaleoMapViewport(center_lng=115.0, center_lat=30.0,
                               zoom=3.0, width=400, height=300)

        painter = QPainter(widget)
        cache.paint(painter, vp1)
        painter.end()

        painter = QPainter(widget)
        cache.paint(painter, vp2)
        painter.end()
        assert render_count == 2

    def test_mark_dirty_triggers_rerender(self, qtbot):
        from geoviz_paleo_map.paint_scheduler import LayerPixmapCache

        render_count = 0

        class StubLayer:
            def paint(self, painter, viewport):
                nonlocal render_count
                render_count += 1

        layer = StubLayer()
        cache = LayerPixmapCache(layer)

        widget = QWidget()
        qtbot.addWidget(widget)
        vp = PaleoMapViewport(center_lng=115.0, center_lat=30.0,
                              zoom=2.0, width=400, height=300)

        painter = QPainter(widget)
        cache.paint(painter, vp)
        painter.end()
        assert render_count == 1

        cache.mark_dirty()
        painter = QPainter(widget)
        cache.paint(painter, vp)
        painter.end()
        assert render_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_paint_scheduler.py::TestLayerPixmapCache -v`
Expected: FAIL — `LayerPixmapCache` not importable

- [ ] **Step 3: Implement LayerPixmapCache for geoviz_paleo_map**

Append to `packages/geoviz_paleo_map/geoviz_paleo_map/paint_scheduler.py`:

```python
class LayerPixmapCache:
    """Per-layer pixmap cache with oversized buffer for pan headroom.

    Renders the layer into a 2x-viewport QPixmap. On pan, blit-shifts
    from the cached pixmap instead of re-rendering. Re-renders only on
    zoom change, data change (mark_dirty), or pan > 50% margin.
    """

    def __init__(self, layer):
        self._layer = layer
        self._pixmap: QPixmap | None = None
        self._vp_center: tuple[float, float] = (0.0, 0.0)
        self._vp_scale: float = 0.0
        self._dirty: bool = True

    def mark_dirty(self) -> None:
        self._dirty = True

    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        if self._needs_rerender(viewport):
            self._rerender(viewport)
        self._blit(painter, viewport)

    def _needs_rerender(self, vp: PaleoMapViewport) -> bool:
        if self._dirty:
            return True
        if abs(vp.scale - self._vp_scale) > 1e-6:
            return True
        dx = abs(vp.center_world[0] - self._vp_center[0]) * vp.scale
        dy = abs(vp.center_world[1] - self._vp_center[1]) * vp.scale
        return dx > vp.width * 0.5 or dy > vp.height * 0.5

    def _rerender(self, vp: PaleoMapViewport) -> None:
        buf_w = vp.width * 2
        buf_h = vp.height * 2
        self._pixmap = QPixmap(buf_w, buf_h)
        self._pixmap.fill(Qt.transparent)
        p = QPainter(self._pixmap)
        try:
            buf_vp = PaleoMapViewport(
                center_lng=vp.center_world[0],
                center_lat=vp.center_world[1],
                zoom=vp.zoom,
                width=buf_w,
                height=buf_h,
            )
            self._layer.paint(p, buf_vp)
        finally:
            p.end()
        self._vp_center = vp.center_world
        self._vp_scale = vp.scale
        self._dirty = False

    def _blit(self, painter: QPainter, vp: PaleoMapViewport) -> None:
        if self._pixmap is None:
            return
        # Center of buffer corresponds to cached center.
        # Current viewport center may have shifted — compute source offset.
        dx_px = (vp.center_world[0] - self._vp_center[0]) * vp.scale
        dy_px = (self._vp_center[1] - vp.center_world[1]) * vp.scale  # y flipped
        src_x = int(vp.width / 2 + dx_px)
        src_y = int(vp.height / 2 + dy_px)
        painter.drawPixmap(0, 0, self._pixmap, src_x, src_y, vp.width, vp.height)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_paint_scheduler.py::TestLayerPixmapCache -v`
Expected: 4 passed

- [ ] **Step 5: Implement LayerPixmapCache for geoviz_map**

Append to `packages/geoviz_map/geoviz_map/paint_scheduler.py`:

```python
class LayerPixmapCache:
    """Per-layer pixmap cache with oversized buffer for pan headroom."""

    def __init__(self, layer):
        self._layer = layer
        self._pixmap: QPixmap | None = None
        self._vp_center: tuple[float, float] = (0.0, 0.0)
        self._vp_scale: float = 0.0
        self._dirty: bool = True

    def mark_dirty(self) -> None:
        self._dirty = True

    def paint(self, painter: QPainter, viewport: MapViewport) -> None:
        if self._needs_rerender(viewport):
            self._rerender(viewport)
        self._blit(painter, viewport)

    def _needs_rerender(self, vp: MapViewport) -> bool:
        if self._dirty:
            return True
        if abs(vp.scale - self._vp_scale) > 1e-6:
            return True
        dx = abs(vp.center_world[0] - self._vp_center[0]) * vp.scale
        dy = abs(vp.center_world[1] - self._vp_center[1]) * vp.scale
        return dx > vp.width * 0.5 or dy > vp.height * 0.5

    def _rerender(self, vp: MapViewport) -> None:
        buf_w = vp.width * 2
        buf_h = vp.height * 2
        self._pixmap = QPixmap(buf_w, buf_h)
        self._pixmap.fill(Qt.transparent)
        p = QPainter(self._pixmap)
        try:
            from geoviz_map.projection import world_to_lnglat
            lng, lat = world_to_lnglat(*vp.center_world)
            buf_vp = MapViewport(
                center_lng=lng, center_lat=lat,
                zoom=vp.zoom, width=buf_w, height=buf_h,
            )
            self._layer.paint(p, buf_vp)
        finally:
            p.end()
        self._vp_center = vp.center_world
        self._vp_scale = vp.scale
        self._dirty = False

    def _blit(self, painter: QPainter, vp: MapViewport) -> None:
        if self._pixmap is None:
            return
        dx_px = (vp.center_world[0] - self._vp_center[0]) * vp.scale
        dy_px = (self._vp_center[1] - vp.center_world[1]) * vp.scale
        src_x = int(vp.width / 2 + dx_px)
        src_y = int(vp.height / 2 + dy_px)
        painter.drawPixmap(0, 0, self._pixmap, src_x, src_y, vp.width, vp.height)
```

- [ ] **Step 6: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/paint_scheduler.py packages/geoviz_map/geoviz_map/paint_scheduler.py tests/test_paint_scheduler.py
git commit -m "feat: add LayerPixmapCache for per-layer pixmap caching"
```

---

### Task 3: ScreenPathCache

**Files:**
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/screen_path_cache.py`
- Create: `packages/geoviz_map/geoviz_map/screen_path_cache.py`
- Modify: `tests/test_paint_scheduler.py`

- [ ] **Step 1: Write tests for ScreenPathCache**

Append to `tests/test_paint_scheduler.py`:

```python
class TestScreenPathCache:
    def test_returns_screen_space_path(self, qtbot):
        """Cached path should be in screen coordinates, not world."""
        from geoviz_paleo_map.screen_path_cache import ScreenPathCache

        cache = ScreenPathCache()
        # Simple world-space path: a square from (0,0) to (10,10)
        world_path = QPainterPath()
        world_path.moveTo(0, 0)
        world_path.lineTo(10, 0)
        world_path.lineTo(10, 10)
        world_path.lineTo(0, 10)
        world_path.closeSubpath()

        vp = PaleoMapViewport(center_lng=5.0, center_lat=5.0,
                              zoom=2.0, width=400, height=300)
        screen_path = cache.get_or_build("f1", world_path, vp)

        # Screen-space: center (5,5) maps to (200, 150)
        # At zoom=2, scale = 2^(2-1) = 2 px/deg
        # (0,0) → (200 - 5*2, 150 + 5*2) = (190, 160)... wait let me compute:
        # sx = (x - cx) * s + w/2 = (0-5)*2 + 200 = 190
        # sy = (cy - y) * s + h/2 = (5-0)*2 + 150 = 160
        bounds = screen_path.boundingRect()
        assert bounds.width() > 0
        assert bounds.height() > 0
        # The path should be roughly centered around (200, 150)
        assert 180 < bounds.center().x() < 220
        assert 140 < bounds.center().y() < 170

    def test_cache_hit_returns_same_object(self, qtbot):
        """Same zoom + feature_id should return cached path (same object)."""
        from geoviz_paleo_map.screen_path_cache import ScreenPathCache

        cache = ScreenPathCache()
        world_path = QPainterPath()
        world_path.moveTo(0, 0)
        world_path.lineTo(10, 0)
        world_path.lineTo(10, 10)
        world_path.closeSubpath()

        vp = PaleoMapViewport(center_lng=5.0, center_lat=5.0,
                              zoom=2.0, width=400, height=300)
        p1 = cache.get_or_build("f1", world_path, vp)
        p2 = cache.get_or_build("f1", world_path, vp)
        assert p1 is p2

    def test_dirty_feature_rebuilds_path(self, qtbot):
        from geoviz_paleo_map.screen_path_cache import ScreenPathCache

        cache = ScreenPathCache()
        world_path = QPainterPath()
        world_path.moveTo(0, 0)
        world_path.lineTo(10, 0)
        world_path.lineTo(10, 10)
        world_path.closeSubpath()

        vp = PaleoMapViewport(center_lng=5.0, center_lat=5.0,
                              zoom=2.0, width=400, height=300)
        p1 = cache.get_or_build("f1", world_path, vp)

        cache.mark_dirty("f1")
        p2 = cache.get_or_build("f1", world_path, vp)
        assert p1 is not p2

    def test_zoom_change_builds_new_path(self, qtbot):
        from geoviz_paleo_map.screen_path_cache import ScreenPathCache

        cache = ScreenPathCache()
        world_path = QPainterPath()
        world_path.moveTo(0, 0)
        world_path.lineTo(10, 0)
        world_path.lineTo(10, 10)
        world_path.closeSubpath()

        vp1 = PaleoMapViewport(center_lng=5.0, center_lat=5.0,
                               zoom=2.0, width=400, height=300)
        vp2 = PaleoMapViewport(center_lng=5.0, center_lat=5.0,
                               zoom=3.0, width=400, height=300)
        p1 = cache.get_or_build("f1", world_path, vp1)
        p2 = cache.get_or_build("f1", world_path, vp2)
        assert p1 is not p2

    def test_eviction_limits_zoom_levels(self, qtbot):
        from geoviz_paleo_map.screen_path_cache import ScreenPathCache

        cache = ScreenPathCache(max_levels=2)
        world_path = QPainterPath()
        world_path.moveTo(0, 0)
        world_path.lineTo(10, 0)
        world_path.lineTo(10, 10)
        world_path.closeSubpath()

        for zoom in [1.0, 1.5, 2.0, 2.5]:
            vp = PaleoMapViewport(center_lng=5.0, center_lat=5.0,
                                  zoom=zoom, width=400, height=300)
            cache.get_or_build("f1", world_path, vp)

        # Should only have 2 zoom levels worth of entries
        zooms = set(k[0] for k in cache._cache)
        assert len(zooms) <= 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_paint_scheduler.py::TestScreenPathCache -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'geoviz_paleo_map.screen_path_cache'`

- [ ] **Step 3: Implement ScreenPathCache for geoviz_paleo_map**

```python
# packages/geoviz_paleo_map/geoviz_paleo_map/screen_path_cache.py
"""ScreenPathCache — caches screen-space QPainterPaths per zoom level."""
from __future__ import annotations

from PySide6.QtGui import QPainterPath, QTransform

from geoviz_paleo_map.viewport import PaleoMapViewport


class ScreenPathCache:
    """Cache screen-space QPainterPaths per zoom level (rounded to 0.25)."""

    def __init__(self, max_levels: int = 4):
        self._cache: dict[tuple[float, str], QPainterPath] = {}
        self._dirty: set[str] = set()
        self._max_levels = max_levels

    def mark_dirty(self, feature_id: str) -> None:
        self._dirty.add(feature_id)

    def mark_all_dirty(self) -> None:
        for key in list(self._cache.keys()):
            self._dirty.add(key[1])

    def get_or_build(self, feature_id: str, world_path: QPainterPath,
                     viewport: PaleoMapViewport) -> QPainterPath:
        """Return screen-space path, building if needed."""
        zoom_key = round(viewport.zoom * 4) / 4
        cache_key = (zoom_key, feature_id)

        if cache_key in self._cache and feature_id not in self._dirty:
            return self._cache[cache_key]

        screen_path = self._transform_path(world_path, viewport)
        self._cache[cache_key] = screen_path
        self._dirty.discard(feature_id)
        self._evict(zoom_key)
        return screen_path

    def _transform_path(self, world_path: QPainterPath,
                        vp: PaleoMapViewport) -> QPainterPath:
        s = vp.scale
        cx, cy = vp.center_world
        ox = vp.width / 2
        oy = vp.height / 2
        t = QTransform()
        t.translate(ox, oy)
        t.scale(s, -s)
        t.translate(-cx, -cy)
        return world_path * t

    def _evict(self, current_zoom: float) -> None:
        zooms = sorted(set(k[0] for k in self._cache))
        if len(zooms) <= self._max_levels:
            return
        keep = set(zooms[-self._max_levels:])
        self._cache = {k: v for k, v in self._cache.items() if k[0] in keep}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_paint_scheduler.py::TestScreenPathCache -v`
Expected: 5 passed

- [ ] **Step 5: Implement ScreenPathCache for geoviz_map**

```python
# packages/geoviz_map/geoviz_map/screen_path_cache.py
"""ScreenPathCache — caches screen-space QPainterPaths per zoom level."""
from __future__ import annotations

from PySide6.QtGui import QPainterPath, QTransform

from geoviz_map.viewport import MapViewport


class ScreenPathCache:
    """Cache screen-space QPainterPaths per zoom level (rounded to 0.25)."""

    def __init__(self, max_levels: int = 4):
        self._cache: dict[tuple[float, str], QPainterPath] = {}
        self._dirty: set[str] = set()
        self._max_levels = max_levels

    def mark_dirty(self, feature_id: str) -> None:
        self._dirty.add(feature_id)

    def mark_all_dirty(self) -> None:
        for key in list(self._cache.keys()):
            self._dirty.add(key[1])

    def get_or_build(self, feature_id: str, world_path: QPainterPath,
                     viewport: MapViewport) -> QPainterPath:
        zoom_key = round(viewport.zoom * 4) / 4
        cache_key = (zoom_key, feature_id)
        if cache_key in self._cache and feature_id not in self._dirty:
            return self._cache[cache_key]
        screen_path = self._transform_path(world_path, viewport)
        self._cache[cache_key] = screen_path
        self._dirty.discard(feature_id)
        self._evict(zoom_key)
        return screen_path

    def _transform_path(self, world_path: QPainterPath,
                        vp: MapViewport) -> QPainterPath:
        s = vp.scale
        cx, cy = vp.center_world
        ox = vp.width / 2
        oy = vp.height / 2
        t = QTransform()
        t.translate(ox, oy)
        t.scale(s, -s)
        t.translate(-cx, -cy)
        return world_path * t

    def _evict(self, current_zoom: float) -> None:
        zooms = sorted(set(k[0] for k in self._cache))
        if len(zooms) <= self._max_levels:
            return
        keep = set(zooms[-self._max_levels:])
        self._cache = {k: v for k, v in self._cache.items() if k[0] in keep}
```

- [ ] **Step 6: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/screen_path_cache.py packages/geoviz_map/geoviz_map/screen_path_cache.py tests/test_paint_scheduler.py
git commit -m "feat: add ScreenPathCache for per-zoom QPainterPath caching"
```

---

### Task 4: Integrate PaintScheduler + LayerPixmapCache into PaleoMapCanvas

**Files:**
- Modify: `packages/geoviz_paleo_map/geoviz_paleo_map/canvas.py`

- [ ] **Step 1: Add imports and PaintScheduler to __init__**

In `packages/geoviz_paleo_map/geoviz_paleo_map/canvas.py`, add import at top:

```python
from geoviz_paleo_map.paint_scheduler import PaintScheduler, LayerPixmapCache
```

In `PaleoMapCanvas.__init__`, after `self._edit_engine = EditEngine(...)`, add:

```python
        self._scheduler = PaintScheduler(self)
        self._layer_caches: list[LayerPixmapCache] = []
```

- [ ] **Step 2: Build layer caches after layer list construction**

After `self._layers = [...]` in `__init__` (the initial layer list), add:

```python
        self._rebuild_layer_caches()
```

Add a helper method after `__init__`:

```python
    def _rebuild_layer_caches(self) -> None:
        """Rebuild LayerPixmapCache wrappers for current layer list."""
        self._layer_caches = [LayerPixmapCache(layer) for layer in self._layers]
```

- [ ] **Step 3: Update load_features to rebuild caches**

In `load_features`, replace the final `self.update()` with:

```python
        self._rebuild_layer_caches()
        self._scheduler.schedule()
```

- [ ] **Step 4: Update load_hierarchy to rebuild caches**

In `load_hierarchy`, replace `self.update()` at the end with:

```python
        self._rebuild_layer_caches()
        self._scheduler.schedule()
```

- [ ] **Step 5: Update _update_active_layers to rebuild caches**

At the end of `_update_active_layers()`, after `self._layers = [...]`, add:

```python
        self._rebuild_layer_caches()
```

- [ ] **Step 6: Update paintEvent to use caches**

Replace the `paintEvent` method body:

```python
    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            if self._hierarchy is not None:
                current_level = self._resolve_level_name()
                if current_level != self._current_active_level:
                    self._current_active_level = current_level
                    self._update_active_layers()

            for cache in self._layer_caches:
                cache.paint(painter, self._viewport)
        finally:
            painter.end()
```

- [ ] **Step 7: Replace all self.update() calls with self._scheduler.schedule()**

Replace these occurrences in `canvas.py`:
- `self.edit_mode = not self.edit_mode` → the `edit_mode.setter` calls `self.update()` — change to `self._scheduler.schedule()`
- `mousePressEvent` → `self.update()` → `self._scheduler.schedule()`
- `mouseMoveEvent` → `self.update()` → `self._scheduler.schedule()`
- `mouseReleaseEvent` → `self.update()` → `self._scheduler.schedule()`
- `mouseDoubleClickEvent` → `self.update()` → `self._scheduler.schedule()`
- `wheelEvent` → `self.update()` → `self._scheduler.schedule()`
- `keyPressEvent` → `self.update()` → `self._scheduler.schedule()`
- `set_zoom` → `self.update()` → `self._scheduler.schedule()`
- `toggle_lock` → `self.update()` → `self._scheduler.schedule()`
- `update_lock_level` → `self.update()` → `self._scheduler.schedule()`
- `_context_delete_vertex` → `self.update()` → `self._scheduler.schedule()`
- `_context_delete_polygon` → `self.update()` → `self._scheduler.schedule()`
- `_context_edit_attributes` → `self.update()` → `self._scheduler.schedule()`

Note: Keep `self.update()` in `edit_mode.setter` — it needs immediate repaint for toggle feedback. But change it to `self._scheduler.schedule()` as well for consistency (the scheduler fires in 16ms which is imperceptible).

- [ ] **Step 8: Mark caches dirty on topology edits**

In `_rebuild_topology_paths`, after rebuilding facies layer paths, mark the facies layer cache dirty:

```python
    def _rebuild_topology_paths(self) -> None:
        if self._topology_model is None:
            return
        dirty = self._topology_model.get_dirty_ids()
        if not dirty:
            return
        for layer in self._layers:
            if isinstance(layer, FaciesPolygonsLayer):
                layer.set_topology_model(self._topology_model)
                layer.rebuild_dirty_paths(dirty)
        self._topology_model.clear_dirty()
        # Mark affected layer caches dirty
        for i, layer in enumerate(self._layers):
            if isinstance(layer, FaciesPolygonsLayer) and i < len(self._layer_caches):
                self._layer_caches[i].mark_dirty()
```

- [ ] **Step 9: Run existing tests**

Run: `pytest tests/test_paleo_map_canvas.py -v`
Expected: All tests pass

- [ ] **Step 10: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/canvas.py
git commit -m "feat: integrate PaintScheduler + LayerPixmapCache into PaleoMapCanvas"
```

---

### Task 5: Integrate ScreenPathCache into FaciesPolygonsLayer

**Files:**
- Modify: `packages/geoviz_paleo_map/geoviz_paleo_map/layers/facies_polygons.py`

- [ ] **Step 1: Add import and ScreenPathCache to __init__**

At the top of `facies_polygons.py`, add:

```python
from geoviz_paleo_map.screen_path_cache import ScreenPathCache
```

In `FaciesPolygonsLayer.__init__`, after `self._topology_model = None`, add:

```python
        self._screen_cache = ScreenPathCache()
```

- [ ] **Step 2: Update paint() to use screen-space paths**

Replace the `paint()` method. The key change: remove the `painter.translate/scale` transform and use `ScreenPathCache.get_or_build()` for each item.

```python
    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        vp_bbox = viewport.world_bbox()

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.save()

        # 1. Spatial Index query for visible items
        visible_items: list[_Item] = []
        if self._quadtree_root is not None:
            self._quadtree_root.query(vp_bbox, visible_items)
        else:
            visible_items = [item for item in self._items if self._bbox_overlaps(vp_bbox, item.bbox)]

        # 2. Style Batching grouping
        groups: dict[tuple[str, str | None], list[_Item]] = {}
        for item in visible_items:
            key = (item.facies_name, item.boundary_kind)
            groups.setdefault(key, []).append(item)

        # 3. Draw visible polygons FILLS ONLY (screen-space paths)
        has_selection = self._selected_id is not None
        for (facies_name, boundary_kind), items in groups.items():
            style = self._resolver.resolve(facies_name)
            painter.setPen(QPen(Qt.PenStyle.NoPen))
            for item in items:
                screen_path = self._screen_cache.get_or_build(
                    item.feature_id, item.path, viewport)
                if has_selection and item.feature_id != self._selected_id:
                    painter.setOpacity(0.6)
                    painter.setBrush(style.brush)
                    painter.drawPath(screen_path)
                    painter.setOpacity(1.0)
                else:
                    painter.setBrush(style.brush)
                    painter.drawPath(screen_path)

        # 3b. Draw selection glow
        if has_selection:
            for item in visible_items:
                if item.feature_id == self._selected_id:
                    glow_pen = QPen(QColor("#3182ce"), 3.0)
                    glow_pen.setCosmetic(True)
                    painter.setPen(glow_pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    screen_path = self._screen_cache.get_or_build(
                        item.feature_id, item.path, viewport)
                    painter.drawPath(screen_path)
                    break

        # 4. Draw hierarchical borders
        if self._hierarchy is not None and self._active_level is not None:
            levels_order = ["facies", "sub_facies", "micro_facies"]
            max_depth = levels_order.index(self._active_level) if self._active_level in levels_order else 0

            for locked_lvl in self._locked_ids.values():
                if locked_lvl in levels_order:
                    depth = levels_order.index(locked_lvl)
                    if depth > max_depth:
                        max_depth = depth

            all_levels = levels_order[:max_depth + 1]
            draw_levels = [lvl for lvl in ["micro_facies", "sub_facies", "facies"] if lvl in all_levels]

            border_pens = {
                "facies": QPen(QColor("#1a202c"), 2.0),
                "sub_facies": QPen(QColor("#4a5568"), 1.5),
                "micro_facies": QPen(QColor("#a0aec0"), 1.0),
            }

            for lvl in draw_levels:
                pen = border_pens[lvl]
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)

                visible_borders = []
                root_node = self._level_quadtrees.get(lvl)
                if root_node is not None:
                    root_node.query(vp_bbox, visible_borders)
                else:
                    visible_borders = []

                for border_item in visible_borders:
                    active_lock = None
                    active_lock_depth = 0
                    if self._hierarchy is not None and self._locked_ids:
                        node = self._hierarchy.get_node(border_item.feature_id)
                        if node is not None:
                            ancestors = self._hierarchy.get_ancestors(border_item.feature_id)
                            chain = ancestors + [node.feature]
                            for f in chain:
                                if f.id in self._locked_ids:
                                    active_lock = self._locked_ids[f.id]
                                    break

                    levels = ["facies", "sub_facies", "micro_facies"]
                    active_depth = levels.index(self._active_level) if self._active_level in levels else 0
                    lvl_depth = levels.index(lvl) if lvl in levels else 0

                    if active_lock is not None:
                        active_lock_depth = levels.index(active_lock) if active_lock in levels else 0

                    if lvl_depth > active_depth:
                        if active_lock is None or lvl_depth > active_lock_depth:
                            continue

                    is_faded = False
                    if active_lock is not None and lvl_depth > active_lock_depth:
                        is_faded = True

                    screen_border = self._screen_cache.get_or_build(
                        border_item.feature_id, border_item.path, viewport)
                    if is_faded:
                        faded_pen = QPen(pen)
                        color = faded_pen.color()
                        color.setAlpha(45)
                        faded_pen.setColor(color)
                        faded_pen.setWidthF(0.7)
                        painter.setPen(faded_pen)
                        painter.drawPath(screen_border)
                        painter.setPen(pen)
                    else:
                        painter.drawPath(screen_border)
        else:
            # Simple fallback (non-hierarchical)
            for (facies_name, boundary_kind), items in groups.items():
                style = self._resolver.resolve(facies_name)
                if self._default_pen is not None:
                    pen = QPen(self._default_pen)
                else:
                    pen = boundary_pen(boundary_kind)
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.setBrush(style.brush)
                for item in items:
                    screen_path = self._screen_cache.get_or_build(
                        item.feature_id, item.path, viewport)
                    painter.drawPath(screen_path)

        painter.restore()
```

- [ ] **Step 3: Mark screen cache dirty on topology rebuild**

In `rebuild_dirty_paths`, after updating item paths, mark them dirty in the screen cache:

```python
    def rebuild_dirty_paths(self, feature_ids: set[str]) -> None:
        """Rebuild QPainterPaths for features whose topology has changed."""
        if self._topology_model is None:
            return
        for fid in feature_ids:
            new_path = self._topology_model.build_path(fid)
            if new_path is None:
                continue
            for item in self._items:
                if item.feature_id == fid:
                    item.path = new_path
                    br = new_path.boundingRect()
                    item.bbox = (br.left(), br.top(), br.right(), br.bottom())
            self._screen_cache.mark_dirty(fid)
        if feature_ids and self._items:
            min_x = min(item.bbox[0] for item in self._items)
            min_y = min(item.bbox[1] for item in self._items)
            max_x = max(item.bbox[2] for item in self._items)
            max_y = max(item.bbox[3] for item in self._items)
            self._quadtree_root = QuadtreeNode((min_x, min_y, max_x, max_y))
            for item in self._items:
                self._quadtree_root.insert(item)
```

- [ ] **Step 4: Run existing tests**

Run: `pytest tests/test_paleo_map_canvas.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/layers/facies_polygons.py
git commit -m "feat: integrate ScreenPathCache into FaciesPolygonsLayer"
```

---

### Task 6: Integrate PaintScheduler + LayerPixmapCache into MapCanvas

**Files:**
- Modify: `packages/geoviz_map/geoviz_map/canvas.py`

- [ ] **Step 1: Add imports and PaintScheduler to __init__**

Add import at top:

```python
from geoviz_map.paint_scheduler import PaintScheduler, LayerPixmapCache
```

In `MapCanvas.__init__`, after `self._layers = [...]`, add:

```python
        self._scheduler = PaintScheduler(self)
        self._layer_caches = [LayerPixmapCache(layer) for layer in self._layers]
```

- [ ] **Step 2: Update paintEvent to use caches**

Replace `paintEvent`:

```python
    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            for cache in self._layer_caches:
                cache.paint(painter, self._viewport)
        finally:
            painter.end()
```

- [ ] **Step 3: Replace self.update() calls**

In `mouseMoveEvent`:
- `self.update()` after drag → `self._scheduler.schedule()`
- `self.update()` after hover → `self._scheduler.schedule()`

In `wheelEvent`:
- `self.update()` → `self._scheduler.schedule()`

- [ ] **Step 4: Run existing tests**

Run: `pytest tests/test_map_canvas.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_map/geoviz_map/canvas.py
git commit -m "feat: integrate PaintScheduler + LayerPixmapCache into MapCanvas"
```

---

### Task 7: Integrate ScreenPathCache into GeoJsonPolygonLayer

**Files:**
- Modify: `packages/geoviz_map/geoviz_map/layers/geojson_polygon.py`

- [ ] **Step 1: Add import and ScreenPathCache to __init__**

Add import:

```python
from geoviz_map.screen_path_cache import ScreenPathCache
```

In `__init__`, after `self._features = []`, add:

```python
        self._screen_cache = ScreenPathCache()
```

Also assign feature IDs (the layer currently stores `(path, bbox)` tuples — add an ID):

Replace the feature storage pattern. Change `self._features` from `list[tuple[QPainterPath, tuple]]` to store an ID:

```python
        self._features: list[tuple[str, QPainterPath, tuple[float, float, float, float]]] = []
        for idx, feat in enumerate(geojson.get("features", [])):
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
                    self._features.append((f"geojson_{idx}", path, bbox))
```

- [ ] **Step 2: Update paint() to use screen-space paths**

Replace the `paint()` method:

```python
    def paint(self, painter: QPainter, viewport: MapViewport) -> None:
        vp_bbox = viewport.world_bbox()

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.save()

        pen = QPen(self.border_color, self.border_width)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(self.fill_color)

        for feat_id, path, bbox in self._features:
            if not self._bbox_overlaps(vp_bbox, bbox):
                continue
            screen_path = self._screen_cache.get_or_build(feat_id, path, viewport)
            painter.drawPath(screen_path)

        painter.restore()
```

- [ ] **Step 3: Run existing tests**

Run: `pytest tests/test_map_canvas.py -v`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add packages/geoviz_map/geoviz_map/layers/geojson_polygon.py
git commit -m "feat: integrate ScreenPathCache into GeoJsonPolygonLayer"
```

---

### Task 8: Update package exports

**Files:**
- Modify: `packages/geoviz_paleo_map/geoviz_paleo_map/__init__.py`
- Modify: `packages/geoviz_map/geoviz_map/__init__.py`

- [ ] **Step 1: Add exports to geoviz_paleo_map __init__**

```python
"""geoviz_paleo_map — QPainter-based paleogeographic map visualization for PySide6."""
from geoviz_paleo_map.canvas import PaleoMapCanvas
from geoviz_paleo_map.hierarchy import FaciesHierarchy
from geoviz_paleo_map.floating_slider import FloatingScaleSlider
from geoviz_paleo_map.locked_panel import LockedObjectsPanel
from geoviz_paleo_map.topology import TopologyModel, TopologyBuilder
from geoviz_paleo_map.edit_engine import EditEngine
from geoviz_paleo_map.edit_commands import UndoManager
from geoviz_paleo_map.paint_scheduler import PaintScheduler, LayerPixmapCache
from geoviz_paleo_map.screen_path_cache import ScreenPathCache

__all__ = [
    "PaleoMapCanvas", "FaciesHierarchy", "FloatingScaleSlider",
    "LockedObjectsPanel", "TopologyModel", "TopologyBuilder",
    "EditEngine", "UndoManager",
    "PaintScheduler", "LayerPixmapCache", "ScreenPathCache",
]
```

- [ ] **Step 2: Add exports to geoviz_map __init__**

```python
"""geoviz_map — QPainter-based geographic map visualization for PySide6."""
from geoviz_map.canvas import MapCanvas
from geoviz_map.models import ReferenceLabel, WellMarker
from geoviz_map.paint_scheduler import PaintScheduler, LayerPixmapCache
from geoviz_map.screen_path_cache import ScreenPathCache

__all__ = [
    "MapCanvas", "WellMarker", "ReferenceLabel",
    "PaintScheduler", "LayerPixmapCache", "ScreenPathCache",
]
```

- [ ] **Step 3: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/__init__.py packages/geoviz_map/geoviz_map/__init__.py
git commit -m "feat: export PaintScheduler, LayerPixmapCache, ScreenPathCache from packages"
```

---

### Task 9: Run full test suite and verify

**Files:** None (verification only)

- [ ] **Step 1: Run all tests**

```bash
pytest tests/ -v
```

Expected: All tests pass, including:
- `test_paint_scheduler.py` (PaintScheduler, LayerPixmapCache, ScreenPathCache)
- `test_paleo_map_canvas.py` (canvas integration)
- `test_map_canvas.py` (map canvas integration)
- All existing topology/edit tests

- [ ] **Step 2: Run paint performance test**

```bash
pytest tests/test_paleo_map_canvas.py::test_paint_performance -v
```

Expected: PASS with improved timing (should be faster than 50ms baseline)

- [ ] **Step 3: Verify no regressions in edit mode tests**

```bash
pytest tests/test_edit_commands.py tests/test_edit_engine.py tests/test_topology.py -v
```

Expected: All pass

- [ ] **Step 4: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: resolve test regressions from caching integration"
```
