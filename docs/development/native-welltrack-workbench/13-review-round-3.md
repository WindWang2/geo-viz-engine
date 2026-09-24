# 13 — Review Round 3（implementation adversarial，逐行，不编译）

日期：2026-09-24 · 审查者：独立对抗审查 agent（全量 .h/.cpp + 与 Python 源逐条数值对照） · A 状态：origin 仍无 A 分支/PR/worktree。

## 修复的发现

| 级别 | 问题 | 处置 |
|---|---|---|
| P1 | `t_domain generalQuantile` 期望值算错（正确值 numpy 实算 (-28.0, 1027.0)；测试从未跑过所以未爆） | ✅ 改为精确 QCOMPARE |
| P1 | `IntervalColumn::finalize` 不过滤 NaN top/bottom：NaN top 破坏 strict weak ordering（UB）；NaN bottom 毒化 maxLength_ 使整列命中失效 | ✅ 过滤非有限与倒置区间 |
| P2 | robust null 掩码容差不完全等价 np.isclose（缺 rtol 分量） | ✅ `1e-3 + 1e-5*\|nv\|` |
| P2 | resolveXRange 缺 Python 的 `isclose(lo,hi)` 近等距拒绝 | ✅ 补 isClose（1e-9 rel）；倒置 manual 的拒绝保留（有意的安全分歧，注释注明） |
| P2 | computeFullRange/images 非有限值使 fullRange 塌缩 {0,1} 整图空白 | ✅ images.finalize 过滤；intervals 已由 P1 覆盖；curves/markers 构造期已过滤 |
| P2 | sync peer 扇出中 range-for 迭代 `syncPeers_`：嵌套槽改 peer 列表 → 迭代器失效 UB | ✅ 迭代副本 |
| P2 | 单样本曲线 readout 语义与 np.interp 分歧（返回 NaN vs 平读） | ✅ 单样本平读（np.interp 语义），头文件注明 |
| P3 | curve.cpp 死分支 `depth==depths_[hi]` | ✅ 重写边界处理 |
| P3 | patternAssetPath cache 键与目录解析的隐式耦合 | ✅ 注释锁定（dir 为进程级 static） |
| P3 | Lithology/Facies 分支重复代码；SystemsTract 双次 style 调用 | ✅ 合并 |
| P3 | `usedRobust` 未使用告警 | ✅ `[[maybe_unused]]` |
| P3 | split 出的轨强制可见 vs merge 保留源可见性 | ✅ 注释声明为有意分歧（用户显式操作） |
| P3 | widget `surface_` 裸指针（host 早删 surface → 悬垂） | ✅ 改 QPointer |
| P3 | view_config rgba double→uint32 越界 UB；lineWidth 无校验 | ✅ clamp 后 cast；lineWidth 非法回退 1.5 |
| P3 | depthTicks 累加漂移 | ✅ k*step 整数步进 |
| P3 | InspectionResult::isValid 以 depthUnit 非空为门槛（host 清空单位 → 巡检全灭） | ✅ 改 `isfinite(depth)` |
| P3 | 测试：zoomAnchor QCOMPARE 浮点直比；snap 断言窗口内恒真；容差注释错 | ✅ qFuzzyCompare / 精确期望值 / 注释修正 |

## 核查通过（专项）

- **hitInterval 反向扫描 break 条件正确**：top 降序使 `depth-top` 单调增，`> maxLength` 后不可能再有重叠（含更早更长区间）；NaN depth 安全退化。
- 钳制组合数学（span≥fullspan、先 bottom 后 top 平移、无效 fullRange 兜底、NaN anchor 吸收）验证无误。
- 生命周期：controller 先析构 → surface 连接自动断开；queued 事件安全；A↔B 互持 QPointer 收敛。
- **无重复绘图逻辑**：QPainter/paintEvent 仅在产品 overlays 与测试 MockSurface；B 无任何 generic canvas/axis-painter/zoom-paint/curve-painter 残留（DoD #5 证据）。
- 拷贝量级评估：rebuildAllColumns 的列向量构造仅发生在结构变更/加载（zoom 只重建深度轴列），SSO 字符串为主，可接受；viewConfig() 拷贝无害。

## 记录在案（不修）

- `roundTo` half-away-from-zero vs Python banker's rounding：半值边界小概率分叉（显示范围取整级别）。
- same-well 刷新时深度轴列先按旧 viewRange 组装再重建（瞬态浪费，终态正确）。
- no-op 判定先于钳制：pre-clamp 差 ≥1e-9 但钳后同值的请求多发一次信号（冗余但无害）。
- `displayLabel`（_LABEL_TO_DISPLAY parity）暂无内部调用方，保留为公开 parity helper。
- interval/marker/image 集合按 shared_ptr 指针判等：host 每次新建 set 对象会退化为全量 structural 重建（性能假设，docs 07 已述）。
