# 02 — Domain Model Inventory（既有数据模型盘点与取舍）

来源：`geoviz_well_log/models.py`（81 行，全部 pydantic 模型）、`geoviz_cross_well/{tops_model,picks_model,seismic_tie}.py`、`geoviz_well_tie/{calibration,sonic_units}.py`、`src/data/models.py`。

## 既有模型 → Native domain model 映射

| Python 模型（字段） | Native 类型 | 取舍说明 |
|---|---|---|
| `CurveData{name,unit,depth[],values[],display_range,color,line_style}` | `CurveBuffer`（数据）+ `CurveBinding`（配置） | **数据与配置分离**（Python 把 style/range 塞进数据模型是债）。数据侧 `shared_ptr<const>` + revision；配置侧可序列化 |
| `IntervalItem{top,bottom,name}` | `DepthInterval{top,bottom,category}` | 泛化为带 category 的区间；8 层级仅是 category 取值 |
| `LithologyInterval{top,bottom,lithology,description}` | `LithologyInterval` | pattern key=lithology；description 进 inspection |
| `FaciesInterval{facies,sub_facies,micro_facies}` + `FaciesData{phase[],sub_phase[],micro_phase[]}` | `FaciesIntervalSet`（三列列表） | nested 三等分宽渲染语义保留 |
| `WellIntervals`（8 列表） | host adapter 职责 | **不进 domain**：那是源数据形状，host 转成 `IntervalTrackData` |
| `WellLogData{well_name,top/bottom_depth,datum_elevation,curves,lithology,facies,intervals,custom_tracks,total_rows,decimated}` | `WellDataSnapshot`（数据快照）+ `WellDescriptor` | custom_tracks（dict！）不搬；total_rows/decimated 进快照 provenance |
| Marker 鸭子类型（`depth|reference_depth`+`label|name`） | `WellTop{depth,name,color?}` | 结构化，编译期可查 |
| `FormationTop{well_name,formation_name,depth_m,color}` | `WellTop` | 去掉 well_name（单井上下文由 document 持有） |
| `HorizonPick{pick_id,formation_name,well_depths,source,confidence}` | **不进 v1** | 单井拾取编辑=未来任务；source/confidence 语义记录在 03 |
| `CorrelationLink{source_interval_id:"top_bottom_name"}` | **不搬** | 字符串编码是反模式（00-baseline #7） |
| `CheckshotTable{depths_m[],twt_ms[]}` / `WellTieCalibration` | `IDepthTransformService`（接口） | host 注入实现；B 只消费 `depthToTwt/twtToDepth` |
| `LineStyle` enum（SOLID/DASHED/DOTTED） | `LineStyle` enum class | 一致 |
| `CURVE_META`（名字→颜色/虚线）+ `_LOG_SCALE_CURVES` | `CurveStyleDefaults` | 默认样式表（可被 host 覆盖） |

## 概念上不存在、需新建（无 Python 对应物）

- `TrackId/CurveId`：稳定 id（Python 用 label 字符串+`id()` 记账，重名靠上游消歧）。
- `WellTrackViewConfig`：可序列化视图配置（track order/width/visible/curve assignments/styles/x-ranges/domain/template id）——**能力增量**（现状无持久化）。
- `WellTrackViewState`：运行时视口（当前 depth range、全范围、选择态、域标签）。
- `TrackLayout`：顺序+宽度+splitter 语义（Python 散落在 canvas/页面内存态）。
- `InspectionResult`：结构化巡检结果（Python 是 overlay 内部拼字符串）。
- `SelectionState`：选中 track/curve/interval（QPainter 管线无选中态；scene 版有但属连井）。

## Ownership 规则（从 Python 债推导）

1. 数据快照 immutable（`shared_ptr<const WellDataSnapshot>`），多 view 共享零拷贝；Python 的 CurveTrack 构造期整体重建 CurveData（内存翻倍）不允许重演。
2. 配置（可序列化）与数据（大数组）分离；不经 JSON 中转热路径。
3. domain 类型不继承 QObject/QWidget；Qt 类型只出现在 view/interop 层边界（颜色用 `std::uint32_t rgba` 在 domain，view 层转 QColor）。
4. 稳定 id + 显式 ownership（document 拥有 track 定义；controller 拥有 view state；widget 拥有 kernel 句柄）。

## Depth domain 结论（对应任务 §6）

- 渲染域：MD（浮点米）。`DepthDomain` 枚举 `{Md, TvdsdLabel, TwtSecondary}`——实际建模为：`DepthAxisDomain {Md}` + 可选 `SecondaryAxisAnnotation{Twt}`（由 `IDepthTransformService` 供给）。
- `datum_elevation` 作为 `WellDescriptor` 元数据透传（渲染不消费，与 Python 一致）。
- TVDSS：host 算好填 MD（`src/data/loaders.py` 现状），Native 只在 header 标注域标签。
- 不实现：MD→TVD、时间域重采样、单位换算（无消费者；转换一律接口注入）。
