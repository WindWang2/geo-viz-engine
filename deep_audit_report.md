# GeoViz Engine — 全量代码深度审计报告

> **审计日期**: 2026-06-03
> **审计范围**: 全部 7 个 package + src/ + tests/ + docs/
> **审计方式**: 6 个并行 subagent 逐行审核
> **当前测试**: 892 passed, 0 failed

---

## 一、BUG 汇总（按严重程度排序）

### CRITICAL — 运行时崩溃/数据损坏

| # | 文件 | 行号 | 问题 | 置信度 |
|---|------|------|------|--------|
| C1 | `geoviz_well_log/chart_engine.py` | 131 | `render_well_log_data()` import 不存在的 `utils.py` → `ImportError` | 100% |
| C2 | `geoviz_well_log/connection_overlay.py` | 16-22 | `_well_names` 未在 `__init__` 初始化 → `paint_event()` 时 `AttributeError` | 95% |
| C3 | `geoviz_seismic/renderer_3d.py` | 179-182 | `_uploadHorizonTexture()` 内复制粘贴错误，重置 `_shading_enabled=False` → 上传层位时静默关闭光照 | 95% |
| C4 | `geoviz_seismic/loader.py` | 85-90 | 异常处理引用未赋值的局部变量 `f` → `UnboundLocalError` 掩盖原始错误（3处） | 90% |
| C5 | `geoviz_seismic/well_tie_panel.py` | 130-131 | Auto-Tie 按钮未连接 slot → 按钮完全无功能 | 95% |
| C6 | `geoviz_paleo_map/edit_commands.py` | 140 | `DeleteVertexCmd` 无条件删除共享顶点 → 相邻多边形几何损坏 | 82% |
| C7 | `geoviz_paleo_map/edit_commands.py` | 53 | `MovePolygonCmd` 对多环多边形使用错误回退位置 `(0,0)` → 拖拽时几何损坏 | 80% |
| C8 | `src/pages/cross_well/page.py` | 449 | `self.canvas.pick_mode = False` 应为 `self._canvas` → Escape 键崩溃 | 95% |
| C9 | `src/main.py` | 241 | `time.sleep(1.0)` 阻塞主线程 → 启动动画冻结 | 95% |

### HIGH — 功能缺陷/数据丢失

| # | 文件 | 行号 | 问题 | 置信度 |
|---|------|------|------|--------|
| H1 | `geoviz_seismic/renderer_3d.py` | 88-92, 184-188 | `setShading` 方法重复定义（copy-paste） | 85% |
| H2 | `geoviz_seismic/renderer_3d.py` | 686-701 | `DualGLVolumeItem.clean()` 不释放 horizon/normal 纹理 → GPU 内存泄漏 | 85% |
| H3 | `geoviz_paleo_map/layers/region_labels.py` | 168 | `visible_labels` 未在 `__init__` 初始化 → 首次 `paint()` 前访问崩溃 | 82% |
| H4 | `geoviz_paleo_map/screen_path_cache.py` | 34 | `np.ndarray` 类型注解缺少 `import numpy` → 运行时类型检查失败 | 90% |
| H5 | `geoviz_paleo_map/layers/facies_polygons.py` | 25 | 同上，`_Item` dataclass 缺少 numpy 导入 | 90% |
| H6 | `geoviz_map/screen_path_cache.py` | 全文 | 平移时不使缓存失效（缺少 `_zoom_center` 跟踪）→ 平移后多边形路径错位 | 80% |
| H7 | `src/pages/map/page.py` | 104-106 | 芯片标签硬编码 "全部 46" / "已解释 31" / "含气 12" → 不反映实际数据 | 85% |
| H8 | `src/pages/map/page.py` | 282-298 | "含气" 过滤器与 "已解释" 过滤器逻辑完全相同 → 假功能 | 85% |
| H9 | `src/data/loaders.py` | 357-358 | `line_style` 计算后未传入 `CurveData` → 所有曲线使用默认线型 | 90% |
| H10 | `src/pages/data/page.py` | 438-449 | LAS/SEGY/JSON 导入实际是空操作 → 用户看到"成功"但数据不可用 | 85% |
| H11 | `src/data/cache.py` | 18-29 | `rename_well`/`remove_well` 只修改内存 → 重启丢失 | 80% |
| H12 | `src/app.py` | 462-466 | 设置按钮选中状态不更新 → 切换到设置页无视觉反馈 | 90% |
| H13 | `geoviz_cross_well/correlation_layer.py` | 22 | `_formation_color` 使用非确定性 `hash()` → 每次运行颜色不同 | 82% |
| H14 | `geoviz_cross_well/tops_model.py` | 42 | 同上，`FormationTop.__post_init__` 使用 `hash()` | 82% |
| H15 | `geoviz_plots/interpolation/idw.py` | 29 | 空输入返回 `np.zeros` 而非 `np.nan` → 静默产生错误数据 | 83% |
| H16 | `geoviz_plots/chart/axes.py` | 14 | `nice_number` 对负数输入崩溃 `math.log10` | 90% |
| H17 | `geoviz_plots/surface/surface_widget.py` | 379 | 等值线 major-level 判断 `abs(lv) % 2.0 == 0.0` 对地质数据无意义 | 88% |

