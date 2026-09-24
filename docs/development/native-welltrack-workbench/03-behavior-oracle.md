# 03 — Behavior Oracle（Python 行为 → Native 责任 → kernel 原语 → 测试/oracle）

每行是一个**行为合同**：Native 必须复现的语义（数值/几何/状态），及其验证方式。测试不追求逐像素一致（任务 §15），验证数据/几何/行为。

## 深度与导航

| # | Python 行为（证据） | Native 责任 | kernel 原语 | 测试/oracle |
|---|---|---|---|---|
| N1 | `set_depth_range` 自动 swap + 防零 span（`track_base.py:112`） | `DepthRange::normalized()` | shared depth viewport | domain 单测：swap/zero-span |
| N2 | no-op 守卫：变化 < 1e-9 不发信号不脏缓存（`canvas.py:122-132`） | controller `setDepthRange` 短路 | — | 单测：重复设置不发 `depthRangeChanged` |
| N3 | 滚轮缩放锚定光标深度；factor 0.88/1.14；最小 span 1.0；钳制全范围（`canvas.py:368-395`，`interaction.py:49-89`） | `zoomAt(anchorDepth,factor)` | plot tools | 单测：锚点深度 zoom 前后不变；span 下限 |
| N4 | 双击 fit 全范围（`interaction.py:91-95`） | `fitDepth()` | — | 状态断言 |
| N5 | 拖拽 pan 钳制 `_full_top/_full_bottom` | `panDepth(dy)` | plot tools | 边界钳制单测 |
| N6 | 滚动条映射深度窗口到 0..100000 整数域（`well_log_view.py:136-179`）+ `_scrollbar_syncing` 防回环 | widget 内 scrollbar 桥（B 拥有） | — | 回环防护单测（设 range 不再触发 valueChanged 重入） |
| N7 | 跨画布同步：blockSignals+`_is_syncing` 防环 + 16ms 合流 | `syncGroup`（多个 controller 共享深度） | shared depth viewport | 单测：A 改 B 跟随、B 不回震 A |

## 曲线显示

| # | Python 行为 | Native 责任 | kernel 原语 | 测试/oracle |
|---|---|---|---|---|
| C1 | display_range 清洗：`lo<=-100 或 hi>1e5 或 lo==hi` → robust P2~P98（`curve_track.py:96-108`） | `resolveXRange()`：manual 合法则直用，否则 robust | curve x-range | 单测对照 `compute_robust_display_range` 数值（GR/RHOB/NPHI 预设） |
| C2 | log 刻度：RT/RXO 自动；非正值不入 log10（下限 floor 1e-10）（`curve_track.py:151-168`） | `XRange{scale=Log}` + 值→x 守卫 | log 映射 | 单测：0/负值 clip 到 floor |
| C3 | 视口裁剪 ±5% margin + searchsorted（`curve_track.py:170-181`） | kernel 责任 | LOD substrate | mock surface 断言传入 span 正确 |
| C4 | min-max 降采样保极值（`downsample.py:33-118`） | kernel 责任 | LOD | 不测（A 域）；B 测 span 传递 |
| C5 | merge group AC+GR / RT+RXO；组内同名重复列都渲染 | `CurveStyleDefaults::mergeGroup(name)` + binding 保留重复列 | 多曲线 track | 配置单测 |
| C6 | header：swatch+name+`min~max unit` | header 渲染（B） | — | inspection/标题单测用字符串组装函数 |
| C7 | 曲线值按深度 bisect 线性插值 readout（`overlay.py:45-100`） | `interpolateAt(depth)` | hit testing | 数值单测：采样点间插值、gap→NaN |

## 区间/地质

| # | Python 行为 | Native 责任 | kernel 原语 | 测试/oracle |
|---|---|---|---|---|
| G1 | interval rect=top/bottom→Y 线性映射 | kernel 责任 | generic interval | mock 断言矩形参数 |
| G2 | lithology pattern：精确→长度降序子串匹配 → 资产 id；未命中 fallback 色（`pattern_engine.py:82-94`） | `PatternLibrary::resolveKey(name)` | brush/style 引用 | 单测：精确/子串/未命中三路径 |
| G3 | facies nested 三等分宽三列 | `FaciesTrackDefinition.nested` | interval×3 列 | 配置单测 |
| G4 | marker 全画布 overlay：dashed 线+循环色+label | marker overlay（经 kernel marker 原语） | marker | 单测：WellTop 列表→层线集 |
| G5 | 体系域：TST 上三角/HST 下三角/LST 矩形 | `IntervalStyle.shape` | generic interval/band | style 映射单测 |
| G6 | interval 命中测试：depth∈[top,bottom] 枚举 | `hitIntervals(depth)` | hit testing | 单测：边界/重叠/间隙 |

## 交互与巡检

| # | Python 行为 | Native 责任 | kernel 原语 | 测试/oracle |
|---|---|---|---|---|
| I1 | crosshair 横线+面板：深度+各曲线插值+interval 命中 | `inspectAt(depth)` → `InspectionResult`（B 组装，kernel 供 hit） | hit testing | 结构化结果单测 |
| I2 | 10px 屏幕容差命中（zoom 无关，px→depth 换算）（`canvas.py:495`） | marker/顶层命中容差 | hit testing | 容差换算单测 |
| I3 | ±1.5m 窗口极值吸附（max/min）（`canvas.py:387`） | `snapToExtreme(depth,window)` | — | 数值单测：峰/谷吸附 |
| I4 | track 宽度 [40,300] 钳制、边界 6px 命中、左右此消彼长 | `TrackLayout` splitter 语义 | — | 布局单测 |
| I5 | track 显隐（by label）不重建数据 | `setVisible` 只动 view/config | — | 状态单测 |
| I6 | label policy：字号自适应/两行/竖排/省略（label_layout） | kernel/B header 渲染细节 | — | 弱化：不做像素断言，仅策略函数单测 |

## 配置/生命周期（增量能力）

| # | 行为 | Native 责任 | 测试 |
|---|---|---|---|
| L1 | （现状无） | `WellTrackViewConfig` 序列化/反序列化 roundtrip；版本字段 | roundtrip 单测 |
| L2 | 切换井=删旧建新（`page.py:389`） | `loadSnapshot(rev)` 复用 widget，区分 6 级更新（style-only/view-only/one-curve/one-track/transform/whole-doc） | 更新粒度单测（断言 dirty 范围） |
| L3 | 迟到 worker 结果篡改当前井（app 坑） | revision/generation id 门控：旧 revision 结果丢弃 | 单测 |
| L4 | widget 销毁后回调不得触达 | Qt 父子 ownership + `QPointer`/guard；signal 断连 | 生命周期 review + smoke |

## Fixture 复用（任务 §15）

- Python 包内测试全部内联合成数据——**无文件 fixture 可搬**；顶层 `samples/demo.xls`、`samples/*.geojson` 可作 host adapter 冒烟输入。
- C++ 测试内联合成等价数据（CurveData 形状），对照项：N1-N7/C1/C2/C7/G2/G6/I2/I3 的数值断言直接取 Python 测试中同类断言的期望值（见各测试文件）。
- 不做逐像素 golden（Python 侧 well-log 也无 golden PNG）。
