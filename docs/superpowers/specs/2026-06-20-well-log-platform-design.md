---
name: well-log-platform-redesign
description: 测井相应用重构 — 从单井列表到平面地图 + 双栏交互
owner: WANG老师 / Kevin
created: 2026-06-20
status: approved
---

# 测井相应用平台重构设计方案

**Spec 版本：v1.0 | 状态：已批准**

---

## 1. Overview

将现有的 geo-viz-engine Phase 1 从"先选井→再看沉积相图"重构为一张可操作的**测井平面分布地图**，配以右滑详情面板，形成标准的 GIS 分析工作流。同时提供平行表格页面供数据检索用途。

**核心目标：**
- 地图页为默认首页，展示所有井的空间分布
- 点击任意井点 → 右滑详情面板，内嵌沉积相图
- 支持 inline 编辑和 hover 数据提示，强化交互
- 表格页与地图页平行，用户自由切换

---

## 2. Pages & Routes

```
/                  → MapHomePage（首页，MapLibre 地图 + 可折叠详情面板）
/table             → WellTablePage（全量井列表，支持搜索/筛选/进入详情）
/well/:id/detail   → 通过地图页或表格页触发的详情面板（非独立路由）
                       表现为覆盖在首页之上的 Slide-over Panel
```

**退化/移除：**
- 原 `/well-log` 路由 → 去除（功能迁移至上文两页）
- `WellLogPage.tsx` → 逐步废弃，内容迁移至 `MapHomePage` 内

---

## 3. Layout Structure

### 3.1 首页（MapHomePage）

```
┌──────────────────────────────────────────────────────────┐
│  ┌─────────────────────────────────────────────────────┐ │
│  │                                                     │ │
│  │              MAPLIBRE GL 地图                      │ │
│  │        （经纬度投点，圆点标记井位）                  │ │
│  │                                                     │ │
│  │                              ┌──────────────────┐   │ │
│  │                              │ ← 返回 / ✕ 关闭 │   │ │
│  │                              ├──────────────────┤   │ │
│  │                              │ 井名 / 元信息    │   │ │
│  │                              ├──────────────────┤   │ │
│  │                              │ Geological       │   │ │
│  │                              │ ProfileViewer    │   │ │
│  │                              │（可编辑 + Hover）│   │ │
│  │                              └──────────────────┘   │ │
│  └─────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
          ↑ 右上角 Tab 条：[🗺️ 地图] [📋 表格]
```

**三种状态：**
- **状态 A**：Panel 未打开 → 地图全屏，左上角仅有 Logo
- **状态 B**：Panel 半开（<60%宽时保持最小宽度）→ 最多占用 55% 屏幕宽度
- **状态 C**：地图透明背景，Panel 全宽 → 点击地图空白处可关闭

### 3.2 底部导航条（Bottom / Right Tab Bar）

替代原有 Sidebar，仅保留两入口：
```
[🗺️ 地图]   [📋 表格]
```
活跃 tab 有高亮，布局位于右上角或底部水平标签栏。

---

## 4. Map Component

### 4.1 技术栈

| 包 | 用途 |
|----|------|
| `maplibre-gl` | 矢量/栅格底图渲染，开源无商业限制 |
| `react-maplibre`（或原生封装） | React 绑定 |
| `ol` / turf.js | （未来）坐标转换，如需要时引入 |

### 4.2 底图

- 来源：**OpenStreetMap** 默认免费瓦片
- 坐标系：**WGS84（EPSG:4326）经纬度**，无需投影转换
- 中心点：重庆东南部示例 `[107.0, 29.0]`，zoom=7 可视全区域

### 4.3 井点渲染

- 每个井用 `CircleMarker` 表达，颜色反映主岩性（如 sandstone=金黄、mudstone=灰）
- 尺寸固定 8-10px，避免大小竞争干扰
- 标注文字：显示井名（小字号，偏移 5px 上方）

### 4.4 Click Behavior

```
点击井点
  → map.flyTo(coords) 居中
  → 打开右侧 DetailPanel
  → 同时 /api/data/well/:id 拉取完整曲线数据
```

