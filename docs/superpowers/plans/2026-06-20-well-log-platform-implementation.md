# Well-Log Platform Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 geo-viz-engine 从"单井列表"重构为"地图 + 双栏详情面板"交互，首阶段交付 MVP（地图打点 + 点击弹详情 Panel + 平行表格页）。

**Architecture:** 后端仅新增坐标 mock 字段；前端新增 MapLibre 地图页、共用 DetailPanel（覆在首页之上）、平行表格页；全剧共用 Zustand store 管理选井/Panel 状态。

**Tech Stack:** maplibre-gl v4, zustand, react-router-dom v6, tippy.js v6（Phase 2 tooltip）, 原 React/Tailwind 生态不变。

---

## File Map

### 新建文件
- `src-web/src/pages/MapHomePage.tsx` — 首页地图主体
- `src-web/src/pages/WellTablePage.tsx` — 平行表格页
- `src-web/src/components/map/WellMap.tsx` — MapLibre 地图组件（封装 marker 打点、popup）
- `src-web/src/components/map/MapPopover.tsx` — 井点 popup 小卡片
- `src-web/src/components/panel/DetailPanel.tsx` — 右滑详情面板容器
- `src-web/src/hooks/useKeyboardClose.ts` — ESC 关闭 panel 自定义 hook
- `src-web/src/stores/useMapStore.ts` — 新 Zustand store（Panel open/close, selectedWellId）

### 修改文件
- `src-python/app/models/well_log.py` — `WellMetadata` / `WellLogData` 加 `longitude`/`latitude`/`intervals`
- `src-python/app/services/data_generator.py` — mock 生成经纬度
- `src-web/src/store/useWellStore.ts` — 扩展字段（选井状态、panel 状态）
- `src-web/src/components/well-log/types.ts` — TS 接口加坐标字段
- `src-web/src/components/layout/AppLayout.tsx` — 移除 sidebar 或改造
- `src-web/src/router.tsx` — 更新路由表，增加 `/table`
- `src-web/src/components/common/Sidebar.tsx` — 替换为 BottomTabBar
- `src-web/src/components/common/BottomTabBar.tsx` — 新建，地图/表格 Tab 切换
- `src-web/src/i18n/zh.json` & `en.json` — 新增翻译 key
- `src-web/package.json` — 新增 `maplibre-gl`, `tippy.js`
- `src-web/vite.config.ts` — 如需要别名调整
- `src-python/tests/test_api_data.py` — 坐标字段测试
- `src-python/tests/test_models.py` — coordinate fields validation

---

## TASK 1: 后端模型加坐标字段

**Files:**
- Modify: `src-python/app/models/well_log.py`
- Test: `src-python/tests/test_models.py`

- [ ] **Step 1: 修改 `WellMetadata` 类，加入经纬度字段**

在 `class WellMetadata(BaseModel)` 中，在现有字段下方添加：

```python
class WellMetadata(BaseModel):
    well_id: str
    well_name: str
    depth_start: float
    depth_end: float
    curve_names: List[str]
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
```

> 注意：保持与其他 Optional 字段一致的写法 `Optional[float] = None`。

- [ ] **Step 2: 在 `WellLogData` 中也加入相同字段**

在 `WellLogData` 的 `location` 字段附近加上：

```python
    location: Optional[Tuple[float, float]] = None
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
```

- [ ] **Step 3: 运行测试验证向后兼容**

Run: `cd ~/projects/geo-viz-engine && python -m pytest src-python/tests/test_models.py -v`
Expected: 所有测试 PASS（包括原有的，不因新字段断裂）

---

## TASK 2: 后端 data_generator 添加 mock 坐标

**Files:**
- Modify: `src-python/app/services/data_generator.py`
- Test: `src-python/tests/test_api_data.py`

前置：需要 `random` 库（已在文件顶部 import time，说明可以 import random）。

