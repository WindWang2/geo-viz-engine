# PaleoMap QPainter 迁移设计

**日期**：2026-05-27
**作者**：WindWang2 + Claude
**状态**：Draft — 待审阅

## 背景与动机

`PaleoMap`（古地理图）目前底层是 `QWebEngineView` + ECharts，内联 ~295 行 HTML/JS 模板，加上 411 行的 `renderer.py`。这是主应用中**唯一**仍依赖 QWebEngineView 的页面。

继 MapPage 迁移之后，PaleoMap 是收尾步——完成后整个主应用零 WebEngine 依赖（虽然 QtWebEngine 仍在 PySide6 install 中，但不再被 import）。

**目标**：

- PaleoMap 渲染从 WebEngine + ECharts 迁移到原生 QPainter
- 抽取为独立包 `packages/geoviz_paleo_map/`（与 well-log/seismic/map 平行）
- 1:1 视觉/交互对齐（背景、polygon 复合花纹、边界样式、井位、标题、指北针、比例尺、图例、tooltip、pan/zoom）
- 删除 411 行 renderer.py + 295 行内联 HTML/JS + tempfile 中转

**非目标**：

- 不改变 page.py 的业务逻辑（拖拽加载、period 选择、compare 模式、导出）
- 不优化古地理数据本身（仍消费 `PaleoDataLoader` 的输出 dict）
- 不引入新功能（不加图层叠加、动画、时间轴等）

## 现状

`src/pages/paleo_map/renderer.py`（411 行）通过 ECharts 实现：

1. 多边形区域填充（per-feature 颜色 + 复合 SVG 花纹）
2. 边界样式（confirmed=实线灰、inferred=虚线灰、fault=实线红）
3. 区域标签（contrast-aware 字色）
4. 井位 scatter（57 红点 + 标签）
5. Tooltip（hover 显示 facies 名）
6. 地图标题（顶部居中）
7. 指北针（右上 SVG）
8. 比例尺（左下，动态 km）
9. 图例（右下，facies + 边线 + 井位）
10. ECharts `roam: true` 提供 pan/zoom

业务逻辑（`page.py`）：拖拽加载、period 下拉、compare 双视图、导出 SVG/PDF/PNG。这部分**保留不动**。

## 架构

新建独立包 `packages/geoviz_paleo_map/`，与 `geoviz-well-log` / `geoviz-seismic` / `geoviz-map` 平行。

**依赖**：

- `PySide6`、`pydantic`（标配）
- `geoviz-well-log`（复用 `PatternEngine` + `PATTERN_MAP` + `FACIES_COLORS`）
- **不**依赖 `geoviz-map`——投影不同（Plate Carrée vs Web Mercator），且 chrome 组件需求差异大

**PatternEngine 同步小增强**（Phase 2 Task 5 一并完成）：

现有 `PatternEngine.get_brush(name)` 返回**透明背景**的 SVG tile QBrush；现有 `get_color(name)` 仅做精确字典查 `FACIES_COLORS`。PaleoMap 需要：

1. `get_composite_brush(name: str, base_color: QColor, alpha: float = 0.6) -> QBrush` —— 复合纹理：底色 + 半透明 SVG pattern 叠加，得到 20×20 tiled QBrush。原 ECharts `makeCompositePattern` 的 Qt 等价物
2. `get_color_fuzzy(name: str) -> QColor | None` —— 按 longest-key-first substring 在 `FACIES_COLORS` 中匹配（与原 JS `matchColor` 一致）

两个新方法都加入 `geoviz_well_log.renderer.pattern_engine.PatternEngine`，well-log 自身不调用但留作公共 API；与 fuzzy `get_brush` 一致地内置缓存。

