# PaleoMap Texture Rendering & Professional Figure Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add sedimentary facies texture fills (Q/HS 1011-2016 Appendix O) and professional figure export (true vector SVG + standardized publishing frame) to geoviz-paleo-map.

**Architecture:** Extend PatternEngine with a `facies/` subdirectory and `get_facies_brush()` method. Add `pattern_id` to `FaciesStyle`. Use `QSvgGenerator` for true vector export. Build a professional figure wrapper that composites the map with a standardized frame (title, scale bar, north arrow, legend, grid).

**Tech Stack:** PySide6, QPainter, QSvgGenerator, QPrinter, pytest-qt

---

## File Structure

| File | Responsibility |
|------|---------------|
| `geoviz_well_log/assets/patterns/facies/*.svg` | 13 sedimentary facies pattern tiles |
| `geoviz_well_log/renderer/pattern_engine.py` | Add `get_facies_brush()`; load from `facies/` subdir |
| `geoviz_paleo_map/models.py` | Add `pattern_id` to `FaciesStyle` |
| `geoviz_paleo_map/style.py` | Add `FACIES_PATTERNS` mapping; update resolver |
| `geoviz_paleo_map/layers/facies_polygons.py` | Use facies brush when `pattern_id` is set |
| `geoviz_paleo_map/save_export.py` | Add `export_vector_svg()` |
| `geoviz_paleo_map/export_professional.py` | New — professional figure export with frame |
| `tests/test_facies_patterns.py` | Pattern loading, brush creation, integration |
| `tests/test_export_vector.py` | Vector SVG export |
| `tests/test_export_professional.py` | Professional figure export |

---

## Subsystem A: Facies Pattern Rendering

### Task 1: Extend FaciesStyle dataclass with pattern_id

**Files:**
- Modify: `packages/geoviz_paleo_map/geoviz_paleo_map/models.py`
- Test: `tests/test_facies_patterns.py`

- [ ] **Step 1: Write the failing test**

```python
from PySide6.QtGui import QBrush, QColor
from geoviz_paleo_map.models import FaciesStyle


def test_facies_style_has_pattern_id():
    brush = QBrush(QColor("#ff0000"))
    style = FaciesStyle(base_color=QColor("#ff0000"), brush=brush, pattern_id="delta")
    assert style.pattern_id == "delta"


def test_facies_style_pattern_id_defaults_to_none():
    brush = QBrush(QColor("#ff0000"))
    style = FaciesStyle(base_color=QColor("#ff0000"), brush=brush)
    assert style.pattern_id is None
```

Run: `pytest tests/test_facies_patterns.py -v`
Expected: FAIL with `TypeError: FaciesStyle.__init__() got an unexpected keyword argument 'pattern_id'`

- [ ] **Step 2: Add pattern_id to FaciesStyle**

In `packages/geoviz_paleo_map/geoviz_paleo_map/models.py`, change:

```python
@dataclass(frozen=True)
class FaciesStyle:
    """Resolved styling for one facies value: base color + optional composite brush."""

    base_color: QColor
    brush: QBrush
    pattern_id: str | None = None
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `pytest tests/test_facies_patterns.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_facies_patterns.py packages/geoviz_paleo_map/geoviz_paleo_map/models.py
git commit -m "feat: add pattern_id to FaciesStyle dataclass"
```

---

### Task 2: Create facies pattern SVGs — Continental facies (5 files)

**Files:**
- Create: `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/alluvial_fan.svg`
- Create: `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/fluvial.svg`
- Create: `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/lacustrine.svg`
- Create: `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/swamp.svg`
- Create: `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/desert.svg`

- [ ] **Step 1: Create the facies directory and all 5 SVG files**

```bash
mkdir -p packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies
```

Write `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/alluvial_fan.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
  <!-- 冲积扇: 散落的粗点，扇形分布 -->
  <circle cx="4" cy="5" r="1.5" fill="#000000"/>
  <circle cx="14" cy="3" r="1.2" fill="#000000"/>
  <circle cx="24" cy="6" r="1.0" fill="#000000"/>
  <circle cx="8" cy="12" r="1.3" fill="#000000"/>
  <circle cx="20" cy="10" r="1.5" fill="#000000"/>
  <circle cx="28" cy="14" r="1.1" fill="#000000"/>
  <circle cx="6" cy="20" r="1.4" fill="#000000"/>
  <circle cx="16" cy="18" r="1.0" fill="#000000"/>
  <circle cx="26" cy="22" r="1.3" fill="#000000"/>
  <circle cx="12" cy="26" r="1.2" fill="#000000"/>
  <circle cx="22" cy="28" r="1.1" fill="#000000"/>
  <circle cx="30" cy="26" r="1.0" fill="#000000"/>
</svg>
```

Write `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/fluvial.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
  <!-- 河流: 蜿蜒曲线 -->
  <path d="M0,8 Q8,2 16,8 T32,8" fill="none" stroke="#000000" stroke-width="1.2"/>
  <path d="M0,20 Q8,14 16,20 T32,20" fill="none" stroke="#000000" stroke-width="1.2"/>
  <path d="M0,30 Q8,24 16,30 T32,30" fill="none" stroke="#000000" stroke-width="1.2"/>
</svg>
```

Write `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/lacustrine.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
  <!-- 湖泊: 水平波浪线 -->
  <path d="M0,6 Q4,3 8,6 T16,6 T24,6 T32,6" fill="none" stroke="#000000" stroke-width="0.9"/>
  <path d="M0,14 Q4,11 8,14 T16,14 T24,14 T32,14" fill="none" stroke="#000000" stroke-width="0.9"/>
  <path d="M0,22 Q4,19 8,22 T16,22 T24,22 T32,22" fill="none" stroke="#000000" stroke-width="0.9"/>
  <path d="M0,30 Q4,27 8,30 T16,30 T24,30 T32,30" fill="none" stroke="#000000" stroke-width="0.9"/>