### MEDIUM — 代码质量/性能

| # | 文件 | 行号 | 问题 | 置信度 |
|---|------|------|------|--------|
| M1 | `geoviz_seismic/renderer_3d.py` | 12 | 未使用的 `QtOpenGL` 导入 | 95% |
| M2 | `geoviz_seismic/seismic_view.py` | 6 | 未使用的 `QColor` 导入 | 90% |
| M3 | `geoviz_seismic/loader.py` | 264 | 计算但未使用的 `sqrt_n` | 95% |
| M4 | `geoviz_seismic/well_tie_panel.py` | 203 | 计算但未使用的 `t_max` | 90% |
| M5 | `geoviz_seismic/renderer_3d.py` | 748 | 设置但未读取的 `_plotter` 属性 | 85% |
| M6 | `geoviz_seismic/dialogs/crossplot.py` | 42-46 | 纯 Python 循环绘制散点 → 大数据集卡顿 | 82% |
| M7 | `geoviz_well_log/renderer/canvas.py` | 5,49 | `WellLogCanvas` 继承 `QOpenGLWidget` 但只用 QPainter → 不必要的 GPU 开销 | 85% |
| M8 | `geoviz_well_log/renderer/curve_track.py` | 29 | `_path_cache` 无大小限制 → 长时间运行内存增长 | 82% |
| M9 | `geoviz_well_log/renderer/curve_track.py` | 216-226 | 多曲线 track 只显示第一条曲线的范围 | 82% |
| M10 | `geoviz_well_log/qpainter_builder.py` | 46-57 | `_apply_curve_meta` 丢失 `unit` 字段 | 82% |
| M11 | `src/pages/plots/page.py` | 308-310 | 使用 `QThread.terminate()` → 潜在死锁/内存损坏 | 85% |
| M12 | `src/main.py` | 多处 | DEBUG print 语句留在生产代码中 | 90% |
| M13 | `geoviz_paleo_map/canvas.py` | 605 | `fit_viewport_to_data()` 在每次 `resizeEvent` 无条件调用 → 冗余计算 | 85% |
| M14 | `geoviz_paleo_map/canvas.py` | 298-313, 356-364 | `_resolve_level()` 和 `_resolve_level_name()` 近重复方法 | 95% |
| M15 | `geoviz_paleo_map/export_professional.py` | 41 | `color_mode="cmyk"` 参数接受但从未使用 | 90% |
| M16 | `geoviz_paleo_map/export_professional.py` | 175-286 | `_draw_scale_bar/north_arrow/legend_panel` 3个函数从未调用 | 95% |
| M17 | `geoviz_cross_well/picks_model.py` | 110-121 | `CompositePickCmd` 定义但从未使用 | 85% |
| M18 | `geoviz_cross_well/canvas.py` | 304 | 拾取命中容差硬编码 5.0m → 不适配不同深度范围 | 82% |