```
packages/geoviz_paleo_map/
├── pyproject.toml
├── README.md
└── geoviz_paleo_map/
    ├── __init__.py             # 公共 API
    ├── projection.py           # Plate Carrée（lng→x、lat→y 直接）
    ├── viewport.py             # PaleoMapViewport
    ├── zoom_pan.py             # ZoomPanHandler
    ├── canvas.py               # PaleoMapCanvas（QWidget 组合所有 layer）
    ├── style.py                # FaciesStyleResolver
    ├── models.py               # PaleoFeature, FaciesStyle, BoundaryStyle
    └── layers/
        ├── __init__.py
        ├── base.py             # PaleoLayer ABC
        ├── background.py
        ├── facies_polygons.py  # 核心：per-feature 颜色 + 复合花纹 + 边界
        ├── region_labels.py
        ├── wells_scatter.py
        ├── title.py
        ├── north_arrow.py
        ├── scale_bar.py
        └── legend.py
```

公共 API：

```python
from geoviz_paleo_map import PaleoMapCanvas, WellMarker

canvas = PaleoMapCanvas(parent=None)
canvas.load_features(features, period_name="C1", wells=[...])
```

`src/pages/paleo_map/page.py` 改动面：3 处替换（import / 实例化 / 数据传入），删 `_write_period_geojsons` + tempfile 中转。其余业务逻辑（compare、export、drag-drop）不动。

### 投影

**Plate Carrée（等距圆柱）**——按 ECharts 默认复现：

```python
# projection.py
def lnglat_to_world(lng: float, lat: float) -> tuple[float, float]:
    """Direct mapping; preserves angular spacing."""
    return lng, lat
```

无三角函数，比 Mercator 快 ~5×（对 scale bar 这种逐帧计算有感）。

### 渲染顺序与数据流

```
                  ┌──────────────────────────────────────┐
   features list  │   PaleoMapCanvas(QWidget)            │
   wells          │  ┌─────────────────────────────┐     │
   period_name    │  │ PaleoMapViewport            │     │
   ─────────────► │  │   center_lng/lat, zoom      │     │
                  │  │   lng/lat ↔ screen 映射     │     │
                  │  └──────────┬──────────────────┘     │
                  │             ▼                        │
                  │  paintEvent → 按序绘制（世界坐标层）：│
                  │   ① Background  (浅灰底 #f7fafc)     │
                  │   ② FaciesPolygons (per-feature 复合)│
                  │   ③ RegionLabels (centroid + contrast│
                  │      color)                          │
                  │   ④ WellsScatter (红点 + 标签)       │
                  │                                      │
                  │  paintEvent → 屏幕坐标 chrome 层：   │
                  │   ⑤ Title (顶部居中)                 │
                  │   ⑥ NorthArrow (右上)                │
                  │   ⑦ ScaleBar (左下，动态 km)         │
                  │   ⑧ Legend (右下，facies + 边线)     │
                  └──┬──────────────────────────┬────────┘
                     │                          │
              ZoomPanHandler           hover hit-test (FaciesPolygons)
              wheel/drag → viewport    polygon contains → QToolTip
```

### Layer 职责

| Layer | 职责 | 复杂度 |
|-------|------|--------|
| `Background` | 纯色 `#f7fafc` 全屏填充 | ~5 行 |
| `FaciesPolygons` | per-feature `FaciesStyle`（base color + 可选 pattern brush + boundary pen）→ drawPath | ~120 行 |
| `RegionLabels` | polygon centroid 文字 `props.name`，contrast-aware 字色 | ~40 行 |
| `WellsScatter` | 红 8px 圆点 + 白边 + 标签 | ~50 行 |
| `Title` | 顶部居中 `<period>岩相古地理图`，白底半透明 padding | ~25 行 |
| `NorthArrow` | 右上方角箭头 + `N` 字 | ~30 行 |
| `ScaleBar` | 左下 80px 线段 + `<N> km`，N ∈ `[1,2,5,10,20,50,100,200,500,1000]` 中最接近 `extent_km × 0.3` 的 | ~50 行 |
| `Legend` | 右下 facies swatch（base color + pattern）+ 3 边线样本 + 1 井位圆点 + 标题"图例" | ~80 行 |