</svg>
```

Write `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/swamp.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
  <!-- 沼泽: 小植物状符号 + 散点 -->
  <circle cx="6" cy="6" r="0.8" fill="#000000"/>
  <circle cx="14" cy="4" r="0.7" fill="#000000"/>
  <circle cx="22" cy="7" r="0.9" fill="#000000"/>
  <circle cx="28" cy="5" r="0.8" fill="#000000"/>
  <circle cx="4" cy="14" r="0.7" fill="#000000"/>
  <circle cx="12" cy="12" r="0.8" fill="#000000"/>
  <circle cx="20" cy="15" r="0.7" fill="#000000"/>
  <circle cx="26" cy="13" r="0.9" fill="#000000"/>
  <circle cx="8" cy="22" r="0.8" fill="#000000"/>
  <circle cx="16" cy="20" r="0.7" fill="#000000"/>
  <circle cx="24" cy="23" r="0.8" fill="#000000"/>
  <circle cx="30" cy="21" r="0.7" fill="#000000"/>
  <circle cx="6" cy="30" r="0.9" fill="#000000"/>
  <circle cx="14" cy="28" r="0.8" fill="#000000"/>
  <circle cx="22" cy="29" r="0.7" fill="#000000"/>
  <circle cx="28" cy="31" r="0.8" fill="#000000"/>
</svg>
```

Write `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/desert.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
  <!-- 沙漠: 新月形沙丘 -->
  <path d="M2,8 Q8,2 14,8" fill="none" stroke="#000000" stroke-width="1.0"/>
  <path d="M18,6 Q24,0 30,6" fill="none" stroke="#000000" stroke-width="1.0"/>
  <path d="M6,18 Q12,12 18,18" fill="none" stroke="#000000" stroke-width="1.0"/>
  <path d="M22,16 Q28,10 30,16" fill="none" stroke="#000000" stroke-width="1.0"/>
  <path d="M4,28 Q10,22 16,28" fill="none" stroke="#000000" stroke-width="1.0"/>
  <path d="M20,26 Q26,20 30,26" fill="none" stroke="#000000" stroke-width="1.0"/>
</svg>
```

- [ ] **Step 2: Verify SVG files are valid XML**

Run: `python -c "import xml.etree.ElementTree as ET; [ET.parse(p) for p in __import__('glob').glob('packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/*.svg')]"`
Expected: No output (success)

- [ ] **Step 3: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/
git commit -m "feat: add continental facies pattern SVGs (alluvial, fluvial, lacustrine, swamp, desert)"
```

---

### Task 3: Create facies pattern SVGs — Transitional + Marine facies (8 files)

**Files:**
- Create: `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/delta.svg`
- Create: `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/estuary.svg`
- Create: `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/lagoon.svg`
- Create: `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/barrier_island.svg`
- Create: `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/shoreface.svg`
- Create: `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/shallow_marine.svg`
- Create: `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/deep_marine.svg`
- Create: `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/abyssal.svg`

- [ ] **Step 1: Create all 8 SVG files**

Write `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/delta.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
  <!-- 三角洲: 树枝状分叉线 -->
  <path d="M16,0 L16,12" fill="none" stroke="#000000" stroke-width="1.0"/>
  <path d="M16,12 L8,20" fill="none" stroke="#000000" stroke-width="1.0"/>
  <path d="M16,12 L24,20" fill="none" stroke="#000000" stroke-width="1.0"/>
  <path d="M16,12 L16,28" fill="none" stroke="#000000" stroke-width="1.0"/>
  <path d="M8,20 L4,28" fill="none" stroke="#000000" stroke-width="1.0"/>
  <path d="M8,20 L12,28" fill="none" stroke="#000000" stroke-width="1.0"/>
  <path d="M24,20 L20,28" fill="none" stroke="#000000" stroke-width="1.0"/>
  <path d="M24,20 L28,28" fill="none" stroke="#000000" stroke-width="1.0"/>
</svg>
```

Write `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/estuary.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
  <!-- 河口湾: 混合水平+波浪 -->
  <line x1="0" y1="6" x2="32" y2="6" stroke="#000000" stroke-width="0.8"/>
  <path d="M0,14 Q4,11 8,14 T16,14 T24,14 T32,14" fill="none" stroke="#000000" stroke-width="0.8"/>
  <line x1="0" y1="22" x2="32" y2="22" stroke="#000000" stroke-width="0.8"/>
  <path d="M0,30 Q4,27 8,30 T16,30 T24,30 T32,30" fill="none" stroke="#000000" stroke-width="0.8"/>
</svg>
```

Write `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/lagoon.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
  <!-- 潟湖: 同心弧线 -->
  <path d="M8,32 A8,8 0 0,1 24,32" fill="none" stroke="#000000" stroke-width="0.9"/>
  <path d="M4,32 A12,12 0 0,1 28,32" fill="none" stroke="#000000" stroke-width="0.9"/>
  <path d="M0,32 A16,16 0 0,1 32,32" fill="none" stroke="#000000" stroke-width="0.9"/>
</svg>
```

Write `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/barrier_island.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
  <!-- 障壁岛: 平行虚线 -->
  <line x1="0" y1="4" x2="12" y2="4" stroke="#000000" stroke-width="1.0"/>
  <line x1="20" y1="4" x2="32" y2="4" stroke="#000000" stroke-width="1.0"/>
  <line x1="0" y1="12" x2="10" y2="12" stroke="#000000" stroke-width="1.0"/>
  <line x1="18" y1="12" x2="32" y2="12" stroke="#000000" stroke-width="1.0"/>
  <line x1="0" y1="20" x2="14" y2="20" stroke="#000000" stroke-width="1.0"/>
  <line x1="22" y1="20" x2="32" y2="20" stroke="#000000" stroke-width="1.0"/>
  <line x1="0" y1="28" x2="11" y2="28" stroke="#000000" stroke-width="1.0"/>
  <line x1="19" y1="28" x2="32" y2="28" stroke="#000000" stroke-width="1.0"/>
</svg>
```

