# GeoViz Engine — Design Specification

**Date**: 2026-04-13
**Status**: Draft
**Author**: WANG Assistant + User

## 1. Overview

GeoViz Engine 是一个基于前后端分离架构的地质数据可视化桌面应用，面向地质师日常工作（测井分析、地震解释、平面图编制）和教学科研展示。

### 1.1 Goals (Product Vision)

- 提供专业级地质数据可视化能力（测井道图、地震剖面、等值线图、三维地质体）
- 支持大规模数据渲染（1000口井、GB级SEG-Y）
- 桌面端体验，未来可迁移到云端
- 中英双语界面

> 注：V1 首期只交付测井可视化 + 图件导出，地震/平面图/三维为后续版本。

### 1.2 Non-Goals (V1)

- 三维地质体可视化（V2）
- 地震剖面任意线切割（V1.1）
- 平面图交互编辑（V1.1）
- 多用户协作
- 云端部署
- 实时数据采集

### 1.3 Target Users

- **主要**：地质师（日常工作工具，高频使用，强调效率和数据准确性）
- **次要**：教学/科研展示（可视化效果展示，交互简单）

### 1.4 Target Platform

- Windows 桌面端为主
- 架构上预留跨平台能力（Tauri 支持 Mac/Linux）

## 2. Architecture

### 2.1 Architecture Decision: Hybrid Mode (Option C)

开发时外置 Python（热重载、快速调试），发布时 PyInstaller 嵌入打包（终端用户无需配置环境）。

通过环境变量 `GEOVIZ_MODE` 切换：
- `dev`：前端 Vite dev server + Python uvicorn 独立运行
- `prod`：Tauri 启动时 spawn 内嵌的 Python 进程

#### Tauri 2.0 Sidecar 配置与命名

Tauri 2.0 要求 Sidecar 二进制文件遵循平台特定的命名规范：`[binary-name]-[target-triple]`。

1. **tauri.conf.json 配置**:
   ```json
   {
     "bundle": {
       "externalBin": [
         "binaries/geoviz-backend"
       ]
     }
   }
   ```
2. **构建脚本处理**:
   构建时，`src-python` 构建出的可执行文件需重命名为 `geoviz-backend-x86_64-pc-windows-msvc.exe` (以 Windows 为例) 并放入 `src-tauri/binaries/` 目录。

#### Tauri Python 进程管理与安全 (Auth Token)

为了保证本地 API 的安全性，防止其他进程恶意调用，采用动态生成的 Auth Token：

```
Tauri main.rs 启动流程:
1. 生成长度为 32 位的随机 `GEOVIZ_API_TOKEN`
2. 检测 GEOVIZ_MODE 环境变量
3. if prod:
   a. 查找内嵌 Python 可执行文件（按 target-triple 命名规则）
   b. spawn 子进程运行 uvicorn，同时通过环境变量或 `--token` 参数传入 `GEOVIZ_API_TOKEN`
   c. 等待 /api/system/status 返回 200（需验证 Token）
   d. WebView 加载时将 Token 注入前端 `localStorage` 或通过 Rust 暴露给前端
4. if dev:
   a. WebView 直接加载 http://localhost:5173
   b. Python 服务需手动启动并使用固定的开发 Token
```

#### 开发脚本

```bash
# scripts/dev.sh — 开发模式一键启动
#!/bin/bash
cd src-python && source venv/bin/activate && uvicorn app.main:app --port 8000 &
cd src-web && npm run dev -- --port 5173 &
GEOVIZ_MODE=dev cargo tauri dev

# scripts/build.sh — 生产构建
#!/bin/bash
cd src-python && pyinstaller --onefile app/main.py -o ../dist/python/
cd src-web && npm run build
cd src-tauri && GEOVIZ_MODE=prod cargo tauri build
```

### 2.2 System Architecture