### Style 解析

```python
# style.py
class FaciesStyleResolver:
    """Resolve a facies name to (base_color, brush, boundary_pen).

    Caches per-facies result; multiple polygons of the same facies share
    a single QBrush instance via the PatternEngine LRU cache.
    """

    def __init__(self, pattern_engine: PatternEngine):
        self._engine = pattern_engine
        self._cache: dict[str, FaciesStyle] = {}

    def resolve(self, facies_name: str) -> FaciesStyle:
        if facies_name in self._cache:
            return self._cache[facies_name]
        base_color = self._engine.get_color_fuzzy(facies_name) or QColor("#d9d4c8")
        # get_composite_brush returns None when no pattern matches → fall back
        # to a plain QBrush(base_color).
        brush = (self._engine.get_composite_brush(facies_name, base_color)
                 or QBrush(base_color))
        style = FaciesStyle(base_color=base_color, brush=brush)
        self._cache[facies_name] = style
        return style


def boundary_pen(kind: str) -> QPen:
    if kind == "confirmed":
        return QPen(QColor("#555555"), 1.5)
    if kind == "inferred":
        pen = QPen(QColor("#555555"), 1.5)
        pen.setDashPattern([6.0, 3.0])
        return pen
    if kind == "fault":
        return QPen(QColor("#e53e3e"), 2.0)
    return QPen(QColor("#555555"), 1.0)
```

`match_color` / `match_pattern` 走 longest-key-first substring 匹配（与原 ECharts JS 实现一致）。

### Tooltip 与 Hit-Test

`mouseMoveEvent` 内 hit-test 流程：

1. 屏幕坐标 → 世界坐标
2. bbox 粗筛（O(N) 比较）
3. 候选 polygon 跑 `QPainterPath.contains(world_pt)`（O(顶点数)，候选通常 1-3 个）
4. 命中 → `QToolTip.showText(globalPos, facies_name)`
5. 离开 → `QToolTip.hideText()`

## 性能策略

### 一次性预计算（init 时做、paint 不重做）

| 资源 | 缓存层级 | 命中粒度 |
|------|----------|----------|
| `QPainterPath`（每个 polygon 的世界坐标路径） | `FaciesPolygonsLayer._items` | 一次构建，永久持有 |
| 世界坐标 bbox（每个 polygon） | 同上 | 用于视口剔除 + hit-test 粗筛 |
| `FaciesStyle`（base color + brush + boundary pen） | `FaciesStyleResolver._cache` | 按 facies 名缓存；60+ polygon 同 facies 共享 1 个 style |
| 复合 QBrush（base + pattern overlay） | `PatternEngine` LRU | 按 `(pattern_id, base_color)` 缓存；多 polygon 共享 brush 实例 |
| Region label centroid + text width | `RegionLabelsLayer._label_items` | 一次算 |

**关键收益**：60 个 polygon 全用同一 facies → 1 个 QBrush 实例复用，不是 60 个。

### Paint 阶段每帧执行

1. **Viewport bbox 剔除**：跳过完全在屏外的 polygon
2. **单一 QTransform**：`painter.translate + scale + translate` 共享变换
3. **Brush 状态切换最小化**：按 facies 排序绘制（同 facies 连续完成才换 brush）
4. **Antialiasing 局部开关**：polygon 填充开 AA、chrome 文字开 TextAA、井点不必
5. **Chrome 层不做内容缓存**：每层 <20 行 drawText/drawRect，单帧 <0.5 ms 可忽略

### 交互响应

Tooltip hit-test 经 bbox 粗筛后通常只 path.contains 1-2 个 polygon，~1µs/move。
不引入空间索引（YAGNI）。

### Compare 模式

- 两个 canvas 共享同一 `PatternEngine` 实例（page.py 注入）
- QPainterPath 不共享（Qt object mutable）；一份内存 ~MB 级，无瓶颈