Write `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/shoreface.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
  <!-- 滨岸: 平行水平线 -->
  <line x1="0" y1="5" x2="32" y2="5" stroke="#000000" stroke-width="1.0"/>
  <line x1="0" y1="13" x2="32" y2="13" stroke="#000000" stroke-width="1.0"/>
  <line x1="0" y1="21" x2="32" y2="21" stroke="#000000" stroke-width="1.0"/>
  <line x1="0" y1="29" x2="32" y2="29" stroke="#000000" stroke-width="1.0"/>
</svg>
```

Write `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/shallow_marine.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
  <!-- 浅海: 细平行水平线 -->
  <line x1="0" y1="4" x2="32" y2="4" stroke="#000000" stroke-width="0.6"/>
  <line x1="0" y1="10" x2="32" y2="10" stroke="#000000" stroke-width="0.6"/>
  <line x1="0" y1="16" x2="32" y2="16" stroke="#000000" stroke-width="0.6"/>
  <line x1="0" y1="22" x2="32" y2="22" stroke="#000000" stroke-width="0.6"/>
  <line x1="0" y1="28" x2="32" y2="28" stroke="#000000" stroke-width="0.6"/>
</svg>
```

Write `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/deep_marine.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
  <!-- 半深海: 细密散点 -->
  <circle cx="4" cy="4" r="0.6" fill="#000000"/>
  <circle cx="12" cy="3" r="0.5" fill="#000000"/>
  <circle cx="20" cy="5" r="0.6" fill="#000000"/>
  <circle cx="28" cy="4" r="0.5" fill="#000000"/>
  <circle cx="8" cy="10" r="0.5" fill="#000000"/>
  <circle cx="16" cy="9" r="0.6" fill="#000000"/>
  <circle cx="24" cy="11" r="0.5" fill="#000000"/>
  <circle cx="4" cy="16" r="0.6" fill="#000000"/>
  <circle cx="12" cy="15" r="0.5" fill="#000000"/>
  <circle cx="20" cy="17" r="0.6" fill="#000000"/>
  <circle cx="28" cy="16" r="0.5" fill="#000000"/>
  <circle cx="8" cy="22" r="0.6" fill="#000000"/>
  <circle cx="16" cy="21" r="0.5" fill="#000000"/>
  <circle cx="24" cy="23" r="0.6" fill="#000000"/>
  <circle cx="4" cy="28" r="0.5" fill="#000000"/>
  <circle cx="12" cy="27" r="0.6" fill="#000000"/>
  <circle cx="20" cy="29" r="0.5" fill="#000000"/>
  <circle cx="28" cy="28" r="0.6" fill="#000000"/>
</svg>
```

Write `packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/abyssal.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
  <!-- 深海: 极稀疏细点 -->
  <circle cx="8" cy="8" r="0.5" fill="#000000"/>
  <circle cx="24" cy="6" r="0.5" fill="#000000"/>
  <circle cx="4" cy="20" r="0.5" fill="#000000"/>
  <circle cx="20" cy="18" r="0.5" fill="#000000"/>
  <circle cx="12" cy="28" r="0.5" fill="#000000"/>
  <circle cx="28" cy="26" r="0.5" fill="#000000"/>
</svg>
```

- [ ] **Step 2: Verify all SVG files are valid XML**

Run: `python -c "import xml.etree.ElementTree as ET; [ET.parse(p) for p in __import__('glob').glob('packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/*.svg')]"`
Expected: No output (success)

- [ ] **Step 3: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/assets/patterns/facies/
git commit -m "feat: add transitional and marine facies pattern SVGs (delta, estuary, lagoon, barrier, shoreface, shallow, deep, abyssal)"
```

---

### Task 4: Extend PatternEngine with get_facies_brush()

**Files:**
- Modify: `packages/geoviz_well_log/geoviz_well_log/renderer/pattern_engine.py`
- Test: `tests/test_facies_patterns.py`

- [ ] **Step 1: Write the failing test**

```python
from PySide6.QtGui import QColor
from geoviz_well_log.renderer.pattern_engine import PatternEngine


def test_get_facies_brush_returns_brush_for_known_pattern(qtbot):
    engine = PatternEngine()
    brush = engine.get_facies_brush("shoreface", QColor("#b5d4c1"))
    assert brush is not None


def test_get_facies_brush_returns_none_for_unknown_pattern():
    engine = PatternEngine()
    brush = engine.get_facies_brush("nonexistent_pattern", QColor("#ffffff"))
    assert brush is None


def test_get_facies_brush_caches_by_pattern_and_color():
    engine = PatternEngine()
    color = QColor("#b5d4c1")
    a = engine.get_facies_brush("shoreface", color)
    b = engine.get_facies_brush("shoreface", color)
    assert a is b