```
┌───────────────────────────────────────────────────┐
│  Tauri 2.x (Rust)                                 │
│  桌面壳，窗口管理，Python进程管理                    │
├───────────────────────────────────────────────────┤
│  WebView (前端)                                    │
│  ┌─────────────────────────────────────────────┐  │
│  │  React 18 + TypeScript                      │  │
│  │  ├─ GeoVizRenderer (统一渲染抽象层)          │  │
│  │  │   ├─ Canvas2DRenderer  → 测井曲线         │  │
│  │  │   ├─ WebGLRenderer     → 地震剖面         │  │
│  │  │   ├─ SVGRenderer       → 岩性/等值线交互  │  │
│  │  │   └─ ThreeJSRenderer   → 三维(V2)        │  │
│  │  ├─ Zustand (状态管理)                       │  │
│  │  ├─ TailwindCSS (样式)                       │  │
│  │  └─ i18next (中英双语)                       │  │
│  └─────────────────────────────────────────────┘  │
│                      ↕ HTTP REST / WebSocket       │
│  ┌─────────────────────────────────────────────┐  │
│  │  Python Backend (FastAPI)                    │  │
│  │  ├─ API层: REST + WebSocket                  │  │
│  │  ├─ 服务层: 业务逻辑                          │  │
│  │  │   ├─ WellLogService (lasio)               │  │
│  │  │   ├─ SeismicService (segyio)              │  │
│  │  │   ├─ ContourService (scipy)               │  │
│  │  │   └─ DataGenService (numpy合成数据)        │  │
│  │  ├─ 数据层: 内存缓存 + 文件系统 + 分块索引     │  │
│  │  └─ Pydantic数据模型                          │  │
│  └─────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────┘
```

### 2.3 Directory Structure

```
geo-viz-engine/
├── src-tauri/                # Rust 桌面壳
│   ├── src/
│   │   ├── main.rs           # Tauri入口
│   │   └── python.rs         # Python进程管理
│   ├── Cargo.toml
│   └── tauri.conf.json
├── src-web/                  # 前端 (WebView内容)
│   ├── src/
│   │   ├── components/
│   │   │   ├── well-log/     # 测井可视化组件
│   │   │   ├── lithology/    # 岩性柱状图组件
│   │   │   ├── seismic/      # 地震剖面组件 (V1.1)
│   │   │   ├── contour/      # 等值线图组件 (V1.1)
│   │   │   ├── common/       # 通用UI组件
│   │   │   │   ├── Toolbar.tsx
│   │   │   │   ├── StatusBar.tsx
│   │   │   │   ├── Legend.tsx
│   │   │   │   └── ColorMap.tsx
│   │   │   └── layout/       # 布局组件
│   │   ├── renderers/        # 渲染引擎
│   │   │   ├── GeoVizRenderer.ts
│   │   │   ├── Canvas2DRenderer.ts
│   │   │   ├── WebGLRenderer.ts
│   │   │   └── SVGRenderer.ts
│   │   ├── stores/           # Zustand状态
│   │   │   ├── useWellStore.ts
│   │   │   ├── useViewportStore.ts
│   │   │   └── useSettingsStore.ts
│   │   ├── hooks/            # 自定义hooks
│   │   │   ├── useDataLoader.ts
│   │   │   └── useZoom.ts
│   │   ├── i18n/             # 国际化
│   │   │   ├── zh.json
│   │   │   └── en.json
│   │   ├── router.ts         # 路由配置（独立页面）
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
├── src-python/               # Python后端
│   ├── app/
│   │   ├── main.py           # FastAPI入口
│   │   ├── api/              # API路由
│   │   │   ├── well_log.py
│   │   │   ├── seismic.py
│   │   │   ├── contour.py
│   │   │   └── export.py
│   │   ├── services/         # 业务逻辑
│   │   │   ├── las_parser.py
│   │   │   ├── segy_parser.py
│   │   │   ├── contour_gen.py
│   │   │   └── data_generator.py
│   │   └── models/           # Pydantic模型
│   │       ├── well_log.py
│   │       ├── seismic.py
│   │       └── common.py
│   ├── tests/
│   ├── requirements.txt
│   └── pyproject.toml
├── data/                     # 测试数据
│   ├── sample_las/
│   ├── sample_segy/
│   └── generated/
├── docs/
│   └── superpowers/
│       └── specs/
├── scripts/
│   ├── dev.sh                # 开发启动脚本
│   ├── build.sh              # 生产构建脚本
│   └── generate_data.py      # 模拟数据生成
└── README.md
```

## 3. Frontend Design

### 3.1 Renderer Abstraction Layer

所有可视化模块共享统一渲染接口 `GeoVizRenderer`：

