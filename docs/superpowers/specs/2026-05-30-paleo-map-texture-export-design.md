# Design Spec: PaleoMap Texture Rendering & Professional Figure Export

**Date:** 2026-05-30  
**Scope:** geoviz-paleo-map package + geoviz-well-log PatternEngine extension  
**Status:** Approved

---

## 1. Overview

Add sedimentary facies texture fill rendering (Q/HS 1011-2016 Appendix O) and professional figure export (true vector SVG + standardized publishing frame) to the PaleoMap package.

---

## 2. Pattern System: Facies Texture Rendering

### 2.1 Data Model

Extend `FaciesStyle` (in `style.py`) with an optional `pattern_id` field:

```python
@dataclass
class FaciesStyle:
    base_color: QColor
    pattern_id: str | None = None   # e.g. "fluvial_dots", "delta_waves"
    boundary_width: float = 1.0
```

`FaciesStyleResolver.resolve(facies_name: str) -> FaciesStyle` returns both color and pattern. The color-to-pattern mapping is derived from Q/HS 1011-2016 Appendix O (pages 226-229):

| Category | Facies Types | Pattern Style |
|----------|-------------|---------------|
| 陆相 (Continental) | 冲积扇, 河流, 湖泊, 沼泽, 沙漠 | Dots, wavy lines, horizontal stripes |
| 海陆过渡相 (Transitional) | 三角洲, 河口湾, 潟湖, 障壁岛 | Cross-hatch, brick, irregular dots |
| 海相 (Marine) | 滨岸, 浅海, 半深海, 深海 | Horizontal lines, fine dots, blank |
| 物源方向 (Provenance) | 单向, 双向, 多向 | Arrow indicators (handled as overlay, not fill) |

### 2.2 SVG Asset Organization

New directory structure under `geoviz_well_log/assets/patterns/`:

```
patterns/
  sandstone.svg       # existing 16 lithology patterns (unchanged)
  mudstone.svg
  ...
  facies/             # new — sedimentary facies patterns
    fluvial_dots.svg
    lake_waves.svg
    delta_brick.svg
    lagoon_cross.svg
    shore_horizontal.svg
    ... (16 total, matching Appendix O types)
```

Each SVG is a 32x32 tile with transparent background, using only `#000000` strokes/fills. The PatternEngine tints them via `QPainter` composition.

### 2.3 PatternEngine Extension

Add to `PatternEngine`:

```python
def get_facies_brush(self, pattern_id: str, base_color: QColor, alpha: float = 0.3) -> QBrush:
    """Return a composite brush: base_color fill + pattern overlay at alpha."""
    ...
```

Implementation reuses existing `get_composite_brush()` but looks up in `facies/` subdirectory. No breaking changes to existing lithology brush API.

### 2.4 FaciesPolygonsLayer Integration

In `facies_polygons.py`, change `paint()`:

```python
style = self.style_resolver.resolve(feature["facies"])
if style.pattern_id:
    brush = self.pattern_engine.get_facies_brush(style.pattern_id, style.base_color)
else:
    brush = QBrush(style.base_color)
painter.setBrush(brush)
painter.drawPath(path)
```

The `ScreenPathCache` and Quadtree culling logic remain unchanged.

### 2.5 Directional Patterns (物源方向)

Deferred to Phase 2. The 3 directional pattern types require per-feature rotation and are better implemented as a dedicated `ProvenanceOverlayLayer` that draws arrow symbols along polygon centroids.

---

## 3. Export System: True Vector + Professional Figure

### 3.1 True Vector SVG Export

New function in `save_export.py`:

```python
def export_vector_svg(canvas: PaleoMapCanvas, filepath: str, target_rect: QRectF):
    """Export map as true vector SVG using QSvgGenerator."""
```

**Implementation:**
1. Create `QSvgGenerator`, set `fileName`, `size`, `viewBox`
2. Create `QPainter(generator)`
3. Call `canvas.paintEvent(QPaintEvent(target_rect))` or directly invoke each layer's `paint()`
4. `painter.end()`