```

Run: `pytest tests/test_facies_patterns.py::test_get_facies_brush_returns_brush_for_known_pattern -v`
Expected: FAIL with `AttributeError: 'PatternEngine' object has no attribute 'get_facies_brush'`

- [ ] **Step 2: Add get_facies_brush() to PatternEngine**

In `packages/geoviz_well_log/geoviz_well_log/renderer/pattern_engine.py`, add after `get_composite_brush()`:

```python
    def get_facies_brush(self, pattern_id: str, base_color: QColor,
                         alpha: float = 0.3) -> QBrush | None:
        """Return a composite brush for a facies pattern tile.

        Looks up SVG files in the `facies/` subdirectory under assets/patterns.
        Renders base_color background with the black SVG pattern overlaid at alpha.
        Cached per (pattern_id, color hex, alpha).
        """
        cache_key = f"facies::{pattern_id}::{base_color.name()}::{alpha:.2f}"
        if not hasattr(self, "_facies_cache"):
            self._facies_cache: dict[str, QBrush] = {}
        if cache_key in self._facies_cache:
            return self._facies_cache[cache_key]

        filename = pattern_id.replace("-", "_")
        svg_path = self._ASSETS_DIR / "facies" / f"{filename}.svg"
        if not svg_path.exists():
            return None

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
        self._facies_cache[cache_key] = brush
        return brush
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `pytest tests/test_facies_patterns.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/pattern_engine.py tests/test_facies_patterns.py
git commit -m "feat: add PatternEngine.get_facies_brush() for facies/ subdir patterns"
```

---

### Task 5: Add FACIES_PATTERNS mapping and update FaciesStyleResolver

**Files:**
- Modify: `packages/geoviz_paleo_map/geoviz_paleo_map/style.py`
- Test: `tests/test_facies_patterns.py`

- [ ] **Step 1: Write the failing test**

```python
from PySide6.QtGui import QBrush, QColor
from geoviz_well_log.renderer.pattern_engine import PatternEngine
from geoviz_paleo_map.style import FaciesStyleResolver


def test_resolver_returns_pattern_id_for_known_facies(qtbot):
    engine = PatternEngine()
    resolver = FaciesStyleResolver(engine)
    style = resolver.resolve("滨岸")
    assert style.pattern_id == "shoreface"


def test_resolver_returns_none_pattern_id_for_unknown_facies(qtbot):
    engine = PatternEngine()
    resolver = FaciesStyleResolver(engine)
    style = resolver.resolve("无此相")
    assert style.pattern_id is None


def test_resolver_facies_brush_is_composite(qtbot):
    """Facies with pattern should return a composite brush (not solid color)."""
    engine = PatternEngine()
    resolver = FaciesStyleResolver(engine)
    style = resolver.resolve("三角洲")
    assert style.pattern_id == "delta"
    assert isinstance(style.brush, QBrush)
```

Run: `pytest tests/test_facies_patterns.py -v`
Expected: FAIL — `pattern_id` not set by resolver

- [ ] **Step 2: Add FACIES_PATTERNS and update resolver**

In `packages/geoviz_paleo_map/geoviz_paleo_map/style.py`, add before `class FaciesStyleResolver`:

```python
# Facies name → pattern_id mapping (Q/HS 1011-2016 Appendix O)
# Continental
FACIES_PATTERNS = {
    "冲积扇": "alluvial_fan",
    "洪积扇": "alluvial_fan",
    "河流": "fluvial",
    "湖泊": "lacustrine",
    "沼泽": "swamp",
    "沙漠": "desert",
    # Transitional
    "三角洲": "delta",
    "河口湾": "estuary",
    "潟湖": "lagoon",
    "局限台地": "lagoon",
    "障壁岛": "barrier_island",
    # Marine
    "滨岸": "shoreface",
    "前滨": "shoreface",
    "临滨": "shoreface",
    "浅海": "shallow_marine",
    "半深海": "deep_marine",
    "深海": "abyssal",
    "深水盆地": "abyssal",
}
```

Then modify `FaciesStyleResolver.resolve()`:

```python
    def resolve(self, facies_name: str) -> FaciesStyle:
        if facies_name in self._cache:
            return self._cache[facies_name]
        base = self._engine.get_color_fuzzy(facies_name) or QColor(DEFAULT_BASE_COLOR)
        pattern_id = FACIES_PATTERNS.get(facies_name)
        if pattern_id is not None:
            brush = self._engine.get_facies_brush(pattern_id, base)
            if brush is None:
                brush = self._engine.get_composite_brush(facies_name, base)
            if brush is None:
                brush = QBrush(base)
        else:
            brush = self._engine.get_composite_brush(facies_name, base)
            if brush is None:
                brush = QBrush(base)
        style = FaciesStyle(base_color=base, brush=brush, pattern_id=pattern_id)
        self._cache[facies_name] = style
        return style
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `pytest tests/test_facies_patterns.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/style.py tests/test_facies_patterns.py
git commit -m "feat: add FACIES_PATTERNS mapping and update resolver"
```

---

### Task 6: Update FaciesPolygonsLayer to use facies brushes

**Files:**
- Modify: `packages/geoviz_paleo_map/geoviz_paleo_map/layers/facies_polygons.py`
- Test: `tests/test_paleo_map_canvas.py` (add new test)

- [ ] **Step 1: Write the failing test**

In `tests/test_paleo_map_canvas.py`, add:

```python

def test_facies_polygon_uses_pattern_brush(qtbot):
    """A facies with a known pattern should have pattern_id set on its style."""
    canvas = _make_canvas(qtbot)
    canvas.load_features([
        {
            "type": "Feature",
            "properties": {"name": "三角洲区", "facies": "三角洲"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[110.0, 20.0], [120.0, 20.0], [120.0, 30.0],
                                [110.0, 30.0], [110.0, 20.0]]],
            },
        }
    ], period_name="测试")
    style = canvas._resolver.resolve("三角洲")
    assert style.pattern_id == "delta"
