# 12 — Review Round 2（interaction，用户路径走查，不编译）

日期：2026-09-24 · 审查者：独立交互审查 agent（沿 docs 08 八条路径追踪信号/状态流） · A 状态：origin 仍无 A 分支/PR/worktree。

## 路径结论（修复前 → 修复后）

| 路径 | 修复前 | 修复后 |
|---|---|---|
| 1 open well | 通过 | 通过（P3 已注记 README） |
| 2 add/merge/split | 不通过（updateTrack 非 upsert 合同） | ✅ seam 固化 insert-or-replace；MockSurface 实现并加状态断言 |
| 3 reorder | 通过 | ✅ 补同位 no-op 守卫（免无谓全量 setTracks） |
| 4 zoom | **不通过（P0）** | ✅ 见下 P0 修复 |
| 5 inspect | **不通过（P0）** | ✅ 单巡检路径 + crosshair 视界裁剪 + mock NaN/越界守卫 |
| 6 change track | 有条件通过（P1） | ✅ 隐藏轨不再复活（rebuildColumn 跳过 hidden；merge 保留可见性） |
| 7 switch well | 通过（同井刷新除外） | ✅ 换井清空 selection |
| 8 close/reopen | 通过 | 通过（无需改动；析构顺序/QPointer/连接断开已核实） |

## P0 — SplitterOverlay 吞输入（真实 kernel 集成致命）

overlay 覆盖整个视口且接收鼠标：wheel/dblclick/move 全部到不了 kernel viewport，`depthRangeRequested/fitRequested/cursorMoved` 在真实集成中永不触发（Mock 测试程序化发信号，测不出）。
**修复**：`SplitterOverlay` 改为 `WA_TransparentForMouseEvents` 纯绘制；拖拽改由 `WellTrackWidget::eventFilter` 安装在 kernel viewport 上，仅消费列边界 6px 内的左键按下（`well_track_widget.cpp eventFilter/handleSplitter*`）。

## P1 — 同井刷新复活隐藏轨

`replaceSnapshot` 非结构路径对 changed 曲线轨 `rebuildColumn` → `updateTrack` 把已 `removeTrack` 的隐藏轨插回。
**修复**：`rebuildColumn` 统一跳过 `!visible`（setTrackVisible(true) 先置位再重建，路径保持）；新增回归测试 `hiddenCurveTrackStaysHiddenOnRefresh`。

## P2 修复汇总

- 双巡检路径 → 单路径：controller 连接 surface `cursorMoved`；widget 订阅 `inspectionChanged` 渲染（删除 widget 内联 `inspectAt`）。
- crosshair 越界：`yPosForDepth` 契约收紧（unknown/NaN/视窗外 → -1）；widget 增加 `y <= height()` 上界；MockSurface 对齐（NaN→-1、视窗外→-1）。
- min-span 语义澄清：docs 08 更正为"交互路径强制，编程 setDepthRange 不强制"（Python canvas parity——审阅者建议移入 applyDepthRange，被 parity 论证否决）。
- 空态标签几何不随 resize → `resizeEvent` 重定位。
- merge 落在隐藏轨时复活 → 保留首个成员轨可见性。

## P3（已修/注记）

- 状态栏补 marker 命中显示 ✅
- `moveTrack` 同位 no-op ✅
- 出厂无 kernel factory → README 已述（错误态是设计行为）📌
- interval/marker 集合用 shared_ptr 指针判等 → 性能假设记录在 docs 07/09（host 复用 set 对象即增量）📌

## 控制器信号拓扑核查（通过）

no-op 短路（1e-9）、单跳扇出 + `syncing_` 守卫无环、生命周期顺序（controller unique_ptr 成员先析构 → surface 连接自动断开；widget lambda receiver=this）、peer QPointer + prune——全部核实无 P0/P1 遗留。