**Known Limitations:**
- Tiled QBrush patterns (from PatternEngine) render as embedded raster `<image>` fills inside `QSvgGenerator`. This is acceptable for facies fills; the base polygon paths are still vector.
- Gradients and some advanced QPainter effects may not translate.

### 3.2 Professional Figure Export

New module `export_professional.py`:

```python
def export_professional_figure(
    canvas: PaleoMapCanvas,
    filepath: str,
    format: Literal["svg", "pdf", "png"],
    *,
    title: str,
    page_size: Literal["A4", "A3", "A2"] = "A4",
    orientation: Literal["portrait", "landscape"] = "landscape",
    dpi: int = 300,
    color_mode: Literal["rgb", "cmyk"] = "rgb",
    include_scale_bar: bool = True,
    include_north_arrow: bool = True,
    include_legend: bool = True,
    include_grid_frame: bool = True,
) -> None:
```

**Standardized Frame Components:**

| Component | Position | Description |
|-----------|----------|-------------|
| Title Block | Top center | `title` text, font size 14pt bold |
| Map Area | Center | The rendered PaleoMapCanvas, clipped to page with margins |
| Scale Bar | Bottom left | Metric bar with km labels, auto-computed from zoom level |
| North Arrow | Top right | Standard arrow symbol, optional |
| Legend Panel | Right side or bottom | Color swatch + facies name list, auto-sized |
| Grid Frame | Around map area | Coordinate graticule with tick labels |

**Color Mode:**
- `rgb` (default): Direct QPainter output
- `cmyk`: Post-process via a small RGB→CMYK lookup table for the known facies palette. For SVG/PDF, embed an ICC profile; for PNG, convert via Pillow with `ImageCms`.

### 3.3 Integration with Canvas UI

Add toolbar buttons to `PaleoMapCanvas`:
- "Export SVG" → `export_vector_svg()`
- "Export Figure" → dialog with format/page/options → `export_professional_figure()`

The existing `export_png()` and `export_pdf()` remain as quick one-click actions.

---

## 4. Testing Strategy

| Test File | Coverage |
|-----------|----------|
| `tests/test_facies_patterns.py` | PatternEngine loads facies SVGs, composite brush returns valid QBrush, each pattern_id resolves |
| `tests/test_style_resolver.py` | FaciesStyleResolver returns correct pattern_id for known facies names |
| `tests/test_export_vector.py` | `export_vector_svg()` creates valid SVG file, contains `<path>` elements, no empty output |
| `tests/test_export_professional.py` | `export_professional_figure()` creates file, all frame components present (parsed via SVG DOM or PDF inspection) |

Target: 20+ new tests, all green.

---

## 5. File Changes

| File | Action |
|------|--------|
| `geoviz_paleo_map/style.py` | Add `pattern_id` to `FaciesStyle`; extend resolver mapping |
| `geoviz_paleo_map/layers/facies_polygons.py` | Use `pattern_id` brush when available |
| `geoviz_paleo_map/save_export.py` | Add `export_vector_svg()` |
| `geoviz_paleo_map/export_professional.py` | New — professional figure export |
| `geoviz_paleo_map/canvas.py` | Add toolbar buttons for new exports |
| `geoviz_well_log/renderer/pattern_engine.py` | Add `get_facies_brush()`; support facies/ subdir |
| `geoviz_well_log/assets/patterns/facies/*.svg` | New — 16 facies pattern SVG tiles |
| `tests/test_facies_patterns.py` | New |
| `tests/test_export_vector.py` | New |
| `tests/test_export_professional.py` | New |

---

## 6. Decisions

| Decision | Rationale |
|----------|-----------|
| Extend PatternEngine, not new engine | Existing composite brush + tile pipeline is correct abstraction; avoids duplication |
| SVG assets over procedural patterns | Spec patterns are static textures; SVG tiles are precise and maintainable |
| QSvgGenerator over manual DOM | Same `paint()` methods work; minimal code change; acceptable raster-pattern limitation |
| CMYK via lookup table, not full ICC | Palette is small (~38 facies colors); simple mapping avoids heavy dependency |
| Directional patterns deferred | Only 3 types; adds significant overlay complexity; not core to facies fill rendering |

---

## 7. Open Questions

None — design approved.