```

Run: `pytest tests/test_paleo_map_canvas.py::test_facies_polygon_uses_pattern_brush -v`
Expected: PASS (resolver already works, no code change needed in layer)

Wait — the layer already uses `style.brush` directly. Since the resolver now returns a composite brush for facies with patterns, the layer will automatically use it. No code change is needed in `facies_polygons.py`!

Let me verify by re-reading the paint method...

Yes, `facies_polygons.py` line ~160: `painter.setBrush(style.brush)` — it already uses the brush from the resolver. Since we updated the resolver to return a facies brush when `pattern_id` is set, the layer automatically uses it.

- [ ] **Step 1 (revised): Verify no code change needed in layer**

The `FaciesPolygonsLayer.paint()` already uses `style.brush` from the resolver. Since `FaciesStyleResolver.resolve()` now returns a composite facies brush for known facies patterns, no changes are needed in `facies_polygons.py`.

Write a confirming test in `tests/test_paleo_map_canvas.py`:

```python

def test_facies_with_pattern_renders_composite_brush(qtbot):
    """Facies '三角洲' should resolve to pattern_id='delta' with composite brush."""
    canvas = _make_canvas(qtbot)
    canvas.load_features([
        {
            "type": "Feature",
            "properties": {"name": "三角洲区", "facies": "三角洲"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[110.0, 20.0], [120.0, 20.0], [120.0, 30.0],
                                [110.0, 30.0], [110.0, 20.0]]],
            },
        }
    ], period_name="测试")
    qtbot.wait(20)
    style = canvas._resolver.resolve("三角洲")
    assert style.pattern_id == "delta"
    # Brush should be a QBrush (composite, not just solid color)
    from PySide6.QtGui import QBrush
    assert isinstance(style.brush, QBrush)
```

Run: `pytest tests/test_paleo_map_canvas.py::test_facies_with_pattern_renders_composite_brush -v`
Expected: PASS

- [ ] **Step 2: Commit**

```bash
git add tests/test_paleo_map_canvas.py
git commit -m "test: confirm facies patterns render through existing layer pipeline"
```

---

## Subsystem B: Vector SVG Export

### Task 7: Add export_vector_svg() using QSvgGenerator

**Files:**
- Modify: `packages/geoviz_paleo_map/geoviz_paleo_map/save_export.py`
- Test: `tests/test_export_vector.py`

- [ ] **Step 1: Write the failing test**

```python
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from PySide6.QtCore import QRectF

from geoviz_paleo_map import PaleoMapCanvas
from geoviz_paleo_map.save_export import export_vector_svg


SAMPLE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"name": "测试区", "facies": "砂岩"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[110.0, 20.0], [120.0, 20.0], [120.0, 30.0],
                                [110.0, 30.0], [110.0, 20.0]]],
            },
        }
    ],
}


def test_export_vector_svg_creates_file_with_path_elements(qtbot):
    canvas = PaleoMapCanvas()
    canvas.load_features(SAMPLE["features"], period_name="测试")
    qtbot.addWidget(canvas)
    canvas.resize(400, 300)
    canvas.show()
    qtbot.waitExposed(canvas)

    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
        path = Path(f.name)

    try:
        export_vector_svg(canvas, str(path), QRectF(0, 0, 400, 300))
        assert path.exists()
        assert path.stat().st_size > 100

        # Parse and verify it contains at least one <path> element
        tree = ET.parse(path)
        root = tree.getroot()
        ns = {"svg": "http://www.w3.org/2000/svg"}
        paths = root.findall(".//svg:path", ns)
        assert len(paths) > 0, "SVG should contain <path> elements"
    finally:
        path.unlink(missing_ok=True)
```

Run: `pytest tests/test_export_vector.py -v`
Expected: FAIL with `ImportError: cannot import name 'export_vector_svg'`

- [ ] **Step 2: Implement export_vector_svg()**

In `packages/geoviz_paleo_map/geoviz_paleo_map/save_export.py`, add after `export_svg()`:

```python

def export_vector_svg(canvas, file_path: str | Path, target_rect: QRectF | None = None) -> None:
    """Export the canvas as a true vector SVG using QSvgGenerator.

    All layer paint() methods render through QSvgGenerator's QPainter,
    producing SVG <path>, <text>, and <image> elements.

    Args:
        canvas: The PaleoMapCanvas to export.
        file_path: Output SVG file path.
        target_rect: Target rectangle in canvas coordinates. If None, uses the
            full canvas size.
    """
    from PySide6.QtSvg import QSvgGenerator

    file_path = Path(file_path)
    rect = target_rect or QRectF(0, 0, canvas.width(), canvas.height())

    generator = QSvgGenerator()
    generator.setFileName(str(file_path))
    generator.setSize(QSize(int(rect.width()), int(rect.height())))
    generator.setViewBox(rect)

    painter = QPainter(generator)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # Paint each layer directly through the generator's painter
    for layer in canvas._layers:
        painter.save()
        layer.paint(painter, canvas._viewport)
        painter.restore()

    painter.end()
```

Add the missing import at the top of `save_export.py`:

```python
from PySide6.QtCore import QRectF, QSize
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `pytest tests/test_export_vector.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/save_export.py tests/test_export_vector.py
git commit -m "feat: add true vector SVG export via QSvgGenerator"
```

---

## Subsystem C: Professional Figure Export

### Task 8: Create export_professional.py core module

**Files:**
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/export_professional.py`
- Test: `tests/test_export_professional.py`

- [ ] **Step 1: Write the failing test**

```python
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from PySide6.QtCore import QRectF

from geoviz_paleo_map import PaleoMapCanvas
from geoviz_paleo_map.export_professional import export_professional_figure


SAMPLE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"name": "测试区", "facies": "砂岩"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[110.0, 20.0], [120.0, 20.0], [120.0, 30.0],
                                [110.0, 30.0], [110.0, 20.0]]],
            },
        }
    ],
}


