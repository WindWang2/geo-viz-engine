# MapPage QPainter 迁移设计

**日期**：2026-05-27
**作者**：WindWang2 + Claude
**状态**：Draft — 待审阅

## 背景与动机

`MapPage`（井位分布图）当前底层是 `QWebEngineView` + MapLibre GL JS，内联 ~600KB JS/CSS，通过 `well://` 自定义 URL scheme 与 Python 通信。

`geoviz_well_log` 与 `geoviz_seismic` 均已采用原生 QPainter / pyqtgraph 渲染，MapPage 是主应用中**最后一个**重度依赖 QWebEngineView 的页面（PaleoMap 暂保留，不在本次范围）。

迁移目标：

- 移除 MapPage 的 WebEngine 依赖路径
- 与 well-log / seismic 形成统一的"独立可视化包"架构
- 消除 Windows 上 WebEngine + OpenGL 上下文顺序的潜在隐患
- 删除 ~700KB 内联静态资源

非目标：

- 不改变现有视觉/交互行为（净迁移，1:1 功能对齐）
- 不动 PaleoMap（仍保留 QWebEngineView + ECharts）
- 不内嵌 GeoJSON 资产到包内

## 现状

`src/pages/map/renderer.py`（394 行）当前实现的功能：

1. MapLibre GL JS 渲染（内联 JS/CSS，完全离线）
2. World GeoJSON + China Provinces GeoJSON 双层底图（统一沙色 `#f3f1ec`，灰色边界）
3. 经纬网（每 2°，虚线，蓝色 `#0284c7` opacity 0.12）
4. 57 口井 marker：14px 圆点 + 白边阴影 + 文字标签 + 白色文字晕影 + hover scale 1.2
5. 15 个参考点：北京/上海/广州/深圳/香港/澳门/惠州/珠海/汕头/湛江/海口/福州/台北/南宁 + "南海"斜体海域标签
6. 海水蓝底色 `#cbebfb`
7. 固定 zoom 7.5，仅支持平移
8. 井点点击 → `well://click?name=<urlencoded>` → `_MapPage.acceptNavigationRequest` 截获 → Python 回调

## 架构

新建独立包 `packages/geoviz_map/`，与 `geoviz_well_log` / `geoviz_seismic` 同级。

```
packages/geoviz_map/
├── pyproject.toml
└── geoviz_map/
    ├── __init__.py            # 公共 API
    ├── models.py              # WellMarker, ReferenceLabel
    ├── projection.py          # Web Mercator 投影
    ├── viewport.py            # MapViewport (center+zoom 像素映射)
    ├── zoom_pan.py            # 滚轮缩放向光标 + 拖拽平移
    ├── canvas.py              # MapCanvas (QWidget 组合 layers)
    └── layers/
        ├── __init__.py
        ├── base.py            # MapLayer 抽象基类
        ├── background.py
        ├── graticule.py
        ├── geojson_polygon.py # World/China 共用
        ├── reference.py       # 城市点 + 南海斜体
        └── wells.py           # 井点 + halo 标签 + hover + click
```

公共 API：

```python
from geoviz_map import MapCanvas, WellMarker, ReferenceLabel

canvas = MapCanvas(
    wells=[WellMarker(name="HZ19-1", lng=114.5, lat=20.1, color="#ef4444",
                      has_data=True), ...],
    world_geojson={...},
    china_geojson={...},
    reference_labels=[
        ReferenceLabel(name="香港", lng=114.17, lat=22.32, kind="city"),
        ReferenceLabel(name="南海", lng=115.5, lat=20.2, kind="sea"),
        ...
    ],
    initial_center=(118.0, 25.0),
    initial_zoom=7.5,
)
canvas.well_clicked.connect(lambda name: ...)
```

`src/pages/map/page.py` 收缩到 ~15 行薄壳，负责从 `DataCache` 读 wells、从 `data/` 读 geojson、连信号。

### 渲染顺序与数据流

```
                  ┌─────────────────────────────────┐
   wells, geojson │   MapCanvas(QWidget)            │
   reference_lbls │  ┌──────────────────────────┐   │
   ─────────────► │  │ MapViewport              │   │
                  │  │  center_xy, zoom         │   │
                  │  │  → screen ↔ world 映射  │   │
                  │  └──────────┬───────────────┘   │
                  │             ▼                   │
                  │  paintEvent → 按顺序绘制：       │
                  │   ① Background  (纯色)          │
                  │   ② Graticule   (虚线网格)      │
                  │   ③ WorldFill+Border            │
                  │   ④ ChinaFill+Border            │
                  │   ⑤ ReferenceLabels             │
                  │   ⑥ Wells (顶层，含 hover/halo) │
                  └───┬─────────────────────┬───────┘
                      │                     │
              ZoomPanHandler         Hit-test (mousePress)
              wheel/drag → viewport   distance² ≤ r²
                                            │
                                     well_clicked: Signal(str)
```