```typescript
interface GeoVizRenderer {
  bindContainer(dom: HTMLElement): void;
  setData(data: ParsedData): void;
  setViewport(viewport: Viewport): void;
  onEvent(event: RendererEvent, callback: Function): void;
  exportImage(format: 'png' | 'svg'): Blob;
  destroy(): void;
}

interface Viewport {
  xMin: number; xMax: number;
  yMin: number; yMax: number;
  zoom: number;
  panX: number; panY: number;
}
```

渲染后端实现：
- `Canvas2DRenderer`：测井曲线、道图（高频刷新，性能优先）
- `SVGRenderer`：岩性符号、交互编辑（DOM操作，交互优先）
- `WebGLRenderer`：地震剖面、大规模数据（GPU加速，V1.1）
- `ThreeJSRenderer`：三维地质体（V2）

### 3.2 Virtual Rendering Strategy

只渲染可视区域数据，按需加载：

1. 用户操作 → React 组件更新 Viewport 状态
2. Viewport 变化 → 计算可见深度/坐标范围
3. 可见范围变化 → 向后端请求对应数据块
4. 数据返回 → Renderer.setData() 渲染
5. 缩放过程中前端用已缓存数据做低精度预览，后台加载高精度数据后替换
6. **高性能传输**: 使用 **Apache Arrow** 格式传输采样点数据。后端将 float 数组打包为 Arrow RecordBatch，前端使用 `arrow-js` 零拷贝读取。

### 3.3 Shared Modules

| 模块 | 职责 |
|------|------|
| `ColorMap` | 地质色标管理（Jet/Rainbow/Gray/地质专用色标） |
| `AxisBuilder` | 深度轴、X/Y轴、比例尺、图例生成 |
| `DataCache` | LRU缓存，存储已加载数据块，避免重复请求 |
| `CoordSystem` | 数据坐标系 ↔ 屏幕像素坐标转换 |

**Memory Management Note**:
为了避免 React 状态追踪导致的大规模数据重渲染延迟，所有的原始数值数据（如测井曲线点集、地震采样数组）应存储在 `Ref` 或全局数据存储中，而非直接存入 `useState/Zustand`。Zustand 仅维护数据的元数据、加载状态和 Viewport 参数。

### 3.4 Page Routing — 独立页面架构

每种可视化类型是独立的处理页面，不强行融合多种图示在同一页面。

```
/ (首页/仪表盘)
  ├─ /well-log          测井可视化页面（独立）
  ├─ /seismic           地震剖面页面（独立，V1.1）
  ├─ /contour           等值线图页面（独立，V1.1）
  └─ /3d-viewer         三维地质页面（独立，V2）
```

每个页面独立加载数据、独立管理状态、独立渲染。页面间通过侧边栏导航切换。
这简化了组件复杂度和状态管理 — 不存在跨图示类型的数据耦合。

### 3.5 Well Log Visualization (V1 Priority)

**组件树**：
```
WellLogPage (独立路由页面)
  └─ WellLogViewer
       ├─ DepthAxis          深度轴（左侧）
       ├─ TrackColumn[]      测井道数组
       │    ├─ TrackHeader   道标题 + 曲线名
       │    ├─ CurveRenderer Canvas 2D曲线渲染
       │    ├─ CurveFill     曲线间填充
       │    └─ TrackAxis     道内X轴刻度
       ├─ LithologyColumn    岩性柱状图
       └─ TrackToolbar       道操作工具栏
```

**交互**：
- 鼠标滚轮：深度缩放（以鼠标位置为中心）
- 鼠标拖拽：上下平移
- 道边界拖拽：调整道宽
- 右键菜单：选择曲线、设置颜色/线型/刻度范围
- Ctrl+点击：添加层位标记
- 双击曲线：显示该点精确数值

**渲染性能要求**：
- 单口井10000个采样点，5条曲线同时显示，帧率≥30fps
- 10口井对比，每口5000采样点，帧率≥30fps
- 1000口井列表加载≤8s（仅加载元数据+索引）

## 4. Backend Design