---

## 二、死代码清单

| 文件 | 行数 | 说明 |
|------|------|------|
| `src/pages/cross_well/scene_page.py` | 598 | 早期实验代码，从未被 app 加载 |
| `geoviz_well_log/modules.py` | 67 | 旧 pyqtgraph LayoutCoordinator，已被 renderer/coordinator.py 替代 |
| `geoviz_well_log/config.py` | 74 | ECharts 时代的 track config 模型，QPainter 管线不使用 |
| `src/pages/tools/dialogs.py:CalamineCompilerDialog` | 59 | 未被任何 tool card 引用 |
| `geoviz_paleo_map/save_export.py:export_svg()` | 18 | 伪 SVG（内嵌 PNG），实际向量导出用 `export_vector_svg` |
| `geoviz_plots/chart/plot_widget.py` | ~400 | PlotWidget 完整实现但从未在生产 app 中使用（orphan） |

**死代码总行数**: ~1,216 行

---

## 三、测试覆盖缺口

### 零覆盖模块

| 包 | 无测试模块 |
|---|---|
| geoviz-well-log | `scene/cross_well_view.py`, `scene/well_item.py`, `scene/correlation_band.py`, `scene/depth_ruler_item.py`, `location_map.py`, `config.py` |
| geoviz-seismic | `attributes.py` (全部14个属性函数), `attribute_pipeline.py`, `gpu_ops.py`, `profile_vd.py`, `profile_wiggle.py`, `colorbar_widget.py`, `dialogs/crossplot.py`, `dialogs/horizon_manager.py` |
| geoviz-map | 0 个包级测试文件 |
| geoviz-paleo-map | 0 个包级测试文件 |
| geoviz-cross-well | `correlation_layer.py`, `report_export.py` |
| geoviz-plots | `interpolation/idw.py` (仅1个测试), `surface/marching_squares.py` (仅1个) |
| geoviz-well-tie | 0 个包级测试文件 |

### 测试基础设施问题

1. **包级测试被排除**: `pyproject.toml` 的 `testpaths = ["tests"]` 不含 `packages/*/tests/`，49 个 cross-well 测试不在 CI 运行
2. **6 个包无独立测试**: well-log, seismic, map, paleo-map, plots, well-tie 均无包级测试，违反"独立 pip-installable"声明
3. **dead code 有测试**: `test_modules.py` 测试已废弃的 `modules.py`

---

## 四、文档过时清单

| 文档 | 问题 |
|------|------|
| README.md | 5 处引用 MapLibre GL（已迁移到 QPainter）；3 处只提 ECharts（缺 QPainter 渲染路径）；路线图止于 Phase 18 |
| CLAUDE.md | 2 处 MapLibre/WebChannel 引用；4 处 ECharts-only 引用；缺 QPainter 架构描述 |
| docs/releases/ | 缺 Phase 19-25 发布说明（6 个 phase） |
| packages/geoviz_plots/README.md | 仅 3 行 stub |
| geoviz-seismic/pyproject.toml | `vispy>=0.16.1` 依赖从未 import → 死依赖 |

---

## 五、未开发功能分析（基于项目定位）

项目定位: **科研院所 + 中小油田 + 教学 + 出版级出图**

### 5.1 数据 I/O 缺口