### 性能基线（强制 assertion）

`tests/test_paleo_map_canvas.py::test_paint_performance`：

```python
def test_paint_performance(qtbot, large_geojson):
    """200 polygons + 57 wells: paint < 50ms after warm-up."""
    canvas = PaleoMapCanvas(parent=None)
    canvas.load_features(large_geojson, wells=wells_data)
    qtbot.addWidget(canvas); canvas.resize(1200, 800); canvas.show()
    canvas.repaint()  # warm-up
    t0 = time.perf_counter()
    for _ in range(10):
        canvas.repaint()
    avg_ms = (time.perf_counter() - t0) / 10 * 1000
    assert avg_ms < 50, f"avg paint {avg_ms:.1f}ms exceeds 50ms"
```

阈值 50 ms = 20 FPS 拖动流畅；MapPage 当前 60+ polygon ~10-20 ms，PaleoMap 翻倍 polygon + 复合 brush，留 2× 余量。

### 内存上限（参考）

- 200 polygon × 平均 50 顶点 × 16 B/QPointF = ~160 KB
- 16 SVG pattern × 20×20 QImage = ~25 KB
- LRU brush cache (100 entries × ~1 KB QBrush metadata) = ~100 KB
- 总 < 300 KB/canvas；compare 模式 < 600 KB

## Page 集成

`src/pages/paleo_map/page.py` 三处替换：

```diff
- from src.pages.paleo_map.renderer import PaleoMapRenderer
+ from geoviz_paleo_map import PaleoMapCanvas

  # 三处实例化（_init_、_start_compare、_stop_compare）
- self.map_view = PaleoMapRenderer(self)
+ self.map_view = PaleoMapCanvas(parent=self)

  # _on_period_changed
- geojson_path = self._period_geojson_files.get(period_name)
- if geojson_path:
-     self.map_view.load_geojson(geojson_path, period_name=period_name)
+ features = self._periods.get(period_name)
+ if features:
+     self.map_view.load_features(features, period_name=period_name)
```

副作用：

- 删 `_write_period_geojsons` + `_period_geojson_files` + tempfile 清理（~25 行）
- 删 `_cleanup_tmp` 调用
- compare/drag-drop/export 不动
- `self.map_view.grab()` 在 QWidget 子类工作，导出零改动

## 测试策略

### 单元测试（`tests/paleo_map/`）

| 文件 | 覆盖 |
|------|------|
| `test_projection.py` | Plate Carrée 数学：原点、单位度、负坐标 |
| `test_viewport.py` | center→屏幕中心、zoom +1→距离 ×2、resize |
| `test_zoom_pan.py` | 拖拽方向、cursor-anchored wheel、clamp |
| `test_style_resolver.py` | facies longest-match → color + pattern；命中/未命中分支 |
| `test_layer_background.py` | 中心像素 = `#f7fafc` |
| `test_layer_facies_polygons.py` | 渲染色匹配、虚线 boundary、断层红线、point-in-polygon hit |
| `test_layer_region_labels.py` | 浅底深字 / 深底浅字（contrast color 选择） |
| `test_layer_wells_scatter.py` | 红点 + 标签 + 命中半径 |
| `test_layer_title.py` | 文字定位居中 |
| `test_layer_north_arrow.py` | 30×40 位置正确 |
| `test_layer_scale_bar.py` | 给定 viewport extent 算出预期 `<N> km`（覆盖 nice steps 选择） |
| `test_layer_legend.py` | seen facies 集合 → 条目数 |

### 集成测试（`tests/test_paleo_map_canvas.py`）

- `PaleoMapCanvas + load_features().grab()` 非空
- hover polygon → `QToolTip.showText` 被调用（mock）
- resize 后 viewport 跟随
- compare 双实例同时存在无 tempfile 冲突
- **性能基线**：200 polygon 平均 paint < 50 ms

