# 测井图模块化制图引擎 — 设计规格书

## 概述

将现有的 well_log 渲染引擎从"Track 配置列表驱动"改造为真正的**模块化体系**，支持：初始化时自适应铺满窗口、曲线成组、全联动缩放、灵活的模块组合与后期调整。

---

## 1. 约束与目标（非功能性）

| 编号 | 描述 |
|-----|------|
| C1 | 单井先行；多井模式为后期计划，预留接口 |
| C2 | 初始化或窗口变化时，数据必须占满垂直可视区域 |
| C3 | 曲线可两两成组（AC+GR、RT+RXO 等），同组曲线共享纵轴标尺 |
| C4 | 缩放采用全联动模式：任一模组 zoom 均触发全员重绘 |
| C5 | 沉积相三列（微相/亚相/相）为配置级固定，不可由用户拆散 |
| C6 | 岩性+描述为可选联合，默认相邻，后期可重组显示序列 |
| C7 | 所有改动不对外破坏现有的 Pydantic 模型与 pytest 测试 |

---

## 2. 模块层级划分

自底向上分为三层，从细节绘制到编排协调：

### Layer 1 — Leaf Module（叶子模块）

单 responsibility：在已知深度范围内，按固定宽高比自己把自己绘制出来。

```python
class LeafModule(Protocol):
    def sync_depth(self, top_m: float, bottom_m: float) -> None:
        """由 Coordinator 调用，告知当前可见深度窗口"""

    def preferred_width(self) -> int:
        """返回配置的建议宽度，供 LayoutCalculator 使用"""

    def set_pixel_density(self, px_per_meter: float) -> None:
        """Coordinator 根据窗口尺寸计算出 px_per_meter，分发下来"""
```

现有类经最小改造后均满足此协议：

- `CurveTrack` — 用 `pyqtgraph PlotWidget` 作图
- `DepthTrack` — 同上，左侧纵轴专用
- `IntervalTrack` — `paintEvent` 内查 `_px_per_m` 绘制矩形与文字
- `TextTrack` — 同上，纯文字
- `SystemsTractTrack` — 绘制 HST/TST 三角形

新增 `@property` 到每个 Track：

```python
# 以 IntervalTrack 为例，其余类同理
def preferred_width(self) -> int:
    return self._config.width

def set_pixel_density(self, px_per_m: float):
    self._px_per_m = px_per_m
    self.update()   # 触发 paintEvent 重绘
```

### Layer 2 — Composite Module（复合模块）

把有关联的一组 Leaf Module 包装成单一编排单元。

```python
@dataclass
class CompositeModule:
    label: str
    children: list[LeafModule]          # 横向叠加（同宽不同内容）
    width_override: int | None = None   # 若设，则优先使用；否则 sum(children)

    def sync_depth(self, top_m, bottom_m):
        for c in self.children:
            c.sync_depth(top_m, bottom_m)

    def set_pixel_density(self, px_per_m):
        for c in self.children:
            c.set_pixel_density(px_per_m)

    def preferred_width(self) -> int:
        return self.width_override or sum(c.preferred_width() for c in self.children)
```

典型实例化：

```python
# AC + GR 共用左轴（仅示意数据结构，非最终 API）
ac_gr_composite = CompositeModule(
    label="AC/GR",
    children=[curve_track_for_AC, curve_track_for_GR],
    width_override=120,
)

# 岩性 + 描述（可拆卸，所以不是 CompositeModule，而是 LayoutCoordinator 里的顺序编排）
# 见 第 5 节说明
```

> 注意：复合模块内部不存在"上下拼接"，只有"横向并排"关系。纵向拼接（即不同模块沿深度方向的排列顺序）完全由 LayoutCoordinator 决定，复合模块对此无感知。

### Layer 3 — Layout Coordinator（布局协调器）

