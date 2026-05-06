# ECharts OOP v2 Refactoring Task 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance WellLogChart with graphic-based headers, fix potential JS errors in custom renderers, and implement a centered depth track.

**Architecture:** Move away from ECharts `title` for track headers to `graphic` elements for better alignment and styling control. Add defensive checks in `LithologyTrack` and `IntervalTrack`. Redesign `DepthTrack` to use a centered axis layout.

**Tech Stack:** ECharts (Graphic component, Custom series), JavaScript (OOP)

---

### Task 1: Refactor Headers to use Graphic Elements

**Files:**
- Modify: `src-echarts/src/geoviz-echarts-wellog.js`

- [ ] **Step 1: Update `BaseTrack` to include `getGraphicElements` and remove `getTitles`**

```javascript
// Add to BaseTrack
getGraphicElements(index, top, height, hasParent) {
    const backgroundColor = hasParent ? THEME.subHeaderBg : THEME.headerBg;
    return {
        type: 'group',
        left: this._calculatedLeft + '%',
        top: top,
        width: this.width + '%',
        height: height,
        children: [
            {
                type: 'rect',
                shape: { width: '100%', height: '100%' },
                style: {
                    fill: backgroundColor,
                    stroke: THEME.borderColor,
                    lineWidth: 1
                }
            },
            {
                type: 'text',
                left: 'center',
                top: 'middle',
                style: {
                    text: this.name,
                    fill: THEME.textColor,
                    font: '11px sans-serif'
                }
            }
        ]
    };
}
```

- [ ] **Step 2: Update `CurveTrack` to override `getGraphicElements`**

```javascript
// Add to CurveTrack
getGraphicElements(index, top, height, hasParent) {
    const backgroundColor = hasParent ? THEME.subHeaderBg : THEME.headerBg;
    const rich = { title: { fontWeight: 'bold', fontSize: 11, color: THEME.textColor } };
    let headerText = '{title|' + (this.name || '') + '}\n';
    
    (this.data.series || []).forEach(s => {
        const line = s.lineStyle === 'dashed' ? '- - ' : '— ';
        const safeName = s.name.replace(/[^a-zA-Z0-9]/g, '_');
        headerText += `{${safeName}|${line}${s.name} ${s.rangeLabel || ''}}\n`;
        rich[safeName] = { color: s.color, fontSize: 10, fontWeight: 'bold' };
    });

    return {
        type: 'group',
        left: this._calculatedLeft + '%',
        top: top,
        width: this.width + '%',
        height: height,
        children: [
            {
                type: 'rect',
                shape: { width: '100%', height: '100%' },
                style: {
                    fill: backgroundColor,
                    stroke: THEME.borderColor,
                    lineWidth: 1
                }
            },
            {
                type: 'text',
                left: 'center',
                top: 'middle',
                style: {
                    text: headerText,
                    rich: rich,
                    fill: THEME.textColor,
                    font: '11px sans-serif',
                    textAlign: 'center'
                }
            }
        ]
    };
}
```

- [ ] **Step 3: Update `WellLogChart._buildEChartsOption` to use `graphic` instead of `title`**

```javascript
// In _buildEChartsOption
const graphics = [];

// Handle Parent Groups
groups.forEach(g => {
    graphics.push({
        type: 'group',
        left: g.startLeft + '%',
        top: HEADER_TOP_Y,
        width: g.width + '%',
        height: THEME.headerHeight,
        children: [
            {
                type: 'rect',
                shape: { width: '100%', height: '100%' },
                style: {
                    fill: THEME.headerBg,
                    stroke: THEME.borderColor,
                    lineWidth: 1
                }
            },
            {
                type: 'text',
                left: 'center',
                top: 'middle',
                style: {
                    text: g.name,
                    fill: THEME.textColor,
                    font: 'bold 12px sans-serif'
                }
            }
        ]
    });
});

// Handle Tracks
tracks.forEach((track, index) => {
    const hasParent = !!track.parentGroup;
    const titleTop = hasParent ? HEADER_SUB_Y : HEADER_TOP_Y;
    const titleHeight = hasParent ? THEME.subHeaderHeight : (THEME.headerHeight + THEME.subHeaderHeight);
    
    graphics.push(track.getGraphicElements(index, titleTop, titleHeight, hasParent));
    // ... rest of loop
});

return {
    // title: titles, // REMOVE
    graphic: graphics,
    // ...
};
```

### Task 2: Data Safety and JS Error Fixes

**Files:**
- Modify: `src-echarts/src/geoviz-echarts-wellog.js`

- [ ] **Step 1: Add defensive checks to `LithologyTrack.getSeries` and `renderItem`**

```javascript
getSeries(index) {
    if (!this.data || !this.data.data) return [];
    const dataItems = (this.data.data || []).map(item => {
        // ... safety checks
        if (item.lithology) {
            const img = document.getElementById(`pat-${item.lithology}`);
            if (img) style.color = { image: img, repeat: 'repeat' };
            else style.color = item.color || '#cbd5e0';
        }
        // ...
    });
    // ...
    return [{
        // ...
        renderItem: (params, api) => {
            if (!params.data) return null;
            // ...
        }
    }];
}
```

### Task 3: Professional Centered Depth Track

**Files:**
- Modify: `src-echarts/src/geoviz-echarts-wellog.js`

- [ ] **Step 1: Modify `DepthTrack` methods**

```javascript
class DepthTrack extends BaseTrack {
    getXAxis(index) {
        return { 
            type: 'value', 
            gridIndex: index, 
            show: false, 
            min: -1, 
            max: 1 
        };
    }

    getYAxis(index, commonY) {
        return {
            ...commonY,
            gridIndex: index,
            show: true,
            position: 'left', // Keep it left for standard coordinate mapping
            axisLine: { 
                show: true,
                onZero: true, // This will center it if X ranges from -1 to 1
                symbol: ['none', 'none'], 
                lineStyle: { color: THEME.borderColor } 
            },
            axisLabel: { 
                show: true, 
                fontWeight: 'bold', 
                color: THEME.textColor,
                inside: false // or true depending on look
            },
            axisTick: { show: true }
        };
    }
}
```

### Task 4: Verification and Commit

- [ ] **Step 1: Commit changes**

```bash
git add src-echarts/src/geoviz-echarts-wellog.js
git commit -m "feat(web): implement graphic-based headers and professional depth axis"
```
