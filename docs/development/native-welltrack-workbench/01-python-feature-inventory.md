# 01 — Python Feature Inventory（现有能力逐项核对）

来源：`packages/geoviz_well_log/**`、`src/pages/well_log/**`、`tests/**`（代码为事实权威）。核对结论：✅=已实现并有代码/测试佐证；⚠️=部分/有条件；❌=不存在。

## Well log 核心

| 能力 | 状态 | 证据（文件:行） | Native 对应责任 |
|---|---|---|---|
| 多轨道 | ✅ | `qpainter_builder.py:73-180` 固定顺序构建 9 类 track | `TrackDefinition` 列表 + `TrackLayout` 顺序 |
| 多曲线（同轨） | ✅ | merge group `["AC","GR"]→"AC/GR"`、`["RT","RXO"]`（`qpainter_builder.py:25`）；组内同名重复列都渲染（:145-158） | `CurveTrackDefinition.curveBindings` 多条 |
| track ordering | ✅ | builder 固定顺序：Depth→系/统/组→岩性→相→体系域→层序→照片→曲线→Marker；UI 拖拽排序 `page.py:310,486`（内存态） | `TrackLayout.order`（可持久化增量） |
| merge/split | ⚠️ | merge：`page.py:586`；split：`page.py:631`（均只改内存 `_all_tracks`） | `mergeCurvesIntoTrack/splitCurveFromTrack` + 序列化 |
| visibility | ✅ | `set_track_visible_by_label`（`cross_well_widget.py:228`）；页面 QListWidget 勾选 | `TrackDefinition.visible` |
| per-track X range | ✅ | `CurveData.display_range:(lo,hi)`；构造清洗：`lo<=-100 或 hi>1e5 或 lo==hi` → robust P2~P98 重算（`curve_track.py:96-108`） | manual/auto `XRange` + robust 备选 |
| curve style | ⚠️ | 仅 color(hex)/line_style(SOLID/DASHED/DOTTED)；线宽硬编码 1.5px（`curve_track.py:266`）；无 fill/marker | `CurveStyle`（含线宽字段化，默认 1.5） |
| depth range | ✅ | `set_depth_range` 自动 swap+防零 span（`track_base.py:112`） | `DepthRange` + 守卫 |
| pan | ✅ | 画布左/中键拖拽（`canvas.py:278-311`）；ZoomPanHandler 钳制全范围（`interaction.py:97-134`） | kernel plot tools |
| zoom | ✅ | 滚轮光标锚定，factor 0.88/1.14（`canvas.py:368-395`）；handler 版 20% 步长+最小 span 1.0（`interaction.py:49-89`） | kernel plot tools + 最小 span 守卫 |
| inspection | ✅ | `CrosshairOverlay`（`overlay.py:13`）：横线+信息面板，按深度 bisect 插值曲线值+枚举 interval 命中（:45-100）；无 overlay 时 QToolTip 回退（`canvas.py:420-488`） | `inspectAt(depth)` → `InspectionResult` |
| labels/header | ✅ | track header：曲线 swatch+name+`min~max unit`（`curve_track.py:288-311`）；组头 32px（`canvas.py:189-201`）；自适应字号/两行/竖排/省略号（label_layout） | header 渲染（B 拥有布局，kernel 供底） |
| grid | ⚠️ | 曲线轨内容区画 display_range 刻度值（`curve_track.py:331-349`），无通用网格策略对象 | `TrackDefinition.gridPolicy` |
| export | ✅ | `export_svg/pdf/png`（`export_qpainter.py:14-47`）走 `paint_all`；复合多井导出（`cross_well_widget.py:429-511`） | 经 kernel 同一绘制路径导出 |
| SVG/PDF | ✅ | 同上（QSvgGenerator/QPrinter） | 同上 |
| sync（多画布深度同步） | ✅ | `QPainterSyncManager` blockSignals+`_is_syncing` 防回环（`painter_sync_manager.py:26-36`）+16ms QTimer 合流 | 共享深度视口 + 防回环语义 |
| 对数刻度 | ✅ | `log_scale` ctor 参数；`_LOG_SCALE_CURVES={"RT","RXO"}` 自动；下限 floor `max(lo,1e-10)`（`curve_track.py:151-168`；测试 test_curve_track_log_value_to_x.py） | `XRange.scale=Log` + 非正守卫 |
| 视图配置持久化 | ❌ | 无任何落盘（见 00-baseline） | **增量**：可序列化 `WellTrackViewConfig` |
| LOD/大曲线 | ✅ | ndarray+searchsorted 视口裁剪（`curve_track.py:170-181`）+min-max 降采样（`downsample.py`）+QPainterPath 量化缓存 | kernel LOD substrate（B 不复制） |
| 宽度调整 | ✅ | 边界 6px 命中区，钳制 [40,300]，左右轨此消彼长（`canvas.py:249-276`） | `TrackLayout.width` + splitter 语义 |