### Layer 接口

```python
class MapLayer(ABC):
    def paint(self, painter: QPainter, viewport: MapViewport) -> None: ...

    def hit_test(self, screen_pt: QPointF,
                 viewport: MapViewport) -> str | None:
        """Override for interactive layers. Default: no hit."""
        return None
```

`MapCanvas.mousePressEvent` 逆序遍历 layers 调 `hit_test`，井点最先响应。

### Web Mercator 投影

```python
class MapViewport:
    R = 6378137.0  # 地球半径（Web Mercator 标准）

    def __init__(self, center_lng, center_lat, zoom, width, height):
        self.center_world = self._lnglat_to_world(center_lng, center_lat)
        self.zoom = zoom
        self.width, self.height = width, height

    @staticmethod
    def _lnglat_to_world(lng, lat):
        x = math.radians(lng) * MapViewport.R
        y = math.log(math.tan(math.pi/4 + math.radians(lat)/2)) * MapViewport.R
        return (x, y)

    def world_to_screen(self, x, y):
        scale = 256 * 2**self.zoom / (2 * math.pi * self.R)
        sx = (x - self.center_world[0]) * scale + self.width / 2
        sy = (self.center_world[1] - y) * scale + self.height / 2  # Y 翻转
        return QPointF(sx, sy)

    def lnglat_to_screen(self, lng, lat):
        return self.world_to_screen(*self._lnglat_to_world(lng, lat))
```

公式选取理由：与 MapLibre GL 内部 mercator 投影完全一致，保证黄金图比对可以做严格视觉一致性。

### 性能要点

- `QPainterPath` 预构建：World 与 China geojson 在初始化时各转一次 `QPainterPath`，paint 时只对路径做坐标变换 + `drawPath`，不重建几何
- 视口剔除：`MapViewport.world_bbox()` 返回当前可视区世界坐标范围，`GeoJsonPolygonLayer` 跳过完全在屏外的 polygon（缩放后省 ~90% 绘制）
- Wells 数量小（57），不剔除；hover 状态变更触发**仅 wells layer 区域**重绘 `update(wells_bbox)`
- High-DPI：dot 直径、字号、网格线宽等通过 `devicePixelRatio()` 自适配

### 交互

| 操作 | 行为 |
|------|------|
| 鼠标拖拽 | 平移视口中心 |
| 滚轮 | 以光标为锚点缩放（光标处经纬度在缩放前后不变） |
| Hover 井点 | 圆点 scale 1.2 |
| Click 井点 | `well_clicked.emit(name)` |

点击 hit-test：在 `WellsLayer.paint` 时把每口井的屏幕坐标 + 半径缓存为列表；`hit_test` 用 `distance² ≤ r²` 判断。

## 测试策略

沿用 well-log 迁移已经验证有效的"视觉一致性回归网"。

### 单元测试

| 测试文件 | 覆盖 |
|----------|------|
| `tests/map/test_projection.py` | Web Mercator 数学：已知点往返、赤道、零经度、极区（>85.05°）拒绝 |
| `tests/map/test_viewport.py` | `lnglat_to_screen` 中心点 → 屏幕中心；zoom +1 → scale ×2；pan 后位移正确 |
| `tests/map/test_zoom_pan.py` | 滚轮缩放向光标（光标处 lng/lat 在缩放前后不变）；拖拽 Δx → 中心经度增量正确 |
| `tests/map/test_layer_background.py` | 离屏渲染，中心像素 = `#cbebfb` |
| `tests/map/test_layer_graticule.py` | 经线像素列存在虚线段 |
| `tests/map/test_layer_polygon.py` | World polygon 在 viewport 内被绘制；屏外 polygon 被剔除 |
| `tests/map/test_layer_reference.py` | "南海"渲染为斜体，字号符合规格 |
| `tests/map/test_layer_wells.py` | 点击 (well_x, well_y) → `hit_test` 返回 name；偏移 20px → None |

### 集成测试

`tests/test_map_canvas.py`：

- `MapCanvas(57 wells, world, china).grab()` → 非空 QImage
- `well_clicked` 信号：模拟 mousePress at well 屏幕坐标 → 收到对应 name
- 性能基线：57 wells + China geojson 首次 paint < 100ms

### 视觉一致性测试（关键）