- [ ] **Step 1: 在 `generate_well_log` 函数签名中加入 `rng` 参数（或在函数内新建 rng）**

为了可复现性，坐标也应该基于 seed。当前函数已经有 `seed: int = 42`，利用它派生坐标。

在 `def generate_well_log(...)` 函数体内，`depths` 构建之后（大约在第 25-28 行之间），加入：

```python
    # Generate deterministic mock coordinates (Chongqing East region)
    lng = round(106.0 + (seed % 1000) / 1000.0 * 2.5, 6)   # 106.0 ~ 108.5°E
    lat = round(28.0 + (seed % 777) / 777.0 * 2.5, 6)     # 28.0 ~ 30.5°N
```

这样 seed 不同 → 不同的井有不同的坐标，同一个 seed 永远产生相同的坐标（可复现）。

- [ ] **Step 2: 把坐标注入返回值**

在 `return WellLogData(...)` 调用中，加上两个新字段：

```python
    return WellLogData(
        ...
        location=None,
        longitude=lng,
        latitude=lat,
        curves=curves,
        ...
    )
```

- [ ] **Step 3: 更新 `generate_wells` 中的循环（如果需要）**

`generate_wells` 里调用 `generate_well_log(base + i * 42 + 7, ...)` 已经带着 seed，坐标会自动派生，无需额外修改。

- [ ] **Step 4: 运行测试验证**

Run: `cd ~/projects/geo-viz-engine && python -m pytest src-python/tests/test_api_data.py -v -k "coordinate or meta or metadata or well_id"`
Expected: 测试应通过，且 `well["longitude"]` 和 `well["latitude"]` 现在存在于返回 JSON 中。

补充检查：在 Python REPL 中快速验证：
```python
cd ~/projects/geo-viz-engine && source venv/bin/activate
python -c "
from app.services.data_generator import generate_well_log
w = generate_well_log('TEST-1', 'Test Well', seed=42)
print(f'lng={w.longitude}, lat={w.latitude}')
"
```
Expected 输出类似 `lng=106.xxx, lat=28.xxx`

---

## TASK 3: 前端安装依赖

**Files:**
- Modify: `src-web/package.json`

- [ ] **Step 1: 安装 maplibre-gl 和 tippy.js**

Run: `cd ~/projects/geo-viz-engine/src-web && npm install maplibre-gl tippy.js`
Expected: 无 ERROR，package.json 和 package-lock.json 均更新成功。

- [ ] **Step 2: 检查 vite 配置**

确认 `vite.config.ts` 不需要额外 plugin 就能使用 maplibre-gl（通常不需要）。如有疑问，检查官方文档：maplibre-gl 在 Vite 中可以直接 `import 'maplibre-gl/dist/maplibre-gl.css'` 使用。

- [ ] **Step 3: tsconfig 检查**

确保 `"types": [..., "vite/client"]` 存在（已有的），不需要改动。

---

## TASK 4: TypeScript 接口扩充 + Zustand Store 新建

**Files:**
- Modify: `src-web/src/components/well-log/types.ts`
- Create: `src-web/src/stores/useMapStore.ts`
- Modify: `src-web/src/stores/useWellStore.ts`（新增 selectedWellId / panelOpen 字段）

---

### TASK 4A: TypeScript 类型扩容

- [ ] **Step 1: 给 `WellMetadata` 接口加上坐标字段**

```typescript
export interface WellMetadata {
  // ...existing fields...
  well_id: string;
  well_name: string;
  depth_start: number;
  depth_end: number;
  curve_names: string[];
  longitude?: number | null;
  latitude?: number | null;
}
```

### TASK 4B: 新建 useMapStore（Panel 状态管理）

- [ ] **Step 2: 创建 `src-web/src/stores/useMapStore.ts`**