### 4.1 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/data/import` | 上传数据文件（LAS/SEG-Y/CSV） |
| GET | `/api/well-log/list` | 获取井列表（含元数据） |
| GET | `/api/well-log/{id}` | 获取单口井数据（支持分页） |
| GET | `/api/well-log/{id}/curves` | 获取曲线数据（指定深度范围） |
| GET | `/api/system/status` | 服务状态检查 |
| POST | `/api/data/generate` | 生成合成测试数据 |
| POST | `/api/export` | 导出图件（PNG/SVG/PDF） |

**分页参数**（用于大数据量）：
```
GET /api/well-log/{id}/curves?depth_start=100&depth_end=200&max_points=5000
```

**Content Negotiation**:
API 会根据请求头 `Accept` 返回不同格式：
- `application/json`: 返回标准 JSON 数据（适合元数据和少量点）
- `application/vnd.apache.arrow`: 返回 Arrow 格式数据（大批量采样点推荐）

### 4.2 Data Models

```python
class WellLogData(BaseModel):
    well_id: str
    well_name: str
    depth_start: float
    depth_end: float
    depth_step: float
    location: Optional[Tuple[float, float]]  # (x, y)坐标
    curves: List[CurveData]

class CurveData(BaseModel):
    name: str          # "GR", "RT", "DEN", "NPHI"
    unit: str          # "API", "ohm.m", "g/cc", "%"
    data: List[float]  # 采样值数组
    depth: List[float] # 对应深度数组
    min_value: float
    max_value: float
    display_range: Tuple[float, float]
    color: str         # 默认颜色
    line_style: str    # "solid" | "dashed" | "dotted"

class WellMetadata(BaseModel):
    well_id: str
    well_name: str
    depth_start: float
    depth_end: float
    curve_names: List[str]
    file_path: str
    file_size: int
    import_time: datetime

class ExportRequest(BaseModel):
    format: str         # "png" | "svg" | "pdf"
    width: int
    height: int
    dpi: int = 150
    include_legend: bool = True
    include_title: bool = True
    title: Optional[str]
```

### 4.3 Synthetic Data Generator

由于没有样品数据，V1 需要一个模拟数据生成器：

**测井曲线模拟**：
- GR（自然伽马）：基线 ~80 API，砂岩降低至 ~30，泥岩升高至 ~120
- RT（电阻率）：基线 ~10 ohm.m，含油气层升高至 ~100+
- DEN（密度）：基线 ~2.5 g/cc，煤层降低至 ~1.8
- NPHI（中子孔隙度）：基线 ~0.15，孔隙带升高至 ~0.30

**地质特征模拟**：
- 砂岩段：GR低 + DEN中等 + NPHI中等
- 泥岩段：GR高 + DEN中等 + RT低
- 煤层：GR低 + DEN极低 + RT高 + NPHI高
- 含油气层：RT异常高

**默认生成**：10口模拟井，每口3000m，步长0.125m（24000采样点）

### 4.4 Large File Handling (SEG-Y)

- segyio 使用 `mmap` 内存映射，不全量读入内存
- 首次打开 SEG-Y 时生成 trace 索引文件（.idx），后续查询毫秒级
- 前端请求单个 inline 剖面时，后端只切片返回该部分
- 索引文件缓存到数据目录，避免重复生成

## 5. Tech Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Desktop Shell | Tauri | 2.x | Rust壳，窗口+进程管理 |
| UI Framework | React | 18+ | 组件化UI |
| Language | TypeScript | 5.x | 类型安全 |
| Build Tool | Vite | 5.x | 前端构建 |
| State | Zustand | 4.x | 轻量状态管理 |
| 2D Rendering | Canvas 2D + D3.js | v7 | 测井曲线、道图 |
| Large-scale | deck.gl | 9.x | 地震剖面、等值线(V1.1) |
| SVG Interaction | D3.js | v7 | 岩性符号、平面图编辑 |
| 3D | Three.js | r160+ | 三维地质(V2) |
| Styling | TailwindCSS | 3.x | UI样式 |
| Icons | Lucide React | latest | 图标 |
| Backend | FastAPI | 0.100+ | Python API |
| ASGI | uvicorn | latest | Python服务 |
| Well Log | lasio | 0.30+ | LAS格式解析 |
| Seismic | segyio | 1.9+ | SEG-Y格式解析 |
| Science | scipy/numpy | latest | 等值线/插值 |
| Data Serialization | Apache Arrow | latest | 高性能科学计算并行传输 (pyarrow/arrow-js) |
| Data Model | Pydantic | 2.x | 数据校验 |
| Test (FE) | Vitest + Testing Library | latest | 前端测试 |
| Test (BE) | pytest | latest | 后端测试 |
| i18n | i18next | latest | 中英双语 |

