# Geo Viz Engine 代码级深度审查报告

> **审查日期**: 2026-08-15
> **审查对象**: `geo-viz-engine/` @ master（dd8e7bf1）
> **审查方式**: 主 Agent 逐文件阅读 + 静态分析 + 算法/性能审查（未修改任何代码）
> **覆盖范围**: `geoviz/` 核心、9 个 workspace 包、`src/` 应用层、`native/map_edit_core`（C++）、`tests/` 体系、现有 audit 文档
> **产出**: 35 个 GitHub Issues（#44–#78，标签 geo-viz-engine + P0–P3）

---

## 1. 项目架构总结

geo-viz-engine 是一个 **PySide6 桌面地质可视化引擎**（不是 C++ GL/Vulkan 引擎），Python 约 5.1 万行 + 1 个 pybind11 C++ 加速模块。分层清晰：

```
数据输入层   geoviz/previews (DAT/LAS/SEGY schema 解析) · src/data (Excel/LAS loader, catalog)
数据管理层   geoviz (Engine/Registry/Contracts/prepared_codec) · SeismicCache · WellCatalog
几何处理层   geoviz_plots (IDW/克里金/方向趋势/等值线/map_edit) · geoviz_paleo_map/topology
渲染核心层   geoviz_seismic/renderer_3d (pyqtgraph GL + 自定义 LUT/R8 shader)
             geoviz_well_log/renderer (QPainter + min-max LOD)
             geoviz_paleo_map layers (QPainter + 四叉树 + pixmap 缓存)
GPU 接口层   PyOpenGL（自写 GLSL LUT shader）+ 可选 CuPy（gpu_ops/colormap）
UI 交互层    src/pages/* （9 个页面） · 各包 canvas/widget
输出层       export_professional / save_export / cross_well report_export（SVG/PDF/PNG）
```

架构评价：

- **优点**：`geoviz` 门面的懒加载 re-export、PreviewBackend 协议、CancellationToken、SliceReadWorker（latest-wins + 预取 + generation 防串代）、CurveTrack 的 searchsorted 裁剪 + min-max LOD + 量化键缓存、`dat.py` 的 schema 驱动解析（CRS 溯源、行级诊断）都是高工程质量。
- **弱点**：渲染热点散落（QPainter 逐点 Python 循环在多处仍是主路径）；`geoviz_map` 与 `geoviz_paleo_map` 基础设施重复；一批“实现了但没接线”的组件（LOD manager、预取、GPU 波形渲染器）。

## 2. 渲染流程分析

**3D 体渲染**（renderer_3d.py）：自定义 `DualGLVolumeItem`（单 3D 纹理双体叠加 + LUT 在 shader 内查表）与 `GLImageLutItem`（R8 索引纹理 + 256×1 LUT，colormap 切换 O(1)）是正确的高性能方向。问题：

- 体渲染固定 `[::2,::2,::2]` 降采样；LOD 管理器存在但未接线（#63）。
- 每次重建无条件计算 CPU 法线图（#57）。
- CPU 体 + CuPy 镜像 + GL 纹理三份拷贝（#77）。
- 纹理超限在 paint 中 raise（#65）。

**2D 剖面**（profile_vd.py）：Indexed8 零拷贝 + clip 缓存 + 视口子切片，是全场最优渲染路径。Wiggle 路径则是逐采样 Python 循环，且 GPU instanced 渲染器未接线（#58）。

**地图**（paleo_map）：LayerPixmapCache（2x buffer pan 复用）+ 四叉树裁剪 + RDP LOD 设计正确，但 ScreenPathCache 的 zoom 量化键会返回错误尺度缓存（#48），矢量花纹逐瓦片 QPicture 回放（#52），FilledContourLayer 无缓存（#53）。

## 3. 数据结构分析

- `PreviewRequest/PreparedPreview` frozen dataclass + schema 版本化磁盘编解码（prepared_codec）——良好。
- `TopologyModel`（共享顶点 + 边索引 + 脏标记）设计正确，edit_commands 撤销/重做严谨。
- 反面：`SliceInfo.axis_*_values` 用 Python list 携带数千浮点（每帧 `.tolist()`）；`_WellResourceLimitError` 前的全量 Python 行解析；`fit_viewport_to_data` 的全顶点 list 收集。

## 4. 算法审查结果

| 算法 | 实现 | 复杂度 | 结论 |
|---|---|---|---|
| 普通克里金 | kriging.py | O(n³+n²m) 一次求解 | 正确；LOO 评估重复拟合（#67） |
| IDW + 断层屏障 | idw.py | O(cells·N·S) 纯 Python | 屏障路径不可用（#56） |
| 方向趋势 | directional.py | 分块向量化 | 良好 |
| DTW | dtw_engine.py | O(n·band) 带状 numpy | 实现好；调用在 UI 线程（#61） |
| RDP 抽稀 | lod.py | 递归 O(n log n) | 极端输入递归深度风险 |
| 四叉树裁剪 | facies_polygons.py | O(log n) 查询 | 正确；编辑后整树重建 |
| 等值线提取 | marching_squares (contourpy) | — | 裁剪时孔洞被填（#68） |
| 顶点捕捉 | map_edit/api.py | 网格索引 O(1) | snap_shared_nodes 为 O(n²)（#55） |
| Min-max LOD | downsample.py | 向量化 | 良好，支持 C++ 注入 |

