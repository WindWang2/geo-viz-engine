# 05 — Target Package Architecture

包：`packages/geoviz-well-track-native/` · target `GeoViz::WellTrackNative`（库文件 target `geoviz_well_track_native`）· namespace `geoviz::well_track` · C++17 · Qt6（Core/Gui/Widgets；**不含** QGIS）。

## 目录

```
packages/geoviz-well-track-native/
├── CMakeLists.txt                  # 独立可配置；Qt6 find_package；可选 GeoVizQgisWellTrack
├── README.md                       # 消费指南 + host integration 示例
├── include/geoviz/well_track/      # public headers（全部安装）
│   ├── well_track.h                # umbrella
│   ├── domain/
│   │   ├── ids.h                   # TrackId/CurveId/IntervalSetId/MarkerSetId（StrongId）
│   │   ├── depth.h                 # DepthRange/DepthDomainLabel/niceDepthInterval
│   │   ├── curve.h                 # CurveMetadata/CurveBuffer(valueAt 插值)/CurveBufferPtr
│   │   ├── curve_style.h           # LineStyle/CurveStyle/ScaleKind/XRange/resolveXRange
│   │   ├── robust_range.h          # computeRobustDisplayRange（P2~P98 + GR/RHOB/NPHI 预设）
│   │   ├── intervals.h             # IntervalItem/IntervalColumn/IntervalSetData/IntervalShape/IntervalStyle
│   │   ├── markers.h               # WellTop/MarkerSetData
│   │   ├── images.h                # ImageSegment/ImageSetData
│   │   └── defaults.h              # CurveStyleDefaults（CURVE_META/merge groups/log curves/label map）
│   ├── data/
│   │   ├── snapshot.h              # WellDescriptor/WellDataSnapshot/Provenance
│   │   └── data_source.h           # IWellTrackDataSource/IDepthTransformService
│   ├── config/
│   │   └── view_config.h           # WellTrackViewConfig（可序列化）+ toJson/fromJson
│   └── view/
│       ├── render_surface.h        # IWellTrackSurface + Surface* 值类型（冻结 seam，04）
│       ├── surface_factory.h       # ISurfaceFactory + 内置注册点
│       ├── inspection.h            # InspectionResult/CurveReading/IntervalHit
│       ├── selection.h             # SelectionState
│       ├── well_track_controller.h # WellTrackController（QObject）
│       ├── well_track_widget.h     # WellTrackWidget（QWidget 产品组件）
│       └── well_track_factory.h    # WellTrackViewFactory
├── src/
│   ├── domain/{curve,robust_range,intervals,defaults,depth}.cpp
│   ├── config/view_config.cpp
│   ├── data/snapshot.cpp
│   ├── view/{well_track_controller,well_track_widget,inspection,splitter_overlay,crosshair_overlay,surface_registry}.cpp
│   └── view/qgis_surface.cpp       # ← 唯一 include A 头的文件（条件编译）
├── assets/patterns/*.svg           # 自 well_log 包复制的 19 岩性 + 17 相 SVG（数据资产，非代码）
├── tests/
│   ├── CMakeLists.txt
│   ├── domain/…                    # Qt-free 逻辑测试（QtTest 无 GUI）
│   ├── config/…                    # 序列化 roundtrip
│   ├── view/…                      # MockSurface 驱动的 controller/widget 测试（offscreen）
│   └── mock_surface.h              # 记录式 test double
├── examples/
│   ├── CMakeLists.txt
│   └── host_integration_example.cpp  # representative well smoke（需 A；否则跳过 target）
└── docs/ → 仓库 docs/development/native-welltrack-workbench/
```

## 分层与依赖方向

```
domain（Qt-free，仅 std）   ← 不依赖任何上层
config（QtCore，QJson）      ← 依赖 domain
data （QtCore）              ← 依赖 domain
view （QtCore/Gui/Widgets）  ← 依赖 domain+config+data；经 IWellTrackSurface 抽象消费 A
```

- domain 头不 include 任何 Qt 头（颜色 `std::uint32_t` 0xAARRGGBB；异常用返回值/optional，保持 noexcept 友好）。
- `IWellTrackSurface` 是 QObject（信号槽承转 A 的输入意图）；Surface* 值结构在 view 层可用 QColor/QString。
- 唯一 back-edge：controller 持 widget/表面指针均经 `QPointer`/值语义，禁止 domain→view 引用。

## 关键类型速览（实现在 include 中为权威）

```cpp
// domain
template<class Tag> struct StrongId { std::string value; … };
using TrackId = StrongId<struct TrackIdTag>;   // 稳定字符串 id（可序列化）
struct DepthRange { double top=0, bottom=1; void normalize(); … };
struct CurveBuffer {                 // immutable 数据侧
    std::vector<double> depths, values;   // 已按 depth 升序；NaN=洞
    CurveMetadata meta; std::uint64_t revision=0;
    std::size_t size() const; double valueAt(double depth) const; // bisect 线性插值，洞→NaN
};
struct XRange { std::optional<std::pair<double,double>> manual; ScaleKind scale=Linear; };
struct IntervalItem { double top, bottom; std::string category, description; };
struct IntervalSetData { std::vector<IntervalColumn> columns; };  // FaciesTrack=3 列 nested
struct WellTop { double depth; std::string name; std::uint32_t color=0; }; // 0=用默认调色板

// data
struct WellDataSnapshot {
    WellDescriptor well; std::uint64_t revision=0;
    DepthRange fullRange;
    std::map<CurveId, CurveBufferPtr> curves;                  // 低拷贝：shared_ptr<const>
    std::map<IntervalSetId, std::shared_ptr<const IntervalSetData>> intervalSets;
    std::map<MarkerSetId, std::shared_ptr<const MarkerSetData>> markerSets;
    std::map<IntervalSetId, std::shared_ptr<const ImageSetData>> imageSets;
    std::optional<Provenance> provenance;
};
class IWellTrackDataSource {         // host 实现；GUI 线程调用
public: virtual ~…; virtual WellDescriptor descriptor() const=0;
    virtual std::shared_ptr<const WellDataSnapshot> snapshot() const=0;
};
class IDepthTransformService { virtual double depthToTwt(double m)=0; virtual double twtToDepth(double ms)=0; };

// config：视图/轨道配置（可序列化，无大数组）
struct TrackConfigEntry { TrackId id; std::string title; TrackKind kind; int width; bool visible;
                          XRange xRange; std::vector<CurveAssignment> curves; … };
struct WellTrackViewConfig { int schemaVersion=1; std::string templateId;
    std::vector<TrackConfigEntry> tracks; std::string depthDomainLabel; QJsonObject toJson() const; … };

// view
class WellTrackController : public QObject { … 见 06 };
class WellTrackWidget : public QWidget { … };
```

## 更新粒度（§16 的实现机制）

controller 内部 `ChangeSet` 区分六类：`StyleOnly(trackId)` / `ViewStateOnly` / `CurveData(curveId, oldRev→newRev)` / `TrackStructural` / `DepthTransform` / `FullDocument`。差异直接映射为 seam 调用：单列 `updateTrack` vs 全量 `setTracks`。断言手段：MockSurface 记录调用序列，测试验证最小调用集。

## 反目标（本包禁止出现）

generic PlotCanvas、generic axis renderer、zoom/pan 框架、QGraphicsScene 替代、LOD 引擎、curve painter、第二 SVG 渲染框架（pattern 材质化归 A；B 只做名字→资产 key 的**数据**解析）、QVariantMap 类型系统、热路径 JSON 中转、逐点 QObject/QVariant。