```python
@dataclass
class LayoutCoordinator:
    master_vb: pg.ViewBox                     # DEPTH 共享源
    modules: list[LeafModule | CompositeModule]  # 有序列表，代表横向从左到右的列
    viewport_height: int                       # scrollArea 内容区高度

    def fit_to_viewport(self):
        """初始化及每次 resize 时调用，使数据铺满可见区"""
        _, (_, d_bot), _) = self.master_vb.getViews()  # 或另存取方法
        vis_top, vis_bot = self.master_vb.viewRange()[1]  # DEPTH 已设为全范围
        span = vis_bot - vis_top
        px_per_m = self.viewport_height / span
        for mod in self.modules:
            mod.set_pixel_density(px_per_m)
        self._broadcast_range(vis_top, vis_bot)

    def _broadcast_range(self, top_m, bottom_m):
        for mod in self.modules:
            mod.sync_depth(top_m, bottom_m)

    def on_master_range_changed(self, vb, y_range):
        """连接到 master ViewBox 的 sigYRangeChanged"""
        self._broadcast_range(y_range[0], y_range[1])

    def on_resize(self, height: int):
        self.viewport_height = height
        self.fit_to_viewport()

    def modules_from_config(
        self, chart_config: ChartConfig,
        data: WellLogData, top_depth: float, bottom_depth: float
    ) -> list[LeafModule | CompositeModule]:
        """工厂：从 ChartConfig 构建各 LeafModule，按约束聚合为 CompositeModule"""
        ...
```

---

## 3. 数据流与生命周期

### 初始化（初次构建）

```
WellLogPage.load_well()
  └─ ChartEngine.__init__(data, config)
       ├─ Coordinator.modules_from_config(...)  # 创建所有叶子模块，按约束聚合成 CompositeModule
       ├─ scrollArea.setWidget(container)       # container 水平容纳所有列
       ├─ master_vb.setYRange(top_depth, bottom_depth)
       ├─ Coordinator.fit_to_viewport()          # 计算 px_per_m，发给所有人
       └─ master_vb.sigYRangeChanged.connect(coordinator.on_master_range_changed)
```

### 用户执行缩放（DEPTH 轴或其他曲线触发）

```
用户滚轮 或 pyqtgraph 内部
  └─ master_vb.scaleBy / panBy （pyqtgraph 自己处理）
       └─ sigYRangeChanged.fire(master_vb, y_range)
            └─ Coordinator.on_master_range_changed(vb, y_range)
                 └─ _broadcast_range(new_top, new_bottom)
                      └─ 每个 LeafModule.sync_depth(new_top, new_bottom)
                           └─ IntervalTrack/TextTrack/SystemsTractTrack.update() → 重绘
```

### 窗口 resize

```
ChartEngine.resizeEvent(event)
  └─ coordinator.on_resize(scroll_area.viewport().height())
       └─ fit_to_viewport()
            └─ 计算 px_per_m，发给所有人，全体重绘
```

---

## 4. 各 Track 模块改造要求

### 4.1 CurveTrack（含 DepthTrack）

- 已有 `set_depth_range(top, bottom)` 通过 `view_box.setYRange`
- 新增 `set_pixel_density(px_per_m)` 用于密度广播（当前 pyqtgraph 无需此参数，跳过）
- 新增 `preferred_width()`

```python
def set_pixel_density(self, px_per_m: float):
    pass  # pyqtgraph 自动从 viewbox 拿到 scale，无额外动作
```

### 4.2 IntervalTrack、TextTrack、SystemsTractTrack

这三者共三层改动，以下以 IntervalTrack 为例，TextTrack / SystemsTractTrack 同理：

**改造前（旧逻辑）：**
- `_depth_to_y(depth)` 用 `self.height()`（固定像素高度）计算
- `paintEvent` 直接用几何高度渲染

**改造后（新逻辑）：**

```python
class IntervalTrack(TrackWidget):
    def __init__(self, config, ...):
        super().__init__(...)
        self._px_per_m: float = 0.0        # 由 Coordinator 写入
        self._current_top: float = 0.0
        self._current_bottom: float = 100.0

    def set_pixel_density(self, px_per_m: float):
        self._px_per_m = px_per_m
        self.update()

    def sync_depth(self, top_m, bottom_m):
        self._current_top = top_m
        self._current_bottom = bottom_m
        self.update()

    def _depth_to_y(self, depth_m: float) -> float:
        span = self._current_bottom - self._current_top
        if span <= 0 or self._px_per_m <= 0:
            return 0.0
        return (depth_m - self._current_top) * self._px_per_m

    def paintEvent(self, event):
        # 旧逻辑完全一致，只需要把固定高度改成动态映射
        ...
```