### 视觉一致性回归（`tests/test_paleo_map_visual_parity.py`）

复用 `tests/utils/visual_parity.py`。

- 用 `samples/sample_paleo.geojson` 作为输入
- 固定 viewport 渲染 → 与 `tests/golden/paleo_map_default.png` 比对
- 容差 1%（同 MapPage）

## 迁移步骤

**Phase 1：包骨架 + 基础（4 task）**
1. Scaffold package + 注册 workspace
2. Plate Carrée projection
3. PaleoMapViewport + 单元测试
4. ZoomPanHandler

**Phase 2：核心渲染层（5 task）**
5. PatternEngine 扩展（`get_composite_brush` + `get_color_fuzzy`）+ Models + StyleResolver
6. PaleoLayer ABC + BackgroundLayer
7. FaciesPolygonsLayer（最大单层 ~120 行）
8. RegionLabelsLayer
9. WellsScatterLayer

**Phase 3：Chrome 层（4 task）**
10. TitleLayer
11. NorthArrowLayer
12. ScaleBarLayer
13. LegendLayer

**Phase 4：集成 + 验收 + 清理（5 task）**
14. PaleoMapCanvas 合成 + hover tooltip + canvas 集成测试（含性能基线）
15. 接 `paleo_map/page.py`（保留 renderer.py 待删）
16. 生成 golden image + 视觉一致性回归测试
17. **人工验收门**：拖一份 GeoJSON 验证渲染、tooltip、compare、export 全通
18. 删 `src/pages/paleo_map/renderer.py` + tempfile 中转代码；更新 CLAUDE.md / README.md / CHANGELOG.md

**总计 18 task**。

## 删除清单

| 资产 | 量化 | 操作 |
|------|------|------|
| `src/pages/paleo_map/renderer.py` | 411 行（含 295 行内联 HTML/JS） | 删 |
| `_write_period_geojsons` + `_period_geojson_files` + `_cleanup_tmp` | ~25 行 | 删（page.py 内联） |
| `_PaleoMapPage(QWebEnginePage)` 子类 + URL scheme 限制 | — | 一并消失 |
| Tempfile-based GeoJSON 中转 | — | 消失（直接传 dict） |

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| Tooltip hit-test 性能（mouseMove 高频） | bbox 粗筛 + path.contains 二阶；测试覆盖 200 polygon 场景 |
| Region label centroid 在凹 polygon 外 | 起步用 bbox center；已知妥协，必要时引入 visual center 算法 |
| Compare 模式 PatternEngine 共享 | page.py 注入全局 PatternEngine 实例 |
| Plate Carrée 在 PaleoMap 是否"对" | 按原 ECharts 约定，照搬不引入争议 |
| 拖拽加载新 GeoJSON 刷新 | `load_features` 内重建 layers list 并 `update()`；Canvas 内部封好 |
| QPainterPath.contains 复杂 polygon 慢 | 已通过 bbox 粗筛缓解；如成瓶颈再上 R-tree |

## 验收标准

迁移完成的判定（DONE）：

1. 所有新增单元/集成/视觉一致性测试通过
2. `test_paint_performance` 单帧平均 < 50 ms（200 polygon + 57 wells）
3. 启动应用，PaleoMap 页：
   - 拖拽 `samples/sample_paleo.geojson` 后画面渲染（背景灰、polygon 上色 + SVG 花纹、井点红、标题/指北/比例尺/图例齐全）
   - hover 某 polygon → 弹出 tooltip 显示 facies 名
   - 切换 period（如多时期）→ 视图刷新
   - 右上"对比"按钮 → 双屏并排，分别 hover/click 独立工作
   - 导出 PNG/SVG/PDF 仍能产出图片
4. `pytest -q` 全套通过
5. 旧 `PaleoMapRenderer` + tempfile 中转代码已删
6. CLAUDE.md / README.md / CHANGELOG.md 已更新
