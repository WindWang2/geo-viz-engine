# 10 — Test Plan

框架：QtTest（domain 测试无 GUI；view 测试 `QT_QPA_PLATFORM=offscreen`）。CTest 注册。fixture 内联合成（对齐 Python 包内做法）；数值期望取自 03-behavior-oracle 各行对应的 Python 测试断言。

## A. Domain（Qt-free）

| 测试 | 覆盖（oracle 行） |
|---|---|
| `t_depth` | swap/零 span/contains/isValid（N1） |
| `t_nice_interval` | 1/2/5×10^k、子单位 span、>5000 span（对齐 test_nice_interval.py） |
| `t_curve_buffer` | valueAt：采样点/点间插值/洞 NaN/未排序拒收/空曲线（C7） |
| `t_robust_range` | GR/RHOB/NPHI 预设 + P2~P98 通用 + 空/全 NaN + 倒置预设回退（C1，对齐 test_robust_scale_units.py #113） |
| `t_xrange_log` | 非正 clip 1e-10、manual/auto（C2） |
| `t_intervals` | 排序副本、重叠取最长、gap、边界 top≤d<bottom（G6） |
| `t_pattern_catalog` | 精确/长度降序子串/未命中 fallback 色（G2，对齐 PatternEngine._fuzzy_lookup） |
| `t_defaults` | merge groups/log 曲线/CURVE_META 色/label 映射（C5） |
| `t_document_builder` | 默认轨道顺序/宽度/空段跳过/markers overlay/重复 mnemonic 全渲染（#584） |

## B. Config

| 测试 | 覆盖 |
|---|---|
| `t_view_config_roundtrip` | 全字段 JSON roundtrip；schemaVersion 拒收未知主版本 |
| `t_view_config_invalid` | 重复 TrackId、宽度钳制、X range 倒置、引用不存在曲线（L1） |

## C. Controller/View（MockSurface）

| 测试 | 覆盖（oracle） |
|---|---|
| `t_controller_depth` | no-op 守卫不发信号；钳制；span≥1.0（N2/N3/N5） |
| `t_controller_zoom_anchor` | zoomAt 锚点深度不变（N3 数值） |
| `t_controller_tracks` | add/remove/move/visible/width 钳 40..300/merge/split（I4/I5/C5） |
| `t_controller_snapshot` | replaceSnapshot revision diff → 断言 seam 调用最小集（L2 六类粒度） |
| `t_controller_stale_revision` | 旧 revision 拒收（L3） |
| `t_inspection` | inspectAt：曲线插值+interval 命中+top 容差（I1/I2/G6） |
| `t_snap` | 极值吸附 ±1.5m 窗口 max/min（I3） |
| `t_sync_group` | 双 controller 同步不回震（N7） |
| `t_widget_lifecycle` | 切井/重开/销毁后无 UAF（offscreen + QSAN 不适用则靠空指针断言 + 崩溃即败）（L4） |
| `t_widget_states` | 空态/错误态/状态栏读出 |

## D. Large data（09 的验收）

`t_large_data`：1e5×8 曲线加载+巡检计时记录；200 轨/5e3 区间命中；20 次换井 RSS 粗检；零拷贝指针断言。

## E. GUI integration（需 A；A 缺席时 SKIP 且明示）

`t_gui_smoke`（或 example 可执行）：representative well（曲线+lithology+facies nested+tops）→ show → zoom/pan → crosshair → hide/reorder → close。判据：无崩溃、状态读出非空。
`host_link_smoke`：最小 main 链接两 target，create/destroy 一轮。

## 与 Python 的 oracle 对照（任务 §15）

- 不做逐像素比对。
- 结构化对照点：轨道顺序（builder 规则）、X range 清洗数值、log floor、插值数值、pattern 解析命中、nice interval 值——期望值均来自同名 Python 测试断言（03 表已标注文件）。
- Python 包保持原样（behavior oracle / fixture 来源），不删除不修改。