```typescript
import { create } from 'zustand';

interface MapState {
  selectedWellId: string | null;
  panelOpen: boolean;

  selectWell: (wellId: string) => void;
  closePanel: () => void;
  openPanel: () => void;
  togglePanel: () => void;
}

export const useMapStore = create<MapState>((set) => ({
  selectedWellId: null,
  panelOpen: false,

  selectWell: (wellId) =>
    set({ selectedWellId: wellId, panelOpen: true }),

  closePanel: () =>
    set({ panelOpen: false }),   // keep selectedWellId for re-open

  openPanel: () =>
    set((state) =>
      state.selectedWellId ? { panelOpen: true } : {}
    ),

  togglePanel: () =>
    set((state) => ({ panelOpen: !state.panelOpen })),
}));
```

---

## TASK 5: 建立 BottomTabBar（地图/表格导航）

**Files:**
- Create: `src-web/src/components/common/BottomTabBar.tsx`
- Modify: `src-web/src/components/common/Sidebar.tsx`
- Modify: `src-web/src/components/layout/AppLayout.tsx`

> 如果 AppLayout 高度允许，把导航条放在页面右上角或底部均可。本项目选用**页面顶部右侧**水平 Tab，符合现代 SPA 设计语言。

### TASK 5A: BottomTabBar 组件

- [ ] **Step 1: 创建 `src-web/src/components/common/BottomTabBar.tsx`**

```tsx
import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Map, Table2 } from 'lucide-react';

const tabs = [
  { to: '/',         icon: <Map size={16} />,    labelKey: 'nav.map' },
  { to: '/table',    icon: <Table2 size={16} />, labelKey: 'nav.table' },
];

export default function BottomTabBar() {
  const { t } = useTranslation();

  return (
    <div className="flex items-center gap-1 bg-geo-surface border border-geo-border rounded-lg p-1">
      {tabs.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.to === '/'}
          className={({ isActive }) =>
            `flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors ${
              isActive
                ? 'bg-geo-accent text-white'
                : 'text-geo-muted hover:text-geo-text hover:bg-geo-accent/10'
            }`
          }
        >
          {tab.icon}
          <span>{t(tab.labelKey)}</span>
        </NavLink>
      ))}
    </div>
  );
}
```

### TASK 5B: 国际化 key

- [ ] **Step 2: 在 zh.json 和 en.json 加入翻译**

zh.json 增加：
```json
  "nav.map": "地图",
  "nav.table": "表格"
```
en.json 增加：
```json
  "nav.map": "Map",
  "nav.table": "Table"
```

### TASK 5C: AppLayout 简化

- [ ] **Step 3: 修改 `AppLayout.tsx`**，使其变成纯全屏容器，去掉左侧 Sidebar（因为导航已改为 Top Tab）

将现有 AppLayout 内容替换为：
```tsx
export default function AppLayout() {
  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-geo-bg">
      <header className="flex-initial flex items-center justify-end px-4 py-2 border-b border-geo-border bg-geo-surface">
        <BottomTabBar />
      </header>
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
```
（需要 import `Outlet` from `react-router-dom`，以及 import `BottomTabBar`）

- [ ] **Step 4: 删除或注释 `Sidebar` import**（不再在 AppLayout 中使用）

---

## TASK 6: WellMap 地图组件（MapLibre GL）

**Files:**
- Create: `src-web/src/components/map/WellMap.tsx`
- Modify: `src-web/src/pages/MapHomePage.tsx`（使用 WellMap）

### TASK 6A: WellMap.tsx 主体

- [ ] **Step 1: 创建基础 MapLibre 地图组件**