> 原来的 `set_fixed_height(chart_height)` 以及 `_container.setFixedHeight(chart_height)` 可以完全删除，因为高度不再由父容器固定，而是由 Coordinator 在知道 viewport 高度后才分发 density。

---

## 5. 配置模型变更

`chart_engine.py` 中不再硬算 `chart_height`，该值由 `fit_to_viewport()` 在运行时推导，不存留于配置。

`ChartConfig` 模型（`config.py`）维持不变，Pydantic 兼容性完好。

新增 Pydantic 模型描述新的"成组曲线"结构体：

```python
class CurveGroupConfig(BaseModel):
    """一条成组曲线配置，对应 CompositeModule 实例"""
    label: str = ""
    curve_names: list[str] = []        # 如 ["AC", "GR"]
    width: int = 120

class ChartLayoutConfig(BaseModel):
    """描述横向列的显示顺序和分组关系"""
    columns: list[
        str | CurveGroupConfig  # str = 遗留的 track data_key
    ] = Field(default_factory=list)
```

> 旧 TrackConfig 的组织方式（`tracks: list[TrackConfig]`）在过渡期保持并存，新旧两套并行解析，以保持向后兼容。待迁移完成后废止旧格式。

---

## 6. 关键技术决策

| 问题 | 决策 | 理由 |
|-----|------|-----|
| 如何计算铺满用的 px_per_m | `viewport_height / 全局深度跨度` | 一个除法，无参数，简单可靠 |
| `pixel_ratio` 要不要保留 | 废弃，作为过渡期内 legacy 备选字段 | 已无固定像素密度的用武之地，C2 要求必须自适应 |
| 曲线缩放时是否联动非pyqtgraph 道 | 是（C4）全联动 | 任何一个模组的视野变化都要体现在所有道上 |
| 复合模块内部是并排还是上下 | 并排（横向），复合模块内部不对齐 | 与现有实现完全一致，没有歧义 |
| DEPTH 轴本身是否也需要 `set_pixel_density` | 否，它自带 pyqtgraph 处理 | DEPTH 轴不需要 density 参数，只需接收 zoom 事件 |
| resize 时为什么不需要重建 DOM | 因为 paintEvent 已经改为动态计算 | 只需要分发新的 px_per_m，现有 QWidget 树不改变 |

---

## 7. 文件变更概要

| 文件 | 操作 |
|------|------|
| `src/renderers/well_log/chart_engine.py` | 重构：提取 LayoutCoordinator，移除固定高度逻辑，增加自适应逻辑 |
| `src/renderers/well_log/tracks/interval_track.py` | 增加 `set_pixel_density` / `sync_depth` / `preferred_width`，改 `_depth_to_y` 为动态 |
| `src/renderers/well_log/tracks/text_track.py` | 同上 |
| `src/renderers/well_log/tracks/systems_tract_track.py` | 同上 |
| `src/renderers/well_log/tracks/curve_track.py` | 增加 `preferred_width`（density 已由 pyqtgraph 隐式处理） |
| `src/renderers/well_log/tracks/depth_track.py` | 增加 `preferred_width` |
| `src/renderers/well_log/tracks/base.py` | TrackWidget 基类增加 `preferred_width` 声明（protocol 用途） |
| `src/renderers/well_log/config.py` | 增加 `CurveGroupConfig`、`ChartLayoutConfig`（新旧并存，过渡后废止旧） |
| `src/renderers/well_log/modules.py` | **新增文件**：`CompositeModule`、`LayoutCoordinator` |
| `tests/test_interval_track.py` | 补充 `test_set_pixel_density_and_sync_depth` |
| `tests/test_chart_engine.py` | **新增文件**：测试 `LayoutCoordinator.fit_to_viewport` 与 resize 联动 |

---

## 8. 暂不纳入本次的设计要点

以下内容已在本文档中明确记录其接口与定位，但不作为本次改造的实现目标：

- 多井联动（需要井间同步协议，本次属 C1 范畴外）
- 用户自定义曲线分组 UI（需要配套的交互层，本设计只解决模块化结构不破坏）
- 垂向非均匀密度（如地层年代的绝对时间映射到深度，属于 C1 前置知识不足，待后期扩展）
- 导出质量超出屏幕分辨率（`export()` 目前取 `container.grab()`，高分屏下需要 `devicePixelRatio` 补偿，属非核心功能）