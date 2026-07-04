# Map Rendering Performance Optimization Design

**Date:** 2026-05-29
**Scope:** `geoviz_map` and `geoviz_paleo_map` packages
**Goal:** Eliminate jank during pan/zoom and reduce initial render time for 200+ polygon maps

## Problem

Both map renderers (`MapCanvas` and `PaleoMapCanvas`) repaint every layer from scratch on every `update()` call. With 200+ polygons using pattern brush fills, this causes:

- Visible lag during pan/zoom (every mouse move triggers full repaint)
- Redundant work: 90% of the viewport hasn't changed between frames
- No coalescing: rapid mouse events spawn N `update()` calls for N mouse moves

Root cause: zero caching at every level — layer output, path transforms, and update scheduling.

## Solution: 3-Layer Cache Architecture

```
LayerPixmapCache (per layer)
  ↓ renders to
Oversized QPixmap buffer (2x viewport)
  ↓ blit-shifts on pan
Screen ← PaintScheduler (16ms debounce)
  ↓ triggers
ScreenPathCache (per zoom level, per feature)
  ↓ provides
Pre-computed screen-space QPainterPaths
```

## Layer 1: LayerPixmapCache

Each layer renders to its own oversized QPixmap instead of directly to the widget QPainter.

```python
class LayerPixmapCache:
    """Per-layer pixmap cache with oversized buffer for pan headroom."""

    def __init__(self, layer: PaleoLayer):
        self._layer = layer
        self._pixmap: QPixmap | None = None
        self._vp_center: tuple[float, float] = (0, 0)
        self._vp_scale: float = 0
        self._buffer_size: tuple[int, int] = (0, 0)
        self._dirty = True

    def mark_dirty(self) -> None:
        """Called when layer data changes."""
        self._dirty = True

    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        """Blit cached pixmap or re-render if needed."""
        needed = self._needs_rerender(viewport)
        if needed:
            self._rerender(viewport)
        # Blit from cached pixmap with offset
        self._blit(painter, viewport)

    def _needs_rerender(self, vp: PaleoMapViewport) -> bool:
        """True if cache is invalid (zoom change, data dirty, or pan > 50% margin)."""
        if self._dirty:
            return True
        if abs(vp.scale - self._vp_scale) > 1e-6:
            return True
        # Check if pan exceeded 50% of buffer margin
        dx = abs(vp.center_world[0] - self._vp_center[0]) * vp.scale
        dy = abs(vp.center_world[1] - self._vp_center[1]) * vp.scale
        margin_x = vp.width * 0.5  # 50% of viewport = 25% of buffer
        margin_y = vp.height * 0.5
        return dx > margin_x or dy > margin_y

    def _rerender(self, vp: PaleoMapViewport) -> None:
        """Render layer into oversized pixmap."""
        buf_w = vp.width * 2
        buf_h = vp.height * 2
        self._pixmap = QPixmap(buf_w, buf_h)
        self._pixmap.fill(Qt.transparent)
        p = QPainter(self._pixmap)
        # Create viewport for buffer (centered same, but 2x size)
        buf_vp = PaleoMapViewport(
            width=buf_w, height=buf_h,
            center_world=vp.center_world,
            scale=vp.scale,
        )
        self._layer.paint(p, buf_vp)
        p.end()
        self._vp_center = vp.center_world
        self._vp_scale = vp.scale
        self._buffer_size = (buf_w, buf_h)
        self._dirty = False

    def _blit(self, painter: QPainter, vp: PaleoMapViewport) -> None:
        """Copy the visible portion from buffer to screen."""
        if self._pixmap is None:
            return
        # Source rect: center of buffer maps to viewport center
        src_x = vp.width // 2
        src_y = vp.height // 2
        painter.drawPixmap(0, 0, self._pixmap, src_x, src_y, vp.width, vp.height)
```

**Key properties:**
- Buffer is 2x viewport in each direction (4x area). Pan within 50% margin = pure blit.
- Zoom change → full re-render (zoom affects path detail).
- Data change → `mark_dirty()` → re-render on next frame.
- Each layer has independent cache. Static layers (background, graticule) almost never re-render.

## Layer 2: Oversized Buffer Strategy

The 2x buffer means:
- 50% of buffer is off-screen in each direction
- Pan by less than 50% of viewport → shift blit source rect, no re-render
- Pan more than 50% → re-render (but this is rare during normal use)

Buffer math:
```
buffer_width  = viewport_width  * 2
buffer_height = viewport_height * 2
blit_source_x = viewport_width  / 2 + (center_world[0] - cached_center[0]) * scale
blit_source_y = viewport_height / 2 + (cached_center[1] - center_world[1]) * scale
```

## Layer 3: PaintScheduler

Replace scattered `self.update()` calls with a debounced scheduler.