## 5. 性能问题列表（按严重度）

- **P0**：地震联动坐标系换算错误（#45，正确性）；AI 预测回写源 Excel（#44，数据安全）。
- **P1**：矢量花纹瓦片回放（#52）、FilledContour 全量重建（#53）、编辑把手 O(V×E)（#54）、snap_shared_nodes O(n²)（#55）、IDW 断层三重循环（#56）、层位构面 Python 循环 + 无条件法线图（#57）、Wiggle 逐点循环（#58）、SurfaceWidget 每帧重算等值线（#59）、preview UI 线程 SEGY I/O（#60）、DTW UI 线程 + processEvents 重入（#61）。
- **P2**：loader 三条慢路径（#64）、UI 线程属性计算（#66）、克里金 LOO（#67）、preview 双重 I/O（#73）。

## 6. GPU 优化建议

- 接线 Renderer3DLODManager：交互期 LOD2、静止回 LOD1（#63、#77）。
- normal map 惰性计算 + 按体版本缓存（#57）。
- GLImageLutItem 超限时降采样降级而非 raise（#65）。
- 体数据保留策略：CuPy 镜像与 GL 纹理二选一，避免三份拷贝（#77）。
- gl_clipping 固定管线裁剪面改为 shader clip distance（#76）。

## 7. UI 交互问题

- resize 重置用户视口（#49）；geo 坐标按钮假切换（#50）；DTW processEvents 重入（#61）；terminate() 强杀线程（#74）；导入假成功提示（#70）；标注拖拽半成品、硬编码假状态文本等（#76）。

## 8. 稳定性风险

- **数据损坏**：AI 预测就地改写用户源 xlsx（#44，P0）。
- **坐标造假**：bin_grid 缺失时虚构 Easting/Northing（#46）。
- **崩溃面**：paint 中 raise（#65）、rdp 递归深度、processEvents 重入（#61）、terminate（#74）。
- **静默错误**：render_export 空白 PNG（#62）、比例尺标签错误（#47）、ScreenPathCache 错尺度（#48）、双 LAS 解析器不一致（#75）、auto-tie 不回写标定（#72）。

## 9. Issue 统计

本次审查新建 **35 个 Issue**（WindWang2/geo-viz-engine #44–#78）：

| 优先级 | 数量 | Issue 编号 |
|---|---|---|
| P0 | 2 | #44, #45 |
| P1 | 18 | #46–#63 |
| P2 | 11 | #64–#74 |
| P3 | 4 | #75–#78 |

（分类标签：bug / performance / rendering / gpu / algorithm / memory / ui / architecture / optimization / testing，均带 geo-viz-engine 标签。）

另：2026-06-03 上一轮审计（deep_audit_report.md）的 C1–C9、H1–H17 大部分已修复（本次逐项核实）；本次发现的 P0/P1 多为**新引入或未覆盖**的问题。

## 10. 下一阶段优化路线

1. **立即（正确性）**：#44 源文件保护、#45 坐标换算统一层、#46 坐标溯源、#47 比例尺、#48 缓存尺度一致性。
2. **性能骨架**：#52/#53/#59 渲染缓存三件套；#54/#55/#56 算法复杂度；#60/#61/#74 UI 线程纪律（统一走 worker + CancellationToken）。
3. **架构收敛**：#63 死代码接线或删除；#69 基础设施下沉 geoviz_common；#75 解析器收敛；#71 测试收集补齐 + 性能回归基线。
4. **中期**：体数据 brick/pyramid LOD（VolumeAccess 协议已预留）；GPU 波形渲染接入；CRS 体系统一。

---

*审查笔记与 Issue 生成脚本留存于主仓 `.scratch/geoviz-review-notes.md` / `.scratch/geoviz_issues_{1,2}.py`。*

---

# 修复轮次（2026-08-16 追加）

全部 35 个 Issue 已修复并关闭（#44–#78），swarm 共 27 个 coder subagent 分两波完成：

- **Wave 1（24 agents）**：按文件归属划分，同文件 Issue 合并到同一 agent，零文件冲突。
- **Wave 2（3 agents）**：补修漏分配的 #44（P0）；更新 3 个因契约变更过时的测试（test_seismic_spatial / test_geoviz_seismic_preview / test_auto_tie）；#69 基础设施下沉 geoviz_common。

**验证**：全量回归 1545 passed / 7 skipped / 1 failed（仅 golden 图因 #47 比例尺修正的预期渲染变化失配，已核对图像确认差异即修复内容本身，golden 已重生成，重跑通过）。修改 47+ 源文件 + 3 测试文件 + 1 golden，约 +3000/−1200 行；未做任何 git 提交（改动留在工作树，由维护者审阅后提交）。

**修复方式说明**：每处修复的详细技术说明见对应 Issue 的关闭评论。
