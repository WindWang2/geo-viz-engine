# 07 — Data Adapters（数据边界与 host 适配层）

## 设计原则（任务 §12）

- 包不依赖 paleo-workbench 内部类型（AppWellLogData/WellCatalog/loaders 等）。
- 接口按**真实数据边界**最小化：现有 app 的边界就是"后台加载完成后的一次性 WellLogData 快照" + 可选 checkshot 表。不做 per-curve 拉取、不做懒加载分页、不做单位换算（现状无消费者）。
- adapter 实现放 host 侧（`src/pages/well_log/` 或独立 integration target），**不进本包**。

## B 侧接口（唯一数据入口）

```cpp
class IWellTrackDataSource {
public:
    virtual ~IWellTrackDataSource() = default;
    virtual WellDescriptor descriptor() const = 0;
    virtual std::shared_ptr<const WellDataSnapshot> snapshot() const = 0;
};
```

- 快照不可变；曲线数据 `shared_ptr<const CurveBuffer>`，一份数据多视图零拷贝。
- `WellDescriptor{id, displayName, depthUnitLabel("m"), datumElevation, domainLabel("MD"/"TVDSS")}` —— TVDSS 情形：host 已按 `src/data/loaders.py` 现状把 TVDSS 值算好填入深度列，domainLabel 仅是标注（00-baseline 深度域结论）。

## Host adapter 映射表（现有 Python 数据 → 快照）

| Python（src/data） | Native 快照字段 | 转换说明 |
|---|---|---|
| `WellLogData.well_name` | `well.displayName`（id 由 host 稳定化） | |
| `top_depth/bottom_depth` | `fullRange` | swap+防零 |
| `curves: list[CurveData]` | `curves: map<CurveId, CurveBufferPtr>` | `list[float]→vector<double>`；**必须**先排序+剔非有限深度（Python 在 CurveTrack 内做，Native 约定 host 不必做，adapter 内做一次）；重复 mnemonic 以 `name#2` 消歧为稳定 CurveId（沿用 `unique_curve_names` 语义） |
| `intervals.series/system/formation/member` | `intervalSets["stratigraphy"].columns[...]` | 列 key=字段名 |
| `intervals.lithology / data.lithology(LithologyInterval)` | `intervalSets["lithology"]`，category=lithology 名 | description 保留 |
| `intervals.facies(FaciesData)` | `intervalSets["facies"]` 3 列（phase/sub_phase/micro_phase） | nested 渲染 |
| `intervals.systems_tract` | `intervalSets["systems_tract"]` | shape 按名称映射三角/矩形 |
| `intervals.lithology_desc` | `imageSets["core_photos"]`（CorePhotoSegment 对应 ImageSegment） | |
| `intervals.sequence` | `intervalSets["sequence"]` | |
| markers（鸭子类型 `depth/reference_depth`+`label/name`） | `markerSets["tops"]`（WellTop） | **结构化**，鸭子类型由 adapter 归一 |
| `datum_elevation` | `well.datumElevation` | 透传 |
| `total_rows/decimated` | `provenance` | 预览降采样溯源 |
| checkshot CSV | host 自建 `IDepthTransformService` 实现（如分段线性） | B 不重实现 |

## IDepthTransformService

```cpp
class IDepthTransformService {
public:
    virtual ~IDepthTransformService() = default;
    virtual double depthToTwt(double depthM) const = 0;   // 无表→NaN
    virtual double twtToDepth(double twtMs) const = 0;
};
```

- 仅用于 TWT 标注轴（行为等价 `PickingOverlay._paint_twt_axis` 的数据源 `CheckshotTable`）。
- B 不提供产品级实现；测试/示例中有一个线性测试桩（非产品代码）。

## 反模式（从现状债推导，adapter 评审清单）

1. 不复制 pydantic list→list 全量深拷贝两次以上（一次 vector 化即止）。
2. CurveId 稳定化必须先于任何按名索引（Python 用 `id()` 记账的教训，builder #584）。
3. 不把 `custom_tracks: list[dict]`（无 schema dict 流）搬进来；host 需要时自行转 TrackConfigEntry。
4. 单位字符串只是元数据；绝不在 adapter 里做数值换算（现状无单位换算消费者）。