```tsx
import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { WellMetadata } from '../well-log/types';

interface WellMapProps {
  wells: WellMetadata[];
  onWellClick: (wellId: string) => void;
  selectedWellId?: string | null;
}

const DFLT_CENTER: [number, number] = [107.0, 29.0];
const DFLT_ZOOM = 7;

export default function WellMap({ wells, onWellClick, selectedWellId }: WellMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          'osm': {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '© OpenStreetMap contributors',
          },
        },
        layers: [
          {
            id: 'osm',
            type: 'raster',
            source: 'osm',
            minzoom: 0,
            maxzoom: 19,
          },
        ],
      },
      center: DFLT_CENTER,
      zoom: DFLT_ZOOM,
    });

    mapRef.current = map;

    // Cleanup
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Add / update markers whenever wells prop changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.loaded()) return;

    // Clear old markers
    const markers = (map as any)._markers || [];
    markers.forEach((m: any) => m.remove());
    (map as any)._markers = [];

    wells.forEach((well) => {
      if (well.longitude == null || well.latitude == null) return;

      // Color by selection
      const el = document.createElement('div');
      el.className = 'well-marker';
      el.style.cssText = `
        width: 12px; height: 12px;
        background: ${well.well_id === selectedWellId ? '#ef4444' : '#3b82f6'};
        border-radius: 50%;
        border: 2px solid white;
        cursor: pointer;
        box-shadow: 0 1px 4px rgba(0,0,0,0.3);
      `;
      el.title = well.well_name;

      new maplibregl.Marker(el)
        .setLngLat([well.longitude, well.latitude])
        .setPopup(
          new maplibregl.Popup({ offset: 15 }).setHTML(
            `<b>${well.well_name}</b><br/><small>${well.well_id}</small>`
          )
        )
        .addTo(map);

      el.addEventListener('click', () => onWellClick(well.well_id));

      (map as any)._markers = [(map as any)._markers || [], markers].flat();
    });
  }, [wells, selectedWellId]);

  return (
    <div
      ref={mapContainer}
      className="w-full h-full"
      style={{ minHeight: '400px' }}
    />
  );
}
```

> 注：上述 useEffect 中 markers cleanup 是简化实现。如 maplibre 版本提供了 `map.markers` 集合，用官方 API 更稳妥。可以后续优化。

- [ ] **Step 2: 确认 css import 不会冲突**

在 `src-web/src/index.css` 中若无 `@import 'maplibre-gl/dist/maplibre-gl.css';` 就补一条，确保地图字体正常。

---

## TASK 7: DetailPanel（右滑详情面板）

**Files:**
- Create: `src-web/src/components/panel/DetailPanel.tsx`
- Hook: `src-web/src/hooks/useKeyboardClose.ts`
- Modify: `src-web/src/pages/MapHomePage.tsx`

### TASK 7A: useKeyboardClose Hook

- [ ] **Step 1: 创建 `src-web/src/hooks/useKeyboardClose.ts`**

```typescript
import { useEffect } from 'react';

export function useKeyboardClose(onClose: () => void, enabled: boolean = true) {
  useEffect(() => {
    if (!enabled) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose, enabled]);
}
```

### TASK 7B: DetailPanel 组件

- [ ] **Step 2: 创建 `src-web/src/components/panel/DetailPanel.tsx`**