## Track 类型（9 种）

| Track | 证据 | 要点 |
|---|---|---|
| DepthTrack | `depth_track.py:12` | 深度标签轨；nice tick `1/2/5×10^k` |
| CurveTrack | `curve_track.py:82` | 见上 |
| IntervalTrack | `interval_track.py:16` | 系/统/组/层序通用区间列，pastel 循环色 |
| LithologyTrack | `lithology_track.py:18` | SVG pattern 填充 + 模糊匹配备用色 |
| FaciesTrack | `facies_track.py:15` | nested=true 时三等分宽画 phase/sub_phase/micro_phase |
| SystemsTractTrack | `systems_tract.py:29` | TST 上三角/HST 下三角/LST 矩形+竖排标签 |
| MarkerTrack | `marker_track.py:48` | **零宽全画布 overlay**，dashed 层顶线，marker 鸭子类型 `depth|reference_depth`+`label|name` |
| ImageTrack | `tracks/image_track.py:33` | CorePhotoSegment 渲染；BoreholeImageSegment 定义未渲染 |
| BaseTrack | `track_base.py:42` | 抽象基类 |

## Geological columns

| 能力 | 状态 | 证据 | 说明 |
|---|---|---|---|
| lithology patterns | ✅ | `pattern_engine.py:15`；assets 19 根目录 SVG + facies/ 17 SVG（32×32 viewBox）；`QSvgRenderer→20px tile→QBrush`，name::dpr 缓存；精确→长度降序子串匹配 | Native：PatternLibrary 加载同一批 SVG 资产 → QBrush/纹理，交 kernel 画 interval |
| facies patterns | ✅ | `get_facies_brush`（facies/ 子目录） | 同上 |
| categorical intervals | ✅ | `IntervalItem{top,bottom,name}` 统一结构；8 层级（series/system/formation/member/lithology/lithology_desc/systems_tract/sequence）在 `WellIntervals`（models.py:33） | `IntervalTrackData` 泛化 |
| tops/horizons（单井） | ✅ | MarkerTrack overlay（层顶 dashed 线+循环色）；宿主 markers 鸭子类型注入（`page.py`；测试 test_qpainter_marker_track.py） | `MarkerTrack`（结构化 `WellTop`，不用鸭子类型） |
| annotations | ⚠️ | 仅 scene 版 `AnnotationItem` 可拖拽/编辑；QPainter 管线无 | v1 不做可编辑 annotation；tops/marker 满足现状 |

## Cross-well（仅提取单井可复用 contract）

| 能力 | 状态 | 证据 | 进 Native？ |
|---|---|---|---|
| 多井同步 | ✅ | 每井一 canvas + SyncManager | **否**（连井编排；但防回环语义进共享深度视口） |
| picks | ✅ | `HorizonPick`+Command undo/redo（`picks_model.py:11,40-163`）；10px 容差命中（zoom 无关，`canvas.py:495`）；±1.5m 极值吸附（:387） | 语义参考（命中容差/吸附进交互层）；pick 编辑本体 v1 不做 |
| horizon lines | ✅ | FormationTop 横贯虚线（`canvas.py:129`） | 是（WellTop 渲染语义） |
| manual correlations | ✅ | `CorrelationLink` interval_id 字符串编码 | **否**（脆弱设计，禁止复制） |
| DTW suggestions | ✅ | `DTWEngine` Sakoe-Chiba（`dtw_engine.py:16`） | **否**（纯数值算法，连井域） |
| depth/time 双域 | ⚠️ | TWT 仅第二轴标注（`_paint_twt_axis`） | 是（`IDepthTransformService` 注入 + TWT 标注轴） |
| checkshot 联动 | ✅ | `CheckshotTable` depth↔twt 分段线性（`seismic_tie.py:14`） | 是（接口注入，不重实现） |

## 数据入口（宿主 → 包）

- Excel(.xlsx/.xls calamine)/LAS(2.0/3.0 有界采样)/WITSML-XML sidecar → pydantic `WellLogData`（QThread worker 后台加载）。
- `CurveData.depth/values` 是 `list[float]`（进 track 才 ndarray 化并排序+剔非有限）。
- 单位：仅元数据字符串（LAS 填、Excel 不填）；深度单位硬编码 "m"。
- Native：数据经 `IWellTrackDataSource` 快照注入（`shared_ptr<const>` 低拷贝），加载线程归 host。

## 明确不做（现状即无）

- TVD/TWT 重采样渲染、sample 域、单位换算服务（无消费者）。
- curve fill/marker/逐点样式 DSL、QVariantMap 配置、ECharts 路径、LocationMap、BoreholeImage 渲染、可编辑 annotation、pick undo/redo 编辑栈（连井域，后续任务）。
