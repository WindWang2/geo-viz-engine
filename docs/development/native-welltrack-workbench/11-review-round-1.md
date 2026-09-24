# 11 — Review Round 1（domain architecture，不编译）

日期：2026-09-24 · 审查者：独立审查 agent（逐文件精读 include/ + src/ + tests + CMake + docs 04/05/06） · A 状态：origin 无 A 分支/PR/worktree。

## 发现与处置

| 级别 | 问题 | 处置 |
|---|---|---|
| P0 | `view/selection.h` 丢失（umbrella/controller include 断裂；本轮开发中 Write 报成功但文件未落盘的"幻影写"现象第三例） | ✅ 重写 `SelectionState`（optional track/curve/depthRange + ==/!=）并 grep 验证落盘 |
| P0 | `StrongId` 无 `reset()`，controller 调用 | ✅ ids.h 增加 `void reset()` |
| P0 | seam 缺 `yPosForDepth` 声明（widget/mock 均 override/调用；早前 Edit 幻影丢失） | ✅ `IWellTrackSurface` 增加纯虚 `int yPosForDepth(double) const`（-1 表无效）；补契约：A 是深度↔像素映射唯一权威（K2 双向） |
| P0 | 公开 `resolveXRange` 声明无定义（实现误放私有 `docbuild::effectiveRange`） | ✅ 公开定义落在 document_builder.cpp，`effectiveRange` 降为指针版薄转发（测试仍用） |
| P1 | `replaceSnapshot` 对 interval/marker/image map 用 `.at()`：同 size 异 key 集抛 `std::out_of_range`（GUI 崩溃） | ✅ 全部改 `find()` + structural 标记 |
| P1 | 测试 `#include "document_builder.h"` 与 `../src` 路径不符（2/3 测试编不过） | ✅ tests/CMakeLists 增 `../src/view` include 目录 |
| P2 | 隐藏 Marker overlay 被 `rebuildAllColumns` 复活（跳过条件漏了 Marker） | ✅ 统一 `if (!entry.visible) continue;` |
| P2 | `updateOverlaysGeometry` 三目运算符触发整个 config 深拷贝（每次 resize/深度变化） | ✅ 重构为早退 + 直接 const 引用 |
| P2 | 数据源/变换服务生命周期文档与实现相悖（docs 说 QPointer 弱持有，实现 shared_ptr 强持有；`depthTransform_` 死成员） | ✅ 删死成员；docs 06 改为如实描述（source=shared_ptr 强持有；transform=host 裸指针，须先置空再释放；`data_source.h` 写明 lifetime contract） |
| P2 | pattern 资产解析每 row 2 次 stat、目录解析每次 3 候选探测 | ✅ `patternAssetPath` 进程级 memoize（GUI 线程单线程合同）；`defaultPatternAssetDir` 一次解析缓存 |
| P2 | widget 错误分支未接管 surface（所有权泄漏路径） | ✅ else 分支 `surface_->setParent(this)` |
| P2 | include 卫生：curve.h `std::shared_ptr` 缺 `<memory>`；robust_range.cpp `std::optional` 缺头 | ✅ 补齐 |
| P3 | intervalRows nested 死分支（assembleColumn 自行三列循环） | ✅ 删除 nested 参数 |
| P3 | GR 预设 `max(0,min(p1,0))` 恒 0 | ✅ 写 `0.0` + parity 注释 |
| P3 | CurveBuffer 抛异常违反"domain 用 optional"约定 | ✅ 头文件注明唯一 throwing 路径 |
| P3 | `computeFullRange` 忽略 imageSets | ✅ 纳入 segments |
| P3 | `fromJson` 越界宽度整份配置被拒 | ✅ fromJson 内 clamp [40,300]（validate 仍拒绝显式非法值，双保险） |
| P3 | facies `nested = columns.size()>=2` 不校验键名 | ✅ 显式检查 phase/sub_phase/micro_phase 键 |
| P3 | controller unique_ptr + QObject parent 双所有权脆弱 | ✅ 去 parent，注释说明析构顺序（unique_ptr 成员先于 surface 子对象析构） |
| P3 | docs 05 说 example "需 A 否则跳过 target" 与实现（恒构建）不符 | ✅ 改文档（实际行为更优：无 A 跑 error-state 冒烟） |
| P3 | `handleCursorMoved` 与 widget 内联巡检双路径 | 📌 保留（controller 信号供 host 直连；widget 路径供 overlay），Round 3 复查是否有分叉风险 |

## 通过项（审查确认）

- 声明/定义对账（修复后全绿）；Q_OBJECT 头已列入 CMake sources，AUTOMOC 覆盖。
- 分层 grep：domain 零 Qt；config 仅 QtCore；view 零 QGIS 头；无 geo-viz 私有头引用。
- CMake 门控逐字符合 docs 04（find_package QUIET → option → FATAL guard），无 fallback 渲染器。
- 序列化边界：配置无大数组；schemaVersion 严格；fromJson 缺字段走默认、坏字段 nullopt。
- 零拷贝：`shared_ptr<const CurveBuffer>` 直传 seam，测试断言指针同一。
- A/B seam：`Surface*` 值类型仅 QColor/QString/POD。

## 结论

分层满足 docs 05 声称的架构。P0×4 + P1×2 + P2×6 已全部修复（本轮内），P3 清理 8 项、保留 1 项待 Round 3。进入 Round 2（交互走查）。

> 过程注记：本轮发生 3 次"工具报告写入成功但文件未落盘"事件（selection.h、curve_style.h/view_config.h 首写、render_surface.h 的 yPosForDepth 编辑）。已建立"每次关键写后 grep 验证"纪律。