| 功能 | 现状 | 重要性 |
|------|------|--------|
| **LAS 文件实际加载** | 导入按钮存在但为空操作 | 🔴 P0 |
| **SEGY 文件实际加载** | 同上 | 🔴 P0 |
| **项目文件持久化** | `ProjectManager` 存在但 DataPage 的 rename/delete 只改内存 | 🟡 P1 |
| **批量数据导入** | 无批量导入向导 | 🟢 P2 |
| **数据格式转换工具** | XML→Excel 存在，但缺 LAS→Excel / SEGY→JSON | 🟢 P2 |

### 5.2 可视化功能缺口

| 功能 | 现状 | 重要性 |
|------|------|--------|
| **WellLog QPainter 渲染路径文档** | `WellLogCanvas` 已实现但 README/CLAUDE.md 未记录 | 🟡 P1 |
| **PaleoMap 井位交互** | `WellsScatterLayer` 无 `hit_test` → 井点不可点击 | 🟡 P1 |
| **等值线 major/minor 级别** | 启发式对地质数据无意义 | 🟡 P1 |
| **PlotWidget 生产接入** | 完整实现但未接入 PlotsPage | 🟡 P1 |
| **CMYK 色彩空间导出** | 参数存在但未实现 | 🟢 P2 |
| **地震属性体渲染** | findings.md 标记为 Tier 3 未实现 | 🟢 P2 |
| **方向性花纹（物源方向）** | Phase 10 设计时推迟到 Phase 2 | 🟢 P2 |

### 5.3 交互/UX 缺口

| 功能 | 现状 | 重要性 |
|------|------|--------|
| **连井自动连井 DTW 生产接入** | `propagate_pick_via_dtw` 已实现但 UI 按钮仍走 name-match | 🟡 P1 |
| **设置页视觉反馈** | 按钮选中状态不更新 | 🟡 P1 |
| **数据页 well 重命名/删除持久化** | 只改内存，重启丢失 | 🟡 P1 |
| **地图井位筛选** | "含气"筛选是假功能 | 🟢 P2 |
| **等值线图交互** | 缺点击读值、等值线标注 | 🟢 P2 |

### 5.4 工程质量缺口

| 功能 | 现状 | 重要性 |
|------|------|--------|
| **统一日志系统** | 仅 seismic 有 logging，其余 6 包为零 | 🟡 P1 |
| **geoviz_core 共享包** | collision/paint_scheduler/screen_path_cache 在 map 和 paleo-map 间复制 | 🟡 P1 |
| **QOpenGLWidget → QWidget** | WellLogCanvas 不需要 OpenGL 但继承 QOpenGLWidget | 🟢 P2 |
| **InterpolationWorker 安全取消** | 使用 `terminate()` 而非协作式取消 | 🟢 P2 |

---

## 六、优先修复建议

### 立即修复（影响运行时稳定性）

1. **C1**: 删除 `chart_engine.py:131` 的死 import 或恢复 `utils.py`
2. **C2**: `connection_overlay.py` 的 `__init__` 加 `self._well_names = []`
3. **C3**: 删除 `renderer_3d.py:179-182` 的 shading 重置代码
4. **C4**: `loader.py` 异常处理改用 `self._f` 而非 `f`
5. **C5**: 连接 Auto-Tie 按钮的 slot
6. **C8**: `page.py:449` 改 `self.canvas` → `self._canvas`
7. **C9**: 删除 `main.py:241` 的 `time.sleep(1.0)`

### 短期修复（影响数据正确性）

8. **H9**: `load_well_log_converted` 传递 `line_style` 给 `CurveData`
9. **H13/H14**: `hash()` → 确定性哈希
10. **H15**: IDW 空输入返回 `np.nan`
11. **H16**: `nice_number` 处理负数输入
12. **C6/C7**: 修复拓扑编辑命令的共享顶点/多环多边形处理

### 中期清理（代码健康）

13. 删除 ~1,216 行死代码
14. 删除 `vispy` 死依赖
15. 更新 README.md / CLAUDE.md 中的过时架构引用
16. 补写 Phase 19-25 发布说明
17. 将 `pyproject.toml` testpaths 扩展到包含包级测试
