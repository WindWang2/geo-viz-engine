# GeoViz Engine UI Redesign — Pass 2

> 第二轮 UI 调整设计规范，基于 UI.html (方案A 蓝铜) 参考，聚焦视觉精修、布局重构、交互增强。

## Goal

在现有 Azurite Design System 基础上进行第二轮全面 UI 调整：
1. **布局重构**：可折叠侧边栏 + 全出血内容区域
2. **视觉精修**：统一间距系统、圆角风格、阴影层次
3. **交互增强**：悬停状态、微交动脉冲、搜索快捷键

## Scope

- 主框架：Header、Sidebar、Footer
- 内容页面：所有 8 个页面的内部布局
- 设计系统：间距、圆角、阴影、动画规范

## Architecture

### Main Frame Layout

```
┌─────────────────────────────────────────────────┐
│ Header (48px)                                   │
│ [☰] [Logo GeoViz Engine] │ 标题 · 副标题 │ [🔍 ⌘K] [🔔 ⚙️] │ 🌐 中文 │
├────────┬────────────────────────────────────────┤
│Sidebar │ Content Area                           │
│(200px) │                                        │
│        │  ┌──────────┬────────────────────────┐ │
│ 🗺️ 地图 │  │Left Panel│  Main Content          │ │
│ 🌍 古地理│  │(260px)   │                       │ │
│ 📊 井剖面│  │          │                       │ │
│ 🔗 连井  │  │          │                       │ │
│ 🧊 地震  │  │          │                       │ │
│ 📈 平面  │  └──────────┴────────────────────────┘ │
│────────│                                        │
│ 📁 数据  │                                        │
│ 🔧 工具  │                                        │
│────────│                                        │
│ ⚙️ 设置  │                                        │
├────────┴────────────────────────────────────────┤
│ Footer (32px)                                   │
│ ● 就绪 │ 地图状态 │ ··· │ GPU: CUDA · 2.1GB │ 缓存 231MB │ v0.14.0 │
└─────────────────────────────────────────────────┘
```

### Sidebar Behavior

- **Default state**: Expanded (200px), showing icons + text
- **Collapse trigger**: Click ☰ button in header, or keyboard shortcut
- **Collapsed state**: 56px, icons only, tooltips on hover
- **Transition**: 200ms ease, width animates smoothly
- **Memory**: Save collapsed state in QSettings

### Header Refinements

- Height: 48px (was 52px)
- Brand: SVG logo + "GeoViz Engine" with gradient text
- Search bar: Integrated with ⌘K shortcut hint
- Tool buttons: 30x30px, hover background #f1f4f9
- Divider: 1px #e5eaf1, height 20px

### Footer Enhancements

- Height: 32px (was 26px)
- Sections: Status dot + text | Context info | GPU info | Cache | Version
- All monospace font for technical data
- Dividers between sections

## Design System

### Spacing (8px Grid)

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | 4px | Inline gaps, chip padding |
| `--space-sm` | 8px | Component internal padding |
| `--space-md` | 12px | Component gaps, section padding |
| `--space-lg` | 16px | Page margins, header padding |
| `--space-xl` | 24px | Section separators |

### Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-sm` | 6px | Chips, badges, small elements |
| `--radius-md` | 8px | Buttons, inputs, sidebar items |
| `--radius-lg` | 12px | Cards, panels, group boxes |
| `--radius-xl` | 16px | Modals, dialogs |

### Shadow Levels

| Level | Value | Usage |
|-------|-------|-------|
| L1 | `0 1px 3px rgba(0,0,0,0.08)` | Floating buttons, hover states |
| L2 | `0 2px 8px rgba(0,0,0,0.1)` | Panels, dropdowns |
| L3 | `0 8px 24px rgba(0,0,0,0.15)` | Modals, dialogs |

### Animation

| Token | Value | Usage |
|-------|-------|-------|
| `--duration-fast` | 150ms | Hover transitions, button states |
| `--duration-normal` | 200ms | Sidebar collapse, page transitions |
| `--duration-slow` | 300ms | Modal open/close |
| `--easing` | ease | All transitions |

## Color Palette (Azurite)

| Name | Hex | Usage |
|------|-----|-------|
| Primary | #1f66d4 | Active states, links, brand |
| Primary Dark | #133a76 | Gradient endpoint |
| Background | #faf9f5 | Page background |
| Surface | #ffffff | Cards, panels, sidebar |
| Border | #e5eaf1 | All borders |
| Text Primary | #1a2433 | Headings, body text |
| Text Secondary | #586878 | Labels, descriptions |
| Text Tertiary | #92a0b0 | Captions, placeholders |
| Hover | #f1f4f9 | Hover background |
| Active | #e9effa | Active/selected background |
| Success | #2ca36b | Status dot, positive |
| Danger | #dc2626 | Errors, warnings |

## Components to Modify

### 1. SidebarButton (app.py)

Changes:
- Default expanded width: 200px
- Collapsed width: 56px (icon only)
- Border-radius: 8px
- Padding: 8px 12px
- Active: background #e9effa, color #1f66d4, border-left 3px solid
- Hover: background #f1f4f9
- Transition: background 150ms ease

### 2. HeaderToolButton (app.py)

Changes:
- Size: 30x30px (was 32x32)
- Border-radius: 8px
- Hover: background #f1f4f9
- Transition: background 150ms ease

### 3. Header Frame (app.py)

Changes:
- Height: 48px (was 52px)
- Add integrated search bar with ⌘K hint
- Add notification bell button
- Divider height: 20px

### 4. Footer Frame (app.py)

Changes:
- Height: 32px (was 26px)
- Add GPU info display
- Add cache size display
- All technical text in monospace
- Dividers between sections

### 5. Sidebar Container (app.py)

Changes:
- Default width: 200px (was 212px)
- Collapsible to 56px via ☰ button
- Transition: width 200ms ease
- Save state in QSettings

## Content Page Adjustments

### Map Page
- Left panel: 260px (was dynamic)
- Well list items: 8px border-radius, hover state
- Filter chips: 6px radius, active blue
- Map controls: Floating with L1 shadow

### Well Log Page
- Track headers: Refined with 8px radius
- Drag-resize handles: Visual indicator
- Scrollbar: 8px width, rounded

### Cross Well Page
- Multi-well layout: Unified spacing
- Picking overlay: Cursor feedback
- Correlation lines: Smooth bezier curves

### Seismic 3D Page
- Slice controls: Grouped with panels
- Colormap bar: Integrated with L2 shadow
- Toolbar: Consistent with header style

## Files to Modify

| File | Changes |
|------|---------|
| `src/app.py` | Sidebar, Header, Footer, SidebarButton, HeaderToolButton |
| `src/main.py` | Global stylesheet updates (spacing, radius, shadows) |
| `src/pages/map/page.py` | Left panel layout, well list styling |
| `src/pages/well_log/page.py` | Track header refinement |
| `src/pages/cross_well/page.py` | Multi-well layout spacing |
| `src/pages/seismic/seismic_page.py` | Toolbar and control panel layout |
| `src/pages/plots/page.py` | Control panel layout |
| `src/pages/data/page.py` | Table styling |
| `src/pages/tools/page.py` | Tool card layout |
| `src/pages/settings/page.py` | Settings layout |

## Testing

- Visual regression: Screenshot comparison before/after
- Interaction: Sidebar collapse/expand, hover states, search shortcut
- Layout: Responsive to window resize
- Performance: Animation smoothness at 60fps