### 4.5 Marker Clustering（远期）

当前阶段不实现，待井数超过 50 再引入 `supercluster` 做聚合。

---

## 5. DetailPanel（详情面板）

### 5.1 开启/关闭

- **打开**：点击地图 Marker，或表格页"查看"按钮
- **关闭**：
  - 点击右上角「✕」
  - 点击左上角 breadcrumb「← 返回地图」（图标 + 文案双保险）
  - 按 `ESC`
  - 点击地图非重叠区域（AOI 外）

### 5.2 Panel 内布局

```
┌─────────────────────────────────┐
│ [← 返回]  老龙1井    [✕ 关闭] │  ← Header，始终可见
├─────────────────────────────────┤
│ 元信息：深度 2510-2620m | 4曲线  │  ← 简介行
├─────────────────────────────────┤
│                                 │
│   GeologicalProfileViewer        │  ← 主内容区（可编辑+Hover）
│                                 │
└─────────────────────────────────┘
```

### 5.3 宽度

- 最大 55vw，最小 380px
- 可拖拽左边距调整宽度（resizable split pane）
- 动画过渡：300ms ease-out slide-in/out

---

## 6. Inline Editing（点击可改名字）

### 6.1 实现原理

`GeologicalProfileViewer` 内，每个可编辑文字块的结构：

```
<span
  contentEditable
  onBlur={(e) => updateField(block.id, e.target.innerText)}
  title="点击修改"
>
  {block.name}
</span>
```

### 6.2 适用范围

| 区块 | 可编辑字段 |
|------|-----------|
| 地层（systems/series/formations/members） | `name` |
| 岩性层（lithologies） | `lithology` 英文类型、`description` 中文描述 |
| 取心段（cored_intervals） | `name`、`color` |
| 沉积相（micro/sub/facies） | `name` |
| 层序/体系域（sequences/system_tracts） | `name` |

### 6.3 约束

- 修改后端本地 mock 状态（Zustand 或组件 state），**不发 API**
- `color` 使用预设色板 picker（有限选项，不开放任意 hex 输入避免脏数据）
- 撤销支持：Ctrl+Z（通过 state snapshot stack 实现）

---

## 7. Hover Tooltip

### 7.1 行为

- 鼠标悬停在任意区间块上 → 出现浮层，显示：
  - 名称、顶底深度（top/bottom）
  - 原始曲线值范围（如 GR: 30-85 API）
  - 颜色值（hex）
  - 岩性描述文本

### 7.2 实现

使用 Tippy.js 或 Radix UI Popover，绑定于 `IntervalBlock` 渲染单元。tooltip 跟随鼠标轻微偏移，不遮挡底层内容。

### 7.3 示例内容

```
┌──────────────────────────┐
│ 龙王庙组                │
│ 深度：2515.0 - 2517.0 m │
│ 曲线：GR 30-82 API      │
│ 颜色：#E8D5B7           │
└──────────────────────────┘
```

---

## 8. Backend Changes

### 8.1 数据模型新增

**Python `well_log.py`** — `WellMeta` / `WellMetadata` 新增：

```python
longitude: Optional[float] = None  # 经度，WGS84
latitude: Optional[float] = None   # 纬度，WGS84
```

> 注：`location: Optional[Tuple[float, float]]` 与 `longitude/latitude` 并存，前者保留备用。

**TypeScript `types.ts`**：

```typescript
export interface WellMetadata {
  // ...existing...
  longitude?: number | null;
  latitude?: number | null;
}
```

### 8.2 data_generator.py 更新

`generate_well_log()` 中，每口井给予随机经纬度（模拟川东地区）：

```python
import random
lng = round(random.uniform(106.0, 108.5), 6)   # 东经 106-108.5°
lat = round(random.uniform(28.0,  30.5), 6)   # 北纬 28-30.5°
```

### 8.3 API 端点

无需新增，现有 endpoint 已够用：
- `GET /api/data/list` → 返回 metadata 含坐标（已包含）
- `GET /api/data/well/:id` → 返回完整 WellLogData

> 注：如果表格页需要导出 Excel，另议。

---

## 9. WellTablePage（平行表格页）

