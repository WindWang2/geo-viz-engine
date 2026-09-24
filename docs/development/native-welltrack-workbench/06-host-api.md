# 06 — Host API（主程序调用面）

目标：`paleo-workbench`（或任意 Qt6 C++ host）`find_package(GeoVizWellTrackNative)` + 链接 `GeoViz::WellTrackNative` 即可；不 include geo-viz 私有头、不依赖其 Python 包。

## CMake

```cmake
find_package(GeoVizWellTrackNative CONFIG REQUIRED)      # B 的 install 导出
target_link_libraries(paleo-workbench PRIVATE
    GeoViz::WellTrackNative
    GeoViz::QgisWellTrack)   # 运行时渲染经 B 的 QgisSurface 间接依赖 A
```

## 最小集成（对应任务 §14 示意）

```cpp
#include <geoviz/well_track/well_track.h>

// 1) host 侧数据源（实现两个纯虚函数；加载线程归 host）
class WorkbenchWellSource final : public geoviz::well_track::IWellTrackDataSource {
public:
    explicit WorkbenchWellSource(WellRecordPtr rec) : rec_(std::move(rec)) {}
    geoviz::well_track::WellDescriptor descriptor() const override { return rec_->descriptor(); }
    std::shared_ptr<const geoviz::well_track::WellDataSnapshot> snapshot() const override {
        return rec_->snapshot();   // host 后台线程构建，GUI 线程取
    }
private:
    WellRecordPtr rec_;
};

// 2) 创建产品组件（factory 内部：controller + widget + surface 装配）
auto source  = std::make_shared<WorkbenchWellSource>(record);
auto factory = geoviz::well_track::WellTrackViewFactory{};
auto *view   = factory.create(source, parentWidget);   // WellTrackWidget*
layout->addWidget(view);

// 3) 可选：TWT 标注轴（注入 host 的 checkshot 服务，B 不重实现）
view->controller()->setDepthTransform(myCheckshotService);

// 4) 可选：保存/恢复视图配置（host 决定存放位置）
auto cfg = view->controller()->viewConfig();           // 值类型
QJsonObject json = cfg.toJson();                       // host 存进自己的 project 文件
view->controller()->applyViewConfig(WellTrackViewConfig::fromJson(json));
```

## WellTrackController 公共面（权威以 header 为准）

**文档/数据**
- `void loadSource(std::shared_ptr<IWellTrackDataSource>)` — 建默认文档（等价 `build_qpainter_tracks` 规则）。
- `void replaceSnapshot(std::shared_ptr<const WellDataSnapshot>)` — 同井数据刷新（revision diff，六类更新粒度）。
- `std::shared_ptr<const WellDataSnapshot> snapshot() const`。

**深度/导航**
- `void setDepthRange(double top, double bottom)`（钳制+swap+防零+no-op 守卫）
- `void zoomAt(double anchorDepth, double factor)` / `void panDepth(double delta)` / `void fitDepth()`
- `DepthRange depthRange() const`；`DepthRange fullRange() const`
- `void setDepthTransform(IDepthTransformService*)`（TWT 标注；nullptr 清除）

**轨道管理**
- `TrackId addCurveTrack(std::vector<CurveId>)` / `bool removeTrack(TrackId)`
- `bool moveTrack(TrackId, std::size_t newIndex)`
- `bool setTrackVisible(TrackId, bool)` / `bool setTrackWidth(TrackId, int px)`（钳 40..300）
- `TrackId mergeCurvesIntoTrack(std::vector<CurveId>, std::string title)` / `bool splitCurveFromTrack(TrackId, CurveId)`
- `bool setCurveStyle(TrackId, CurveId, CurveStyle)`（style-only 粒度）
- `bool setTrackXRange(TrackId, XRange)`

**巡检/选择**
- `InspectionResult inspectAt(double depth) const` — 各曲线插值 + interval/marker 命中 + 井元数据。
- `void setSelection(SelectionState)` / `SelectionState selection() const`

**信号**
- `depthRangeChanged(double,double)`（已过 no-op 守卫）
- `viewConfigChanged()`（任何 config 变更后）
- `selectionChanged(SelectionState)`
- `snapshotReplaced(std::uint64_t revision)`

## WellTrackWidget 公共面

- `WellTrackController* controller() const`
- `void syncWith(WellTrackWidget* other)` / `void unsyncAll()` — 共享深度组（防回环语义同 Python SyncManager）
- `InspectionResult inspectAtCursor() const`（当前 crosshair 位置）
- 状态栏读出（当前深度/域标签/命中项）内建；空态/错误态内建。

## 线程与生命周期合同

- 本包全部 API **GUI 线程调用**；host 后台加载完成后经 queued signal 把 snapshot 交给 GUI 线程再 `replaceSnapshot`。
- widget 销毁 → controller（widget 的 `unique_ptr` 成员，先于 surface 析构）→ surface（widget 的 QObject 子对象）销毁；host 只需 Qt 父子 ownership，无 delete 责任。
- `IWellTrackDataSource` 由 controller **`std::shared_ptr` 强持有**（controller 是最后一个消费者之一，host 可在 view 销毁后安全复用同一 source 重建 view）。`IDepthTransformService` 为 host 裸指针：host 须先 `setDepthTransform(nullptr)` 再释放服务对象（`data_source.h` 已注明）。
- revision 门控：`replaceSnapshot` 带递增 revision；旧 revision 迟到结果被拒（对照 app 现坑 L3）。
- 无包级单例持有 host 项目状态（SurfaceRegistry 只存 factory 回调；pattern 目录解析为进程级只读缓存，无 host 数据）。

## 包不拥有（host 职责）

工程文件、数据目录、数据库、版本管理、文件生命周期、井加载线程、LAS/Excel 解析、checkshot 插值实现、打印/页面编排。
