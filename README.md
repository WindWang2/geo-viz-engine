# GeoViz Engine — 地质数据可视化桌面引擎

![Tauri](https://img.shields.io/badge/Tauri-2.10.3-blue?logo=tauri)
![React](https://img.shields.io/badge/React-18.3.1-61DAFB?logo=react)
![TypeScript](https://img.shields.io/badge/TypeScript-5.6.3-3178C6?logo=typescript)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-009688?logo=fastapi)
![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python)
![License](https://img.shields.io/badge/License-MIT-green)

面向地质工程师和科研人员的**跨平台桌面应用**，提供测井数据可视化与分析功能。

---

## About / 项目简介

GeoViz Engine 是一款基于 **Tauri 2.x + React + Python FastAPI** 的地质数据可视化桌面应用，采用三层架构设计：

- **桌面壳（Rust/Tauri）**：窗口管理、安全 API Token 分发、Python sidecar 进程管理
- **前端渲染（React/Web）**：用户界面、状态管理、路由、国际化
- **后端计算（Python）**：REST API、地质数据处理、合成数据生成

目标用户：地质工程师、测井分析人员、地球科学领域科研人员。

---

## Architecture / 技术架构

```
┌─────────────────────────────────────────────────────┐
│               Desktop Shell (Tauri 2.x / Rust)       │
│   窗口管理 · API Token 安全生成与分发 · 进程管理      │
└───────────────┬────────────────────┬─────────────────┘
                │  WebView           │  Sidecar (IPC)
┌───────────────▼──────┐  ┌──────────▼──────────────────┐
│   Frontend (React)    │  │   Backend (Python FastAPI)   │
│                       │  │                              │
│  React 18 + Vite      │  │  REST API · 数据处理          │
│  TypeScript           │  │  numpy · pyarrow · lasio     │
│  Zustand (状态管理)    │◄─►  合成数据生成                 │
│  React Router 7       │  │  AuthToken 中间件             │
│  TailwindCSS          │  │                              │
│  i18next (中/英)      │  └──────────────────────────────┘
└───────────────────────┘
```

### Tech Stack / 完整技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 桌面壳 | Tauri | 2.10.3 |
| 前端框架 | React | 18.3.1 |
| 语言 | TypeScript | 5.6.3 |
| 构建工具 | Vite | 5.4.10 |
| 图表渲染 | D3.js | 7.x |
| 地图 | MapLibre GL | 4.x |
| 状态管理 | Zustand | 4.5.0 |
| 样式 | TailwindCSS | 3.4.14 |
| 路由 | React Router | 7.0.2 |
| 国际化 | i18next | 23.7.6 |
| 后端框架 | FastAPI | 0.115.0 |
| 数据验证 | Pydantic | 2.9.2 |
| 数值计算 | numpy | 2.1.3 |
| 列式数据 | pyarrow | 18.0.0 |
| LAS 解析 | lasio | 0.30 |
| 坐标转换 | pyproj | 3.7.x |

---

## Features / 功能模块

### Phase 1 已实现功能

**认证与安全**
- `AuthTokenMiddleware`：Tauri 启动时生成 32 位随机 token，通过环境变量安全传递给 Python 后端
- 所有 API 请求需携带 `X-API-Token` 请求头

**系统 API**
- `GET /api/system/status`：返回版本、运行时间、Python 环境信息

**测井数据 API**
- `GET /api/data/wells`：返回合成井列表（10 口模拟井）
- `GET /api/data/wells/{well_id}/curves`：返回指定井的曲线数据（GR / RT / DEN / NPHI）
- `GET /api/data/laolong1`：返回老龙1井完整测井解释数据（11 个 XLS sheet 解析）
- `GET /api/data/real-wells`：返回真实井位坐标（EPSG:4326）

**老龙1井 D3+SVG 综合测井解释图**
- 14 列 D3.js 统一 SVG 渲染：地层系统、测井曲线（AC/GR、RT/RXO、SH/PERM/PHIE）、深度标尺、岩性（SVG 花纹）、岩性描述、沉积相、体系域、层序
- 每列 `<clipPath>` 防止内容溢出
- 文字按列宽自动换行（中文 0.85em 字符宽度估算）
- 学术风格表头：合并单元格、曲线图例、交替列底色、精细网格线

**岩性 SVG 花纹**
| 岩性 | 花纹 |
|------|------|
| 白云岩 | 菱形网格 |
| 砂岩 | 点状 |
| 粉砂岩 | 细点 |
| 泥岩 | 虚线 |
| 页岩 | 实线 |
| 灰岩 | 砖块 |

**交互功能**
- 沉积相（微相/亚相/相）点击弹出 prompt 编辑名称，实时更新图表
- 岩性描述点击编辑
- 鼠标悬停显示十字准线 + tooltip：当前深度、7 条曲线插值、岩性、微相/亚相/相
- `getScreenCTM()` 精确坐标转换，事件命名空间 `.laolong1` 避免冲突

**导出**
- SVG：矢量导出，自动移除交互层
- PNG：高 DPI Canvas 渲染（3x）
- PDF：浏览器原生 `window.print()` 输出矢量 PDF，完美支持中文

**地图井位显示**
- 56 口真实井位坐标（EPSG:2436 → WGS84 转换），地图上绿色圆点展示
- 10 口合成模拟井蓝色圆点展示

**合成数据生成**
- 基于 numpy 生成 10 口模拟井数据
- 每口井包含四条标准测井曲线（自然伽马、电阻率、密度、中子）

**前端 UI**
- `AppLayout` 三栏布局：Sidebar + 主内容区 + StatusBar
- Toolbar 工具栏、首页（HomePage）、测井页面（WellLogPage）、地图页面（MapHomePage）
- 中英双语 i18n 支持（`en.json` / `zh.json`）

**状态管理**
- `useWellStore`：井数据的全局状态
- `useSettingsStore`：应用设置状态

---

## Roadmap / 开发路线图

| 阶段 | 状态 | 内容 |
|------|------|------|
| Phase 1 | ✅ 已完成 | 项目骨架、三层架构、认证、基础 API、合成数据 |
| Phase 2 | ✅ 已完成 | 老龙1井 D3+SVG 综合测井解释图、交互编辑、悬停提示、地图井位 |
| Phase 3 | 🔜 计划中 | 多井对比、LAS 文件上传与解析 |
| Phase 4 | 📋 待规划 | 地震数据可视化（segyio） |
| Phase 5 | 📋 待规划 | 三维可视化（Three.js / CesiumJS） |

---

## Quick Start / 快速开始

### 前置条件

- [Rust](https://rustup.rs/) (stable)
- Node.js 18+
- Python 3.12+
- 系统依赖（WebView2 / libwebkit2gtk）：参考 [Tauri 先决条件文档](https://tauri.app/start/prerequisites/)

### 开发模式

```bash
# 1. 克隆项目
git clone <repo-url>
cd geo-viz-engine

# 2. 安装前端依赖
cd src-web && npm install && cd ..

# 3. 创建 Python 虚拟环境并安装依赖
cd src-python
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cd ..

# 4. 一键启动（Python 后端 + Vite 前端 + Tauri 桌面壳）
./scripts/dev.sh
```

### 生产构建

```bash
./scripts/build.sh
```

---

## Project Structure / 项目结构

```
geo-viz-engine/
├── src-tauri/              # Tauri 桌面壳 (Rust)
│   ├── src/
│   │   ├── lib.rs          # Tauri 配置、sidecar 启动、token 生成
│   │   └── main.rs
│   ├── binaries/           # Python sidecar 构建产物
│   └── tauri.conf.json
├── src-web/                # React 前端
│   └── src/
│       ├── pages/          # HomePage, MapHomePage, WellLogPage, LaoLong1Page
│       ├── components/
│       │   ├── well-log/   # LaoLong1Chart, LaoLong1Dashboard, FaciesTrack, WellLogDashboard
│       │   ├── map/        # WellMap (MapLibre GL)
│       │   ├── layout/     # Sidebar, Toolbar, StatusBar
│       │   └── common/     # 通用组件
│       ├── stores/         # useWellStore, useSettingsStore
│       ├── hooks/          # useApi
│       ├── i18n/           # en.json, zh.json
│       └── router.tsx
├── src-python/             # FastAPI 后端
│   └── app/
│       ├── api/            # system.py, data.py
│       ├── models/         # well_log.py, common.py
│       ├── services/       # data_generator.py, laolong1_loader.py
│       ├── auth.py         # AuthTokenMiddleware
│       └── main.py
├── scripts/                # dev.sh, build.sh, convert_coordinates.py
├── data/                   # well_coordinates.json, generated/
└── docs/                   # 设计文档
```

---

## Testing / 测试

| 层级 | 框架 | 数量 | 覆盖范围 |
|------|------|------|----------|
| Python 后端 | pytest | 36 tests | API、数据模型、认证、数据生成 |
| React 前端 | vitest + @testing-library/react | 39 tests | 组件、页面、hooks、stores、i18n |
| TypeScript | tsc | — | 零编译错误 |
| Rust | cargo check | — | 编译通过 |

```bash
# Python 后端测试
cd src-python && source venv/bin/activate && pytest

# React 前端测试
cd src-web && npm test

# Rust 编译检查
cd src-tauri && cargo check
```

---

## API Overview / API 概览

所有请求需携带 `X-API-Token` 请求头（由 Tauri 在运行时注入）。

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/system/status` | 系统状态（版本、运行时间、环境） |
| `GET` | `/api/data/wells` | 获取合成井列表 |
| `GET` | `/api/data/wells/{well_id}/curves` | 获取指定井的测井曲线数据 |
| `GET` | `/api/data/well-detail/{well_name}` | 获取井详情数据（Excel 解析） |
| `GET` | `/api/data/laolong1` | 获取老龙1井完整测井解释数据 |
| `GET` | `/api/data/real-wells` | 获取真实井位坐标（WGS84） |
| `POST` | `/api/data/generate` | 生成合成测井数据 |

---

## License

[MIT](LICENSE)