### 9.1 功能

- 列：井号、井名、深度范围、曲线数、坐标、操作
- 支持模糊搜索（井号/井名）
- 列排序（点击表头）
- 每行"查看详情"按钮 → 触发打开地图页 DetailPanel

### 9.2 交互

点击"查看详情"：
1. 自动切到 `/` 地图页
2. flyTo 该井坐标
3. 打开 DetailPanel

---

## 10. Navigation / Routing

### 10.1 路由表

```tsx
[
  { path: '/',              component: MapHomePage },
  { path: '/table',         component: WellTablePage },
]
// /well/* 相关路由暂时废除，功能内嵌于首页 panel
```

### 10.2 全局状态（Zustand）

扩展 `useWellStore`：

```typescript
{
  // 现有...
  selectedWellId: string | null;
  panelOpen: boolean;

  selectWell: (id: string) => void;  // 选井 + 开panel
  closePanel: () => void;             // 关panel
  togglePanel: () => void;
}
```

---

## 11. Implementation Phases

> 不求一步到位，分阶段上线可控。

### Phase 1（MVP）— 本次实现
- [x] Spec 本文档完成 ✓
- [x] 安装 maplibre-gl 依赖
- [x] `MapHomePage` 基本地图 + 井点打点（mock 坐标）
- [x] 点击 Marker 打开 DetailPanel（基本版，无编辑/Hover）
- [x] `DetailPanel` 嵌入 GeologicalProfileViewer（已有组件复用）
- [x] ESC / 点击遮罩关闭 Panel
- [x] Bottom Tab Bar 导航（地图/表格）
- [x] 后端 mock 坐标注入
- [x] 36 Python 测试仍然全部通过

### Phase 2（交互增强）
- [ ] Inline editable text（HOC 封装）
- [ ] Hover tooltip on all blocks
- [ ] Ctrl+Z undo local changes

### Phase 3（表格 + 高级）
- [ ] `/table` 页面（搜索 + 排序）
- [ ] 跨页"查看详情"触发地图页
- [ ] Resizable panel（拖拽分割线）
- [ ] Cluster 聚合（>50 井时启用）

---

## 12. Dependencies

```
maplibre-gl          ^4.x     # BSD-2, 零商业风险
react-maplibre       ^4.x     # MIT
@tiptap/react        ^2.x     # 可选，用于 inline edit，如果 contentEditable 够用就不装
tippy.js             ^6.x     # tooltip，仅需此一座（轻量）
tailwindcss           3.x      # 已有
zustand               4.x      # 已有
react-router-dom     ^6        # 已有
```

> `maplibre-gl` 安装后在 vite.config 中无需特殊配置，仅需 npm 即可使用瓦片。

---

## 13. Open Questions

1. ~~坐标系统~~ → **决议**：WGS84 经纬度，mock 坐标在 [106-108.5°E, 28-30.5°N]，对接真实时后端输出同样标准
2. ~~底图选择~~ → **决议**：OSM 免费瓦片，开发阶段足够，正式可换成高德/Google/MapABC
3. inline edit 的修改是否持久化？（不发 API 则刷新丢失）→ **当前结论**：MVP 阶段不持久化，仅内存 state，Phase 3 再论

---

## 14. Acceptance Criteria

- [ ] 首页地图加载后显示 N 个井点（N 由 generate 接口控制，默认 10）
- [ ] 点击任意井点，右侧滑入 Details Panel，显示 GeologicalProfileViewer
- [ ] Panel 始终有可⻅的「← 返回」「✕」关闭控件（共三处保证可达）
- [ ] 键盘 ESC 可关闭 Panel
- [ ] 切换到 Table 页面能正常显示井列表
- [ ] Table 点击"查看"→ 跳转地图并打开同一 Panel
- [ ] 所有 Phase 1 功能无需刷新页面
- [ ] Python 后端测试 `pytest -q` 维持 41/41 passed
- [ ] 前端 build 无 TypeScript 错误

**Actual merged:** PR #2 (`88f344d`) - 2026-04-15
**Test status:** pytest 36/36 ✅ | tsc --noEmit clean ✅