def test_professional_svg_creates_file_with_title(qtbot):
    canvas = PaleoMapCanvas()
    canvas.load_features(SAMPLE["features"], period_name="测试")
    qtbot.addWidget(canvas)
    canvas.resize(400, 300)
    canvas.show()
    qtbot.waitExposed(canvas)

    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
        path = Path(f.name)

    try:
        export_professional_figure(
            canvas, str(path), format="svg",
            title="测试古地理图",
            page_size="A4", orientation="landscape",
        )
        assert path.exists()
        assert path.stat().st_size > 100

        tree = ET.parse(path)
        root = tree.getroot()
        text = ET.tostring(root, encoding="unicode")
        assert "测试古地理图" in text
    finally:
        path.unlink(missing_ok=True)
```

Run: `pytest tests/test_export_professional.py::test_professional_svg_creates_file_with_title -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'geoviz_paleo_map.export_professional'`

- [ ] **Step 2: Create export_professional.py**

Write `packages/geoviz_paleo_map/geoviz_paleo_map/export_professional.py`:

```python
"""Professional figure export with standardized frame (title, scale bar, north arrow, legend, grid)."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtPrintSupport import QPrinter


_PAGE_SIZES_MM = {
    "A4": (297, 210),
    "A3": (420, 297),
    "A2": (594, 420),
}


def _page_size_mm(page_size: str, orientation: str) -> tuple[int, int]:
    w, h = _PAGE_SIZES_MM[page_size]
    if orientation == "portrait":
        return h, w
    return w, h


def _dpi_to_mm(dpi: int) -> float:
    return 25.4 / dpi


def export_professional_figure(
    canvas,
    file_path: str | Path,
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
    """Export a professional publishing-grade figure with standardized frame.

    Args:
        canvas: PaleoMapCanvas to export.
        file_path: Output file path.
        format: "svg", "pdf", or "png".
        title: Figure title (rendered in title block).
        page_size: Page size for PDF/print output.
        orientation: "portrait" or "landscape".
        dpi: Resolution for raster and PDF output.
        color_mode: "rgb" or "cmyk".
        include_scale_bar: Render scale bar in bottom-left.
        include_north_arrow: Render north arrow in top-right.
        include_legend: Render legend panel.
        include_grid_frame: Render coordinate grid frame around map.
    """
    file_path = Path(file_path)
    page_w_mm, page_h_mm = _page_size_mm(page_size, orientation)
    mm_per_px = _dpi_to_mm(dpi)
    page_w = int(page_w_mm / mm_per_px)
    page_h = int(page_h_mm / mm_per_px)

    if format == "svg":
        device = QSvgGenerator()
        device.setFileName(str(file_path))
        device.setSize(QSize(page_w, page_h))
        device.setViewBox(QRectF(0, 0, page_w, page_h))
    elif format == "pdf":
        device = QPrinter(QPrinter.PrinterMode.HighResolution)
        device.setOutputFileName(str(file_path))
        device.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        device.setResolution(dpi)
        from PySide6.QtGui import QPageSize as _QPageSize
        device.setPageSize(_QPageSize(
            getattr(_QPageSize.PageSizeId, page_size)
        ))
        if orientation == "landscape":
            device.setPageOrientation(Qt.Orientation.Horizontal)
        else:
            device.setPageOrientation(Qt.Orientation.Vertical)
    else:  # png
        from PySide6.QtGui import QPixmap
        device = QPixmap(page_w, page_h)
        device.fill(Qt.GlobalColor.white)

    painter = QPainter(device)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # Page background
    painter.fillRect(QRectF(0, 0, page_w, page_h), QColor("#ffffff"))

    # Margins (in pixels)
    margin = int(15 / mm_per_px)
    title_h = int(20 / mm_per_px) if title else 0
    bottom_h = int(15 / mm_per_px)
    right_w = int(60 / mm_per_px) if include_legend else 0

    # Map area
    map_x = margin
    map_y = margin + title_h
    map_w = page_w - margin * 2 - right_w
    map_h = page_h - margin - title_h - bottom_h - margin

    # --- Title Block ---
    if title:
        painter.setPen(QPen(QColor("#1a202c")))
        font = QFont("Microsoft YaHei", 14)
        font.setBold(True)
        painter.setFont(font)
        title_rect = QRectF(margin, margin, page_w - margin * 2, title_h)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, title)

    # --- Grid Frame ---
    map_rect = QRectF(map_x, map_y, map_w, map_h)
    if include_grid_frame:
        pen = QPen(QColor("#a0aec0"), 1.0)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(map_rect)
        # Tick marks every 20% along edges
        for i in range(1, 5):
            t = i / 5.0
            # Top
            x = map_x + map_w * t
            painter.drawLine(QPointF(x, map_y), QPointF(x, map_y + 5))
            # Bottom
            painter.drawLine(QPointF(x, map_y + map_h), QPointF(x, map_y + map_h - 5))
            # Left
            y = map_y + map_h * t
            painter.drawLine(QPointF(map_x, y), QPointF(map_x + 5, y))
            # Right
            painter.drawLine(QPointF(map_x + map_w, y), QPointF(map_x + map_w - 5, y))

    # --- Map Content ---
    # Create a temporary viewport scaled to the map rect
    from geoviz_paleo_map.viewport import PaleoMapViewport
    vp = PaleoMapViewport(
        center_lng=canvas._viewport.center_lng,
        center_lat=canvas._viewport.center_lat,
        zoom=canvas._viewport.zoom,
        width=map_w,
        height=map_h,
    )

    painter.save()
    painter.setClipRect(map_rect)
    painter.translate(map_x, map_y)
    for layer in canvas._layers:
        layer.paint(painter, vp)
    painter.restore()

    # --- Scale Bar ---
    if include_scale_bar:
        _draw_scale_bar(painter, map_x + 10, map_y + map_h - 25,
                        canvas._viewport, dpi)

    # --- North Arrow ---
    if include_north_arrow:
        _draw_north_arrow(painter, map_x + map_w - 30, map_y + 10)

    # --- Legend Panel ---
    if include_legend:
        _draw_legend_panel(painter, map_x + map_w + 10, map_y,
                           right_w - 10, map_h, canvas)

    painter.end()

    if format == "png":
        device.save(str(file_path), "PNG")


def _draw_scale_bar(painter: QPainter, x: float, y: float, viewport, dpi: int) -> None:
    """Draw a metric scale bar with auto-computed length."""
    import math

    lat = viewport.center_lat
    km_per_deg = 111.32 * math.cos(math.radians(lat))
    km_per_px = km_per_deg * (360.0 / (256.0 * (2 ** viewport.zoom)))

    # Pick a nice round length (1, 2, 5, 10, 20, 50, 100, 200, 500 km)
    target_px = 100
    target_km = target_px * km_per_px
    nice_lengths = [0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]
    bar_km = min(nice_lengths, key=lambda v: abs(v - target_km))
    bar_px = bar_km / km_per_px

    pen = QPen(QColor("#1a202c"), 2.0)
    pen.setCosmetic(True)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    # Bar line
    painter.drawLine(QPointF(x, y), QPointF(x + bar_px, y))
    # Ticks
    painter.drawLine(QPointF(x, y - 4), QPointF(x, y + 4))
    painter.drawLine(QPointF(x + bar_px, y - 4), QPointF(x + bar_px, y + 4))

    # Label
    painter.setPen(QPen(QColor("#1a202c")))
    font = QFont("Microsoft YaHei", 8)
    painter.setFont(font)
    label = f"{bar_km:g} km"
    painter.drawText(QRectF(x, y + 6, bar_px, 16),
                     Qt.AlignmentFlag.AlignCenter, label)


def _draw_north_arrow(painter: QPainter, x: float, y: float, size: float = 20.0) -> None:
    """Draw a simple north arrow."""
    pen = QPen(QColor("#1a202c"), 1.5)
    pen.setCosmetic(True)
    painter.setPen(pen)
    painter.setBrush(QColor("#1a202c"))

    # Arrow head (triangle pointing up)
    arrow = QPainterPath()
    arrow.moveTo(x + size / 2, y)
    arrow.lineTo(x + size, y + size)
    arrow.lineTo(x + size / 2, y + size * 0.7)
    arrow.lineTo(x, y + size)
    arrow.closeSubpath()
    painter.drawPath(arrow)

    # N label
    painter.setPen(QPen(QColor("#1a202c")))
    font = QFont("Microsoft YaHei", 8)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(QRectF(x, y + size + 2, size, 14),
                     Qt.AlignmentFlag.AlignCenter, "N")


def _draw_legend_panel(painter: QPainter, x: float, y: float,
                       width: float, height: float, canvas) -> None:
    """Draw a legend panel with color swatches and facies names."""
    # Gather visible facies names
    seen = set()
    for layer in canvas._layers:
        if hasattr(layer, "_resolver"):
            # This won't work directly — legend data comes from LegendLayer
            pass

    # Use the legend layer's facies names if available
    legend_layer = None
    for layer in canvas._layers:
        if hasattr(layer, "facies_names"):
            legend_layer = layer
            break

    if legend_layer is None:
        return

    facies_names = list(getattr(legend_layer, "facies_names", []))
    if not facies_names:
        return

    # Panel background
    painter.fillRect(QRectF(x, y, width, height), QColor("#f8fafc"))
    border_pen = QPen(QColor("#cbd5e1"), 1.0)
    border_pen.setCosmetic(True)
    painter.setPen(border_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(QRectF(x, y, width, height))

    # Title
    painter.setPen(QPen(QColor("#1a202c")))
    font = QFont("Microsoft YaHei", 9)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(QRectF(x + 4, y + 4, width - 8, 18),
                     Qt.AlignmentFlag.AlignLeft, "图例")

    # Swatches
    resolver = canvas._resolver
    swatch_size = 14
    row_h = 20
    text_x = x + swatch_size + 10
    text_w = width - swatch_size - 14

    painter.setFont(QFont("Microsoft YaHei", 8))
    for i, name in enumerate(facies_names):
        row_y = y + 24 + i * row_h
        style = resolver.resolve(name)
        painter.fillRect(QRectF(x + 4, row_y, swatch_size, swatch_size),
                         style.brush)
        painter.setPen(border_pen)
        painter.drawRect(QRectF(x + 4, row_y, swatch_size, swatch_size))
        painter.setPen(QPen(QColor("#1a202c")))
        painter.drawText(QRectF(text_x, row_y, text_w, swatch_size),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         name)
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `pytest tests/test_export_professional.py::test_professional_svg_creates_file_with_title -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/export_professional.py tests/test_export_professional.py
git commit -m "feat: add professional figure export with standardized frame"
```

---

### Task 9: Add comprehensive export tests

**Files:**
- Modify: `tests/test_export_professional.py`
- Modify: `tests/test_export_vector.py`

- [ ] **Step 1: Add vector export content verification tests**

In `tests/test_export_vector.py`, add:

```python

def test_export_vector_svg_contains_text_elements(qtbot):
    """Vector SVG should contain <text> elements from title layer."""
    from PySide6.QtCore import QRectF
    canvas = PaleoMapCanvas()
    canvas.load_features(SAMPLE["features"], period_name="测试")
    qtbot.addWidget(canvas)
    canvas.resize(400, 300)
    canvas.show()
    qtbot.waitExposed(canvas)

    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
        path = Path(f.name)

    try:
        export_vector_svg(canvas, str(path), QRectF(0, 0, 400, 300))
        tree = ET.parse(path)
        root = tree.getroot()
        ns = {"svg": "http://www.w3.org/2000/svg"}
        texts = root.findall(".//svg:text", ns)
        assert len(texts) > 0, "SVG should contain <text> elements"
    finally:
        path.unlink(missing_ok=True)
```

- [ ] **Step 2: Add professional export format tests**

In `tests/test_export_professional.py`, add:

```python

def test_professional_pdf_creates_file(qtbot):
    canvas = PaleoMapCanvas()
    canvas.load_features(SAMPLE["features"], period_name="测试")
    qtbot.addWidget(canvas)
    canvas.resize(400, 300)
    canvas.show()
    qtbot.waitExposed(canvas)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        path = Path(f.name)

    try:
        export_professional_figure(
            canvas, str(path), format="pdf",
            title="测试PDF",
            page_size="A4", orientation="landscape",
        )
        assert path.exists()
        assert path.stat().st_size > 1000
    finally:
        path.unlink(missing_ok=True)


def test_professional_png_creates_file(qtbot):
    from PIL import Image
    canvas = PaleoMapCanvas()
    canvas.load_features(SAMPLE["features"], period_name="测试")
    qtbot.addWidget(canvas)
    canvas.resize(400, 300)
    canvas.show()
    qtbot.waitExposed(canvas)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = Path(f.name)

    try:
        export_professional_figure(
            canvas, str(path), format="png",
            title="测试PNG",
            dpi=150,
        )
        assert path.exists()
        img = Image.open(path)
        assert img.size[0] > 1000  # A4 landscape at 150dpi is wide
    finally:
        path.unlink(missing_ok=True)


def test_professional_svg_has_legend_when_enabled(qtbot):
    canvas = PaleoMapCanvas()
    canvas.load_features(SAMPLE["features"], period_name="测试")
    qtbot.addWidget(canvas)
    canvas.resize(400, 300)
    canvas.show()
    qtbot.waitExposed(canvas)

    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
        path = Path(f.name)

    try:
        export_professional_figure(
            canvas, str(path), format="svg",
            title="测试",
            include_legend=True,
        )
        tree = ET.parse(path)
        root = tree.getroot()
        text = ET.tostring(root, encoding="unicode")
        assert "图例" in text
    finally:
        path.unlink(missing_ok=True)


def test_professional_svg_no_legend_when_disabled(qtbot):
    canvas = PaleoMapCanvas()
    canvas.load_features(SAMPLE["features"], period_name="测试")
    qtbot.addWidget(canvas)
    canvas.resize(400, 300)
    canvas.show()
    qtbot.waitExposed(canvas)

    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
        path = Path(f.name)

    try:
        export_professional_figure(
            canvas, str(path), format="svg",
            title="测试",
            include_legend=False,
        )
        tree = ET.parse(path)
        root = tree.getroot()
        text = ET.tostring(root, encoding="unicode")
        assert "图例" not in text
    finally:
        path.unlink(missing_ok=True)
```

- [ ] **Step 3: Run all new tests**

Run: `pytest tests/test_export_vector.py tests/test_export_professional.py -v`
Expected: PASS

- [ ] **Step 4: Run full test suite**

Run: `pytest`
Expected: All existing tests still pass (601+)

- [ ] **Step 5: Commit**

```bash
git add tests/test_export_vector.py tests/test_export_professional.py
git commit -m "test: add comprehensive export tests (SVG, PDF, PNG, legend toggle)"
```

---

## Final Integration

### Task 10: Update exports and run full verification

**Files:**
- Modify: `packages/geoviz_paleo_map/geoviz_paleo_map/__init__.py`

- [ ] **Step 1: Export new public APIs**

In `packages/geoviz_paleo_map/geoviz_paleo_map/__init__.py`, add:

```python
from geoviz_paleo_map.save_export import export_vector_svg
from geoviz_paleo_map.export_professional import export_professional_figure
```

And add to `__all__`:
```python
    "export_vector_svg", "export_professional_figure",
```

- [ ] **Step 2: Run full test suite**

Run: `pytest`
Expected: All tests pass (target: 620+)

- [ ] **Step 3: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/__init__.py
git commit -m "feat: export new public APIs (export_vector_svg, export_professional_figure)"
```

- [ ] **Step 4: Update task_plan and progress**

Update `task_plan.md` to mark Phase 10 as complete.
Update `progress.md` with Phase 10 completion summary.

```bash
git add task_plan.md progress.md
git commit -m "docs: mark Phase 10 complete"
```

---

## Spec Coverage Check

| Spec Section | Implementing Task |
|--------------|-------------------|
| 2.1 Data Model (pattern_id in FaciesStyle) | Task 1 |
| 2.2 SVG Asset Organization (facies/ subdir) | Tasks 2, 3 |
| 2.3 PatternEngine Extension (get_facies_brush) | Task 4 |
| 2.4 FaciesPolygonsLayer Integration | Task 6 (no code change needed) |
| 2.5 Directional Patterns deferred | Noted in spec, not implemented |
| 3.1 True Vector SVG Export | Task 7 |
| 3.2 Professional Figure Export | Tasks 8, 9 |
| 3.3 Canvas UI Integration | Out of scope (page layer responsibility) |
| 4 Testing Strategy | Tasks 1, 4, 6, 7, 8, 9 |

**No gaps identified.**

## Placeholder Scan

- No "TBD", "TODO", "implement later", "fill in details"
- No "Add appropriate error handling" / "add validation" / "handle edge cases"
- No "Write tests for the above" without actual test code
- No "Similar to Task N" references
- All steps show actual code or exact commands

## Type Consistency Check

- `FaciesStyle.pattern_id: str | None` — used consistently across Tasks 1, 5, 6
- `PatternEngine.get_facies_brush(pattern_id, base_color, alpha)` — signature consistent in Task 4
- `export_professional_figure()` parameters match spec Section 3.2
- `export_vector_svg(canvas, file_path, target_rect)` — signature consistent in Task 7

All consistent. ✅