`tests/test_map_visual_parity.py`：

- 固定 viewport（center=(118, 25), zoom=7.5, 1200×800）渲染 → 与黄金图比对
- 黄金图生成步骤：MapLibre 版本渲染同一视口 → `grab()` 保存到 `tests/golden/map_canvas_default.png`，人工确认后入库
- 容差：HSV 差异 > 阈值的像素 < 0.5%
- 关键检查区域：井点位置、海岸线、中国省界、网格交点

## 迁移步骤

增量、每步独立可测、可中断。

**Phase 1：包骨架**
1. 新建 `packages/geoviz_map/` + `pyproject.toml`，注册到根 `pyproject.toml` workspace
2. `models.py` + `projection.py` + `viewport.py` + 单元测试
3. `zoom_pan.py` + 单元测试

**Phase 2：layers**
4. `BackgroundLayer` + 测试
5. `GraticuleLayer` + 测试
6. `GeoJsonPolygonLayer`（World/China 共用）+ `QPainterPath` 缓存 + 视口剔除 + 测试
7. `ReferenceLabelsLayer`（城市点+斜体南海）+ 测试
8. `WellsLayer`（dot + halo label + hover + hit-test）+ 测试

**Phase 3：组装与切换**
9. `MapCanvas` 组合所有 layer + `well_clicked` 信号 + 集成测试
10. 视觉一致性测试 + 黄金图生成
11. 改 `src/pages/map/page.py` 接 `MapCanvas`，**保留** `src/pages/map/renderer.py`（旧 MapRenderer）以便双跑对比
12. 视觉/交互人工验收（含 hover、click、pan、zoom）

**Phase 4：清理**
13. 删 `src/pages/map/renderer.py`（394 行）
14. 删 `src/pages/map/assets/maplibre-gl.js`（~600 KB）
15. 删 `src/pages/map/assets/maplibre-gl.css`（~40 KB）
16. 更新 `CLAUDE.md` 项目结构 + Architecture 段
17. 更新 `README.md` Project Structure
18. `CHANGELOG.md` `[Unreleased]` 加 entry

## 删除清单

| 资产 | 量化 | 操作 |
|------|------|------|
| `src/pages/map/renderer.py` | 394 行 | 删 |
| `src/pages/map/assets/maplibre-gl.js` | ~600 KB | 删 |
| `src/pages/map/assets/maplibre-gl.css` | ~40 KB | 删 |
| `MAPLIBRE_HTML` 内联模板 | 258 行 | 删（已含在 renderer.py） |
| 临时 HTML 写入 `/tmp` 逻辑 | — | 一并消失 |
| `well://` URL scheme + `QWebEnginePage` 子类 | — | 一并消失 |
| `LocalContentCanAccessRemoteUrls` 设置 | — | 一并消失 |

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| China provinces geojson 较大（数 MB），首次 path 构建慢 | 初始化时一次性构建并持有 `QPainterPath`，paint 不重建 |
| GeoJSON 多边形含洞（multi-ring）需正确填充 | 用 `Qt.WindingFill` 规则；单元测试覆盖含洞 polygon |
| High-DPI 显示器上像素尺寸偏小 | 所有像素值乘 `devicePixelRatio()`，加 High-DPI 测试 |
| Hover 全屏重绘性能差 | `update(wells_layer_rect)` 仅重绘井点区域 |
| 黄金图与 MapLibre 微差异（字体渲染、抗锯齿） | 容差 0.5%；关键检查区只比井位/边界/网格几何，不比文字像素 |
| 迁移期回归未察觉 | Phase 3 保留旧 renderer，双跑对比通过后再 Phase 4 删 |

## 依赖影响

- **不变**：QtWebEngine 仍被 PaleoMap 使用，不能从根 `pyproject.toml` 移除
- **新增**：`packages/geoviz_map` 注册到 workspace；公共 API 通过 `geoviz_map` 包暴露
- **数据共享**：`data/world.json` 与 `data/china_provinces.json` 仍由 app 加载并注入包，保持包独立性

## 验收标准

迁移完成的判定（DONE）：

1. 所有新增单元/集成/视觉一致性测试通过
2. 启动应用，地图页：
   - 视觉与旧版无可察觉差异（参考黄金图）
   - 拖拽、滚轮缩放、井点 hover、井点 click 均工作
   - 切换到地图页 → 其他页 → 切回，无内存泄漏（pytest-qt `qtbot.wait`）
3. `pytest` 全套通过
4. 旧 `MapRenderer` 与 maplibre assets 已删除
5. CLAUDE.md / README / CHANGELOG 已更新