```python
class PaintScheduler:
    """Coalesce rapid update() calls into 60fps repaints."""

    def __init__(self, widget: QWidget):
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

**Usage:** Replace all `self.update()` calls in canvas mouse/key handlers with `self._scheduler.schedule()`.

## Layer 4: ScreenPathCache

Pre-compute screen-space QPainterPaths per zoom level to eliminate per-frame coordinate transforms.

```python
class ScreenPathCache:
    """Cache screen-space QPainterPaths per zoom level."""

    def __init__(self, max_levels: int = 4):
        self._cache: dict[tuple[float, str], QPainterPath] = {}
        self._dirty: set[str] = set()
        self._max_levels = max_levels
        self._current_zoom: float | None = None

    def mark_dirty(self, feature_id: str) -> None:
        self._dirty.add(feature_id)

    def mark_all_dirty(self) -> None:
        self._dirty = set(self._cache.keys())

    def get_or_build(self, feature_id: str, world_path: QPainterPath,
                     viewport: PaleoMapViewport) -> QPainterPath:
        """Return screen-space path, building if needed."""
        zoom_key = round(viewport.zoom * 4) / 4  # round to 0.25
        cache_key = (zoom_key, feature_id)

        if cache_key in self._cache and feature_id not in self._dirty:
            return self._cache[cache_key]

        # Build screen-space path
        screen_path = self._transform_path(world_path, viewport)
        self._cache[cache_key] = screen_path
        self._dirty.discard(feature_id)

        # Evict if over limit
        self._evict(zoom_key)
        return screen_path

    def _transform_path(self, world_path: QPainterPath,
                        vp: PaleoMapViewport) -> QPainterPath:
        """Apply world_to_screen transform to all path elements."""
        s = vp.scale
        cx, cy = vp.center_world
        ox = vp.width / 2
        oy = vp.height / 2
        transform = QTransform()
        transform.translate(ox, oy)
        transform.scale(s, -s)
        transform.translate(-cx, -cy)
        return world_path * transform  # QPainterPath supports QTransform multiplication

    def _evict(self, current_zoom: float) -> None:
        """Remove cache entries for zoom levels far from current."""
        if len(set(k[0] for k in self._cache)) <= self._max_levels:
            return
        zooms = sorted(set(k[0] for k in self._cache))
        keep = set(zooms[-self._max_levels:])
        self._cache = {k: v for k, v in self._cache.items() if k[0] in keep}
```

**Memory:** 200 features × 4 zoom levels × ~2KB/path ≈ 1.6MB. Negligible.

**Integration with `FaciesPolygonsLayer.paint()`:**
```python
# Before (per frame):
painter.translate(ox, oy)
painter.scale(s, -s)
painter.translate(-cx, -cy)
for item in visible_items:
    painter.drawPath(item.path)  # world-space path, transformed by painter

# After (per frame):
for item in visible_items:
    screen_path = self._screen_cache.get_or_build(item.feature_id, item.path, viewport)
    painter.drawPath(screen_path)  # already screen-space, zero transforms
```

## Affected Files

| File | Changes |
|------|---------|
| `packages/geoviz_paleo_map/geoviz_paleo_map/canvas.py` | Add LayerPixmapCache per layer, PaintScheduler, replace `self.update()` calls |
| `packages/geoviz_paleo_map/geoviz_paleo_map/layers/facies_polygons.py` | Add ScreenPathCache, remove painter transform in paint(), use screen-space paths |
| `packages/geoviz_paleo_map/geoviz_paleo_map/layers/base.py` | Add `mark_dirty()` protocol to PaleoLayer |
| `packages/geoviz_map/geoviz_map/canvas.py` | Same LayerPixmapCache + PaintScheduler changes |
| `packages/geoviz_map/geoviz_map/layers/geojson_polygon.py` | Same ScreenPathCache integration |
| `packages/geoviz_paleo_map/geoviz_paleo_map/viewport.py` | Add `zoom` property (log2 of scale) for ScreenPathCache rounding |
| `packages/geoviz_map/geoviz_map/viewport.py` | Same `zoom` property |

## What This Does NOT Change

- Topology model, edit commands, undo/redo — no changes
- Quadtree spatial indexing — stays as-is, used inside layer paint()
- Projection math — stays as-is
- Layer z-ordering — stays as-is
- Edit overlay, context menu, save/export — no changes

## Verification

1. **Smoke test:** Launch app, load paleo map with 200+ polygons. Pan/zoom should be smooth (no visible lag).
2. **Memory:** Monitor RSS — pixmap buffers for 1920×1080 viewport = 4 layers × 3840×2160 × 4 bytes ≈ 265MB max. Acceptable.
3. **Cache invalidation:** Edit a polygon (move vertex) → layer re-renders, other layers stay cached.
4. **Zoom levels:** Zoom in/out — screen path cache builds at each 0.25 zoom step, evicts old levels.
5. **Regression:** All existing tests pass. Edit mode still works (undo/redo, context menu, save/export).
