# Task Plan: Phase 15 — Project File Serialization (.gvz) & DataPage UI Integration

## Goal
引入 `.gvz` (GeoViz Project) 工程文件序列化与反序列化机制，支持将多井、多体、多层位引用，以及用户拾取（Manual Picks）、地层对比关系（Correlation Links）与当前视图状态（View State）统一保存与读取，实现日常科研与工程的 daily-use 项目闭环。并在 DataPage 提供 Open / Save / Save As UI。

该功能的研发遵循严格的 **TDD 流程**：写 RED 测试 -> 实现 GREEN -> 优化 REFACTOR。

## Phases

### Phase 1: 设计 Schema 与 ProjectManager 核心库 (TDD RED-GREEN)
- [x] 设计基于 `pydantic` 的 JSON-friendly, Git-friendly `.gvz` 规范 schema：
  - `meta`: 项目名称、版本号 (`0.8.0`)、创建/修改时间。
  - `wells`: 多井数据引用列表（Excel/LAS 文件路径、井位经纬度）。
  - `seismic`: 3D 地震数据引用及参数（SEGY 路径、坐标原点/spacing）。
  - `horizons`: 层位文件引用列表。
  - `picks`: 用户拾取（Inline, Crossline, Time 坐标列表）。
  - `correlation`: 连井对比关系 (Correlation Links)。
  - `view_state`: 界面状态（当前页面索引、3D 切片位置、色标配置等）。
- [x] 在 `tests/test_project.py` 中编写 TDD 单元测试套件：
  - 测试 schema 数据结构校验。
  - 测试 `ProjectManager` 的 `save_project` 和 `load_project`，验证序列化与反序列化等价性（Round-trip consistency）。
  - 测试路径相对化（Relative paths）处理，防止绝对路径在不同机器间拷贝失效。
- [x] 实现 `src/data/project.py` 及 `ProjectManager` 核心类，实现所有序列化逻辑。
- **Status:** complete

### Phase 2: 全局应用状态集成与 Page 联动 (TDD RED-GREEN)
- [x] 在 `MainWindow` 注入 `ProjectManager`，并提供状态同步 API：
  - `sync_from_project`：将加载后的 project 状态应用到各个子 Page（MapPage, WellLogPage, CrossWellPage, SeismicPage）。
  - `sync_to_project`：收集各个 Page 当前最新编辑/拾取状态到工程结构中。
- [x] 编写集成测试，确保页面状态的收集和恢复逻辑完全正确，无信号回环死锁。
- **Status:** complete

### Phase 3: DataPage UI 接线与 Open/Save 交互 (TDD RED-GREEN)
- [x] 重构 `src/pages/data/page.py`：
  - 增加“工程管理”分组框 (Project Management GroupBox)。
  - 提供 `新建工程`、`打开工程`、`保存工程`、`另存工程` 按钮。
  - 绑定 `QFileDialog` 标准文件对话框。
  - 在“井位坐标”表格上方展示当前加载的工程元数据（如工程名、最近修改时间等）。
- [x] 编写 UI 模拟测试，测试按钮点击信号传导。
- **Status:** complete

### Phase 4: 全量回归与 Pilot 集成校验 (Ship)
- [x] 运行全量 720+ 测试套件，保证 100% 绿。
- [x] 更新根目录 `task_plan.md`、`progress.md` 与 `CHANGELOG.md`。
- [x] 使用 `/ship` 进行提交与交付。
- **Status:** complete

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| **基于 Pydantic 构造 JSON Schema** | pydantic 自带强大的数据类型检验与自动嵌套解析，非常适合 Git 友好的扁平/结构化文本存储。 |
| **相对路径处理** | 工程文件内引用的 Excel / SEGY 文件应该在保存时，若在工程文件同级或子目录下，自动转换为相对路径，确保工程文件包可跨机器拷贝运行。 |
| **DataPage 单入口管理** | 保持业务清爽，DataPage 作为集中管理数据资产与工程生命周期的唯一主入口。 |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| | | |