```tsx
import { useCallback } from 'react';
import { X, ChevronLeft } from 'lucide-react';
import { WellLogDashboard } from '../well-log';
import type { WellLogData } from '../well-log/types';
import { useKeyboardClose } from '../../hooks/useKeyboardClose';

interface DetailPanelProps {
  wellId: string;
  wellName: string;
  wellData: WellLogData | null;
  open: boolean;
  loading?: boolean;
  error?: string | null;
  onClose: () => void;
  onBack: () => void;
}

export default function DetailPanel({
  wellId,
  wellName,
  wellData,
  open,
  loading = false,
  error = null,
  onClose,
}: DetailPanelProps) {
  useKeyboardClose(onClose, open);

  if (!open) return null;

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 bg-black/10 z-40"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <aside
        className="fixed right-0 top-0 h-full bg-white border-l border-geo-border shadow-xl z-50
                   flex flex-col w-[55vw] min-w-[380px]"
        style={{ maxWidth: '55vw' }}
      >
        {/* Header */}
        <div className="flex-shrink-0 flex items-center gap-2 px-4 py-3 border-b border-geo-border bg-geo-surface">
          <button
            onClick={onClose}
            title="返回地图"
            className="flex items-center gap-1 text-sm text-geo-accent hover:text-geo-accent/80 transition-colors"
          >
            <ChevronLeft size={18} />
            <span>返回</span>
          </button>
          <div className="flex-1 text-center font-semibold text-geo-text text-base">
            {wellName}
          </div>
          <button
            onClick={onClose}
            title="关闭"
            className="p-1 rounded hover:bg-geo-accent/10 text-geo-muted transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Meta strip */}
        {!loading && wellData && (
          <div className="flex-shrink-0 px-4 py-1.5 text-xs text-geo-muted bg-geo-surface/50 border-b border-geo-border">
            深度 {wellData.depth_start.toFixed(1)} - {wellData.depth_end.toFixed(1)} m
            {' · '}{wellData.curves.map((c) => c.name).join(', ')}
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-hidden">
          {error && (
            <div className="p-4 m-4 bg-geo-red/10 border border-geo-red/30 rounded-lg text-geo-red text-sm">
              {error}
            </div>
          )}
          {loading && (
            <div className="flex items-center justify-center h-full text-geo-muted text-sm">
              加载中...
            </div>
          )}
          {wellData && !loading && (
            <WellLogDashboard data={wellData} />
          )}
        </div>
      </aside>
    </>
  );
}
```

> 注意：这个 Panel 是**绝对定位浮层**，不干扰底下地图的 DOM tree，故不需要 Portal。

---

## TASK 8: MapHomePage 组装

**Files:**
- Create: `src-web/src/pages/MapHomePage.tsx`
- Modify: `src-web/src/stores/useMapStore.ts`（确认 API 一致）

### TASK 8A: MapHomePage.tsx

- [ ] **Step 1: 创建完整组装页面**

```tsx
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useWellStore } from '../stores/useWellStore';
import { useMapStore } from '../stores/useMapStore';
import { useApi } from '../hooks/useApi';
import WellMap from '../components/map/WellMap';
import DetailPanel from '../components/panel/DetailPanel';
import type { WellLogData } from '../components/well-log';

export default function MapHomePage() {
  const { t } = useTranslation();
  const { wells, setWells } = useWellStore();
  const { panelOpen, selectedWellId, selectWell, closePanel } = useMapStore();
  const { request } = useApi();

  const [wellData, setWellData] = useState<WellLogData | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  // Load wells list on mount
  useEffect(() => {
    if (wells.length > 0) return;
    (async () => {
      try {
        const data = await request<any[]>('/api/data/list');
        if (Array.isArray(data) && data.length > 0) {
          setWells(data);
        } else {
          // Trigger generation if no cached wells
          const gen = await request<any>('/api/data/generate', { method: 'POST' });
          setWells(gen?.wells ?? []);
        }
      } catch {
        // Silently fail on initial load
      }
    })();
  }, []);

  // Watch selectedWellId → fetch full well data
  useEffect(() => {
    if (!selectedWellId) {
      setWellData(null);
      return;
    }
    setDetailLoading(true);
    setDetailError(null);
    request<WellLogData>(`/api/data/well/${selectedWellId}`)
      .then(setWellData)
      .catch((e) => setDetailError(e?.message ?? '加载失败'))
      .finally(() => setDetailLoading(false));
  }, [selectedWellId, request]);

  const selectedWell = wells.find((w) => w.well_id === selectedWellId);
  const selectedWellName = selectedWell?.well_name ?? selectedWellId ?? '';

  return (
    <div className="relative w-full h-full overflow-hidden">
      <WellMap
        wells={wells}
        onWellClick={(id) => selectWell(id)}
        selectedWellId={selectedWellId}
      />

      <DetailPanel
        wellId={selectedWellId ?? ''}
        wellName={selectedWellName}
        wellData={wellData}
        open={panelOpen}
        loading={detailLoading}
        error={detailError}
        onClose={closePanel}
        onBack={closePanel}
      />
    </div>
  );
}
```

