# 08 — Interaction Model（交互模型与事件流）

## 总则

- 输入事件（wheel/mouse）由 surface（A）持有 → 以**视口意图信号**上报 → controller 应用产品规则 → 回写 surface。B 无事件过滤器网络（对照 Python `_TrackMouseFilter`+WellLogView 转发的双路径债）。
- 一次用户操作 = 一条**单向链**，禁止 signal 环：唯一允许的环点（多 view 深度同步）用 `setDepthRange` 的 1e-9 no-op 短路 + syncing 守卫（N2/N7）。

## 用户路径走查（Round 2 的脚本）

```
open well → add curves → reorder → zoom → inspect → change track → switch well → close/reopen
```

各步的数据/信号流：

### 1. open well
host(GUI thread) `factory.create(source,parent)` → controller `loadSource`：
读 snapshot → `DocumentBuilder::buildDefault(snapshot)`（规则=Python builder：Depth→系/统/组→岩性→相→体系域→层序→照片→曲线(merge groups)→Marker overlay；宽度 60/50/50/50/80/80/60/50/180/140）→ `surface->setTracks(columns)` + `setFullDepthRange` + `setDepthRange(full)` → `viewConfigChanged`。
空 snapshot → widget 空态（"无数据"占位，不建 track）。

### 2. add curves
host `addCurveTrack({curveIds})`（或 merge 现有）→ TrackStructural 变更 → `surface->updateTrack` 或 `setTracks`（顺序变化时）→ config 变更信号。曲线不存在的 id → 返回 false，不改文档。

### 3. reorder
`moveTrack(id,newIndex)` → 仅 `TrackLayout` 顺序变化 → `setTracks`（列序）→ config 变更。数据不动、buffer 指针复用。

### 4. zoom（wheel）
surface 捕获 wheel → 光标 y→depth（A 算）→ `depthRangeRequested(newTop,newBottom)` → controller `setDepthRange`：swap/零 span 守卫→全范围钳制→span≥1.0→no-op 检测（<1e-9 跳过）→ `surface->setDepthRange` + `depthRangeChanged`。同步组内其它 controller 收到信号 → 各自 `setDepthRange`（守卫阻断回震）。

### 5. inspect（mouse move）
surface `cursorDepthChanged(depth, trackId)` → widget 刷新 crosshair overlay（B 产品组件，画横线+面板）→ `inspectAt(depth)`：
- 曲线：视口内每 CurveTrack × 每可见 curve → `CurveBuffer::valueAt`（bisect 插值；洞→NaN 标"无值"）。
- interval：每可见区间列 → 命中 `top≤d<bottom` 的 item（重叠取最长匹配者，与 label 绘制一致）。
- marker：容差 = `10px × depthPerPixel`（I2；zoom 无关的屏幕容差）。
- 输出 `InspectionResult` → 状态栏读出 + `inspectionChanged` 信号（host 可接管面板）。

### 6. change track（width/visibility/style）
- width：B 的 splitter overlay（列边界 6px 命中区，B 拥有布局）拖拽 → `setTrackWidth` 钳 40..300，左右轨此消彼长由 layout 重分配（语义同 canvas.py:249-276）→ `updateTrack`。
- visibility：`setTrackVisible` → `updateTrack`（列隐藏但不删数据）。
- style：`setCurveStyle` → StyleOnly 粒度 → `updateTrack` 单列。

### 7. switch well
host 新 snapshot（不同 well id）→ controller 判定 FullDocument → 清 track 定义（保 view config 模板字段可选回放）→ 重建 → `setTracks`。旧 surface 列与缓冲失效由 A 的 setTracks 语义承担；B 不持有裸指针跨此边界（review 检查点 R-17）。
同井 refresh → `replaceSnapshot` 走 revision diff（CurveData 粒度）。

### 8. close/reopen
widget `deleteLater`（Qt ownership）→ controller/surface 连带销毁。host 保存 `viewConfig()` 后即可丢弃。重开 = 路径 1 + `applyViewConfig`。queued 事件在析构后到达：controller 所有对外信号发射前检查 `widget` 存活（`QPointer`），surface 是 QObject 子对象，连接随销毁断开（review 检查点 R-17/R-18）。

## 交互能力清单（实现范围 = 现状真实存在项）

| 能力 | 实现 | 依据 |
|---|---|---|
| 竖向 pan / wheel zoom / 光标锚定 / dblclick fit | A 工具 + B 规则 | N3/N4/N5 |
| set depth range / fit / reset X range | controller API | N1 |
| 多 view 深度同步 | `syncWith` 组 | N7 |
| crosshair + 深度 + 最近曲线值 + 名称/单位 | `inspectAt` | C7/I1 |
| interval/lithology/facies 命中 | `inspectAt` | G6 |
| horizon 命中（10px 容差） | `inspectAt` | I2 |
| track 选择/曲线选择 | `SelectionState`（点击 header/曲线命中） | I1 |
| 宽度拖拽 / 显隐 / 排序 | controller + splitter overlay | I4/I5 |
| merge/split | controller API | C5 |
| 吸附（极值 ±1.5m 窗口） | `snapToExtreme`（供 host 拾取复用） | I3 |

**明确不做**：曲线在轨道间拖拽移动（现状仅 merge/split API 化）、pick 编辑/undo、annotation 编辑、区间拖拽编辑（scene 版专属）。