## 6. V1 Delivery Scope

### Phase 1: Project Scaffold (Week 1-2)

- [ ] Tauri 2.x + React + Vite + TypeScript 项目骨架
- [ ] FastAPI 后端骨架 + 健康检查API
- [ ] 合成数据生成器（10口模拟井）
- [ ] 前后端通信（dev模式启动脚本）
- [ ] 基础UI布局（侧边栏井列表 + 工作区 + 状态栏）
- [ ] i18n 基础配置（中英双语）

### Phase 2: Well Log MVP (Week 3-6)

- [ ] Canvas 2D 曲线渲染器
- [ ] 多道测井道图布局（深度轴 + N个道列）
- [ ] 深度缩放（鼠标滚轮，以光标为中心）
- [ ] 道宽拖拽调整
- [ ] 多曲线叠加（GR/RT/DEN/NPHI，不同颜色/线型）
- [ ] LAS文件上传和解析
- [ ] 合成数据加载和显示

### Phase 3: Well Log Enhancement (Week 7-9)

- [ ] 多井对比展示（水平排列，层位对齐标记）
- [ ] 曲线间填充（砂岩/泥岩区分着色）
- [ ] 右键上下文菜单（曲线选择、颜色设置、刻度调整）
- [ ] 岩性柱状图叠加（SVG符号，覆盖主要岩性类型≥30种）
- [ ] 图例、比例尺、坐标系信息显示
- [ ] 曲线悬停tooltip（显示精确数值）

### Phase 4: Export & Polish (Week 10-11)

- [ ] PNG 导出（含图例和标题）
- [ ] SVG 导出
- [ ] PDF 导出（后端 WeasyPrint 或前端 html2canvas + jsPDF）
- [ ] 打印预览
- [ ] 性能优化（1000口井列表加载测试）
- [ ] UI打磨和细节修复

### V1 Acceptance Criteria

| 场景 | 标准 |
|------|------|
| 单井5曲线渲染 | 10000采样点，帧率≥30fps |
| 多井对比 | 10口井同屏，帧率≥30fps |
| 井列表加载 | 1000口井元数据加载≤8s |
| LAS文件导入 | 标准LAS 2.0/3.0格式，≤5s解析 |
| 图件导出 | PNG/SVG/PDF，含图例比例尺 |
| 岩性符号 | 覆盖主要岩性类型≥30种 |
| 界面语言 | 中英双语切换 |

## 7. Future Phases (Post V1)

### V1.1: Seismic + Contour

- 地震剖面渲染（WebGL + segyio）
- 地震水平切片
- 等值线/填色图（D3.js + scipy）
- 任意线切割

### V2: 3D + Advanced

- 三维地质体渲染（Three.js + WebGPU）
- 井轨迹三维展示（CesiumJS）
- 平面图交互编辑（SVG + D3.js）
- 多用户协作支持

## 8. Risks & Mitigations

| Risk | Level | Mitigation |
|------|-------|------------|
| Canvas 2D 大数据量性能 | Low | 虚拟化渲染 + 按需加载 + 降采样 |
| PyInstaller 打包体积大(~200MB) | Medium | 使用 UPX 压缩；考虑 Nuitka 作为备选 |
| Rust-Tauri 学习曲线 | Medium | Tauri 2.x 文档完善，Rust侧代码量少（主要是进程管理） |
| SEG-Y 格式多样性 | Medium | segyio 处理大多数变体；异常格式添加 fallback |
| Windows WebView2 兼容性 | Low | Win10/11 已预装；Tauri 支持自动引导安装 |
| 招聘前端 WebGL 人才 | Medium | Three.js/CesiumJS 开发者比 OpenGL 更易招 |
| 模拟数据与真实数据差异 | Medium | 设计好数据接口，后端适配器模式切换 |
| 数据序列化瓶颈 (JSON) | High | 引入 Apache Arrow 实现零拷贝序列化与二进制传输 |
| 跨进程本地 API 攻击 | Medium | 采用动态生成 Auth Token 并在进程间加密传递 |