> 别忘了在文件顶部加上 `useState` 的 import。

- [ ] **Step 2: 确保 useApi hook 存在**

如果没有 `src-web/src/hooks/useApi.ts`，先查一下现有项目中是否存在，它可能在 `src-web/src/hooks/index.ts` 里导出。如果是后者，在这里 import 相应路径即可。

---

## TASK 9: WellTablePage 表格页

**Files:**
- Create: `src-web/src/pages/WellTablePage.tsx`
- Modify: `src-web/src/stores/useMapStore.ts`（import into router）

### TASK 9A: WellTablePage.tsx

- [ ] **Step 1: 创建表格页**

```tsx
import { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useWellStore } from '../stores/useWellStore';
import { useMapStore } from '../stores/useMapStore';
import { Eye } from 'lucide-react';

export default function WellTablePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { wells } = useWellStore();
  const { selectWell } = useMapStore();
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    if (!search.trim()) return wells;
    const q = search.toLowerCase();
    return wells.filter(
      (w) =>
        w.well_id.toLowerCase().includes(q) ||
        w.well_name.toLowerCase().includes(q)
    );
  }, [wells, search]);

  const handleView = (wellId: string) => {
    selectWell(wellId);
    navigate('/');
  };

  return (
    <div className="flex flex-col h-full p-6 gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-geo-text">
          {t('page.table.title')}
        </h1>
        <input
          type="search"
          placeholder={t('page.table.searchPlaceholder')}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="px-3 py-2 border border-geo-border rounded-lg text-sm w-64 focus:outline-none focus:border-geo-accent"
        />
      </div>

      <div className="flex-1 overflow-auto border border-geo-border rounded-lg">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-geo-surface text-left text-xs uppercase text-geo-muted border-b border-geo-border">
            <tr>
              <th className="px-4 py-3 font-medium">井号</th>
              <th className="px-4 py-3 font-medium">井名</th>
              <th className="px-4 py-3 font-medium">深度范围 (m)</th>
              <th className="px-4 py-3 font-medium">曲线</th>
              <th className="px-4 py-3 font-medium">经度</th>
              <th className="px-4 py-3 font-medium">纬度</th>
              <th className="px-4 py-3 font-medium text-right">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-geo-border">
            {filtered.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-geo-muted">
                  {t('page.table.noResults')}
                </td>
              </tr>
            )}
            {filtered.map((well) => (
              <tr
                key={well.well_id}
                className="hover:bg-geo-surface/60 transition-colors"
              >
                <td className="px-4 py-2.5 font-mono text-xs">{well.well_id}</td>
                <td className="px-4 py-2.5">{well.well_name}</td>
                <td className="px-4 py-2.5 text-geo-muted">
                  {well.depth_start.toFixed(1)} – {well.depth_end.toFixed(1)}
                </td>
                <td className="px-4 py-2.5 text-geo-muted">
                  {well.curve_names.join(', ')}
                </td>
                <td className="px-4 py-2.5 font-mono text-xs text-geo-muted">
                  {well.longitude?.toFixed(4) ?? '—'}
                </td>
                <td className="px-4 py-2.5 font-mono text-xs text-geo-muted">
                  {well.latitude?.toFixed(4) ?? '—'}
                </td>
                <td className="px-4 py-2.5 text-right">
                  <button
                    onClick={() => handleView(well.well_id)}
                    className="inline-flex items-center gap-1 text-geo-accent hover:text-geo-accent/80 text-xs"
                  >
                    <Eye size={14} />
                    查看
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 国际化翻译 key（在 zh.json / en.json）**

在 zh.json 中增加：
```json
  "page.table.title": "测井数据表",
  "page.table.searchPlaceholder": "搜索井号或井名...",
  "page.table.noResults": "未找到匹配的井"
```
en.json 对应翻译：
```json
  "page.table.title": "Well Data Table",
  "page.table.searchPlaceholder": "Search well ID or name...",
  "page.table.noResults": "No matching wells"
```

---

## TASK 10: 路由更新 + 最后组装

**Files:**
- Modify: `src-web/src/router.tsx`
- Modify: `src-web/src/pages/HomePage.tsx`（重定向至 `/` → MapHomePage）

### TASK 10A: 更新 router.tsx

- [ ] **Step 1: 更新路由表**

```tsx
import { createBrowserRouter } from 'react-router-dom';
import AppLayout from './components/layout/AppLayout';
import MapHomePage from './pages/MapHomePage';
import WellTablePage from './pages/WellTablePage';

// 旧 HomePage 可以删除或留着不再注册路由
const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <MapHomePage /> },
      { path: 'table', element: <WellTablePage /> },
    ],
  },
]);

export default router;
```

> 注：`/well-log` 路由已被移除。如前端 bookmark 了这个 URL，需要告诉用户改用新的 `/` 入口。

### TASK 10B: 确认 MapHomePage 可以在 '/' 直接使用

实际上 `MapHomePage` 就是地图首页，`index: true` 的逻辑已保证这一点。如果之前有 `HomePage` 暂不影响。

- [ ] **Step 2: 运行 TypeScript 类型检查**

Run: `cd ~/projects/geo-viz-engine/src-web && npx tsc --noEmit 2>&1 | head -50`
Expected: 无 FATAL ERROR（warning 可以接受），关注 `types.ts`、`useWellStore.ts`、`MapHomePage.tsx` 的接口一致性。

- [ ] **Step 3: Vite build 测试**

Run: `cd ~/projects/geo-viz-engine/src-web && npm run build 2>&1 | tail -20`
Expected: BUILD SUCCESSFUL，无 chunk 错误。

---

## TASK 11: 回归测试

**Files:**
- 全部后端相关文件

- [ ] **Step 1: Python 测试套件**

Run: `cd ~/projects/geo-viz-engine && python -m pytest src-python/tests/ -q`
Expected: 仍然是 **41 passed**，不能有 regression。

- [ ] **Step 2: 可选：快速 smoke test**

启动后端服务，手动验证各 API 响应新增了 `longitude/latitude` 字段：
```bash
curl -s http://localhost:8000/api/data/list | python -c "import sys,json; d=json.load(sys.stdin); print(list(d[0].keys()))"
```
Expected: 输出中包含 `longitude` 和 `latitude`。

---

## Self-Review Checklist

- [ ] 所有 `longitude` / `latitude` 拼写一致（未混入 `lng`/`lon` 等异体缩写）
- [ ] `useMapStore` 的 `selectWell` 会同步 `panelOpen=true`，满足"点击即开"交互
- [ ] `DetailPanel` 同时有「← 返回」和「✕」，满足 spec 三处保障原则
- [ ] `MapHomePage` 首次加载时会尝试 `/api/data/list`，若空则自动 POST `/api/data/generate`
- [ ] `WellTablePage` 的"查看"会 `navigate('/')` + `selectWell()`，确保回到地图页并开 Panel
- [ ] `AppLayout` 已移除 Sidebar，Navigation 改为 Top Tab
- [ ] `maplibre-gl` 的 `new maplibregl.Map(...)` 在 StrictMode 下不会重复初始化（有 `mapRef.current` guard）
- [ ] `WellMap.tsx` 的 markers 通过 `map.loaded()` 判断地图准备就绪后才添加打点，避免空指针崩溃
- [ ] TypeScript 接口在 `types.ts` / `useWellStore.ts` / `useMapStore.ts` 三处一致（`longitude?: number | null`）

---

*Last reviewed: 2026-04-16*