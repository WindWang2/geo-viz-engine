import * as echarts from 'echarts';

/**
 * GEOLOGICAL WELL LOG RENDERING ENGINE v13.0
 * Fixes: text visibility during zoom, pattern clipping, header centering, infinite re-render.
 */

const THEME = {
    headerTop: 10,
    groupHeaderHeight: 32,
    trackHeaderHeight: 56,
    bodyTopGap: 8,
    borderColor: '#94a3b8',
    headerBg: '#e2e8f0',
    subHeaderBg: '#f8fafc',
    textColor: '#0f172a',
    gridLineColor: '#cbd5e1',
    fontFamily: "Inter, 'Microsoft YaHei', sans-serif"
};

const patternRegistry = new Map();

export function registerPatterns(patternsMap) {
    const promises = [];
    for (const [id, dataUrl] of Object.entries(patternsMap)) {
        if (patternRegistry.has(id)) continue;
        const img = new Image();
        img.src = dataUrl;
        const p = new Promise((resolve) => {
            img.onload = () => { patternRegistry.set(id, img); resolve(); };
            img.onerror = () => { console.warn(`[Pattern] Failed: ${id}`); resolve(); };
        });
        promises.push(p);
    }
    return Promise.all(promises);
}

function getPatternImage(patternId) {
    if (!patternId) return null;
    return patternRegistry.get(patternId) || null;
}

class WellLogLayout {
    estimateTrackHeaderWidth(t) {
        let maxTextW = 50; 
        const measureText = (text, fontSize) => {
            let w = 0;
            const str = String(text || '');
            for (let i = 0; i < str.length; i++) {
                if (str.charCodeAt(i) > 255) w += fontSize;
                else w += fontSize * 0.55;
            }
            return w;
        };

        if (t.type === 'CurveTrack') {
            let tw1 = measureText(t.name || '', 15);
            maxTextW = Math.max(maxTextW, tw1);
            if (t.series) {
                t.series.forEach(s => {
                    const lineStr = s.lineStyle === 'dashed' ? '- -  ' : '—  ';
                    const str = `${lineStr}${s.name} ${s.rangeLabel || ''}`;
                    maxTextW = Math.max(maxTextW, measureText(str, 12));
                });
            }
        } else if (t.type === 'DepthTrack') {
            maxTextW = 40;
        } else {
            maxTextW = Math.max(maxTextW, measureText(t.name || '', 14));
        }
        return maxTextW + 30; // base padding
    }

    constructor(cw, ch, trackDatas) {
        this.cw = cw || 1200;
        this.tracks = trackDatas.map(t => ({ ...t, width: t.width || 10 }));
        
        let calculatedW = 20;
        this.trackWidths = this.tracks.map(t => {
            let requiredW = this.estimateTrackHeaderWidth(t);
            calculatedW += requiredW;
            return requiredW;
        });
        calculatedW += 40;
        
        const finalW = Math.max(this.cw, calculatedW);
        const dom = document.getElementById('chart-container');
        if (dom) {
            dom.style.width = finalW + 'px';
        }
        document.body.style.overflow = 'auto';
        document.documentElement.style.overflow = 'auto';
        
        this.availableW = finalW - 60;
        if (finalW === this.cw) {
            let totalReq = this.trackWidths.reduce((s, tw) => s + tw, 0);
            if (totalReq > 0) {
                this.trackWidths = this.trackWidths.map(tw => (tw / totalReq) * this.availableW);
            }
        }
        
        this.bodyTop = THEME.headerTop + THEME.groupHeaderHeight + THEME.trackHeaderHeight + THEME.bodyTopGap;
    }
    getTrackLayout(index) {
        let curX = 20;
        for (let i = 0; i < index; i++) curX += this.trackWidths[i];
        const tw = this.trackWidths[index];
        return { x: curX, w: tw, bodyTop: this.bodyTop };
    }
    getGroupLayout(groupName) {
        let startX = -1, totalW = 0, curX = 20;
        this.tracks.forEach((t, i) => {
            const tw = this.trackWidths[i];
            if (t.parentGroup === groupName) { if (startX === -1) startX = curX; totalW += tw; }
            curX += tw;
        });
        return { x: startX, w: totalW };
    }
}


class Track {
    constructor(data, layout, index) {
        this.data = data || {};
        this.layout = layout;
        this.index = index;
        this.name = data.name || '';
    }
    getGrid() {
        return {
            id: `grid-${this.index}`,
            left: this.layout.x, width: this.layout.w,
            top: this.layout.bodyTop, bottom: 40,
            show: true, borderWidth: 1, borderColor: THEME.borderColor, containLabel: false
        };
    }
    getXAxis() { return { type: 'value', gridIndex: this.index, show: false, min: 0, max: 1 }; }
    getYAxis(commonY) { return { ...commonY, gridIndex: this.index, show: false }; }
    getSeries() { return []; }

    getHeaderGraphics(hasParent) {
        const top = hasParent ? (THEME.headerTop + THEME.groupHeaderHeight) : THEME.headerTop;
        const height = hasParent ? THEME.trackHeaderHeight : (THEME.groupHeaderHeight + THEME.trackHeaderHeight);
        const rect = {
            type: 'rect',
            shape: { x: this.layout.x, y: top, width: this.layout.w, height: height },
            style: { fill: hasParent ? THEME.subHeaderBg : THEME.headerBg, stroke: THEME.borderColor, lineWidth: 1 }
        };

        let headerText = this.name;
        let rich = {};
        let fontSize = 14;

        // Center point of the header cell
        const cx = this.layout.x + this.layout.w / 2;
        const cy = top + height / 2;

        if (this.data.type === 'CurveTrack') {
            const lines = [`{t|${this.name}}`];
            rich.t = { fontWeight: 'bold', fontSize: 15, color: THEME.textColor, padding: [0, 0, 4, 0], align: 'center' };
            (this.data.series || []).forEach(s => {
                const sn = s.name.replace(/[^a-z0-9]/gi, '_');
                const line = s.lineStyle === 'dashed' ? '- -' : '—';
                lines.push(`{${sn}|${line}  ${s.name} ${s.rangeLabel || ''}}`);
                rich[sn] = { color: s.color || '#3182ce', fontSize: 12, fontWeight: 'bold', padding: [2, 0, 0, 0], align: 'center' };
            });
            headerText = lines.join('\n');
            fontSize = 13;
        }

        const text = {
            type: 'text',
            position: [cx, cy],
            style: {
                text: headerText, rich: rich, fill: THEME.textColor,
                font: `bold ${fontSize}px ${THEME.fontFamily}`,
                textAlign: 'center', textVerticalAlign: 'middle'
            }
        };
        return [rect, text];
    }
}

class CurveTrack extends Track {
    getXAxis() { return { ...super.getXAxis(), min: this.data.min || 0, max: this.data.max || 150 }; }
    getSeries() {
        return (this.data.series || []).map(s => ({
            name: s.name, type: 'line', xAxisIndex: this.index, yAxisIndex: this.index,
            data: (s.data || []).map(p => [p[1], p[0]]),
            lineStyle: { width: 1.5, color: s.color || '#3182ce', type: s.lineStyle || 'solid' },
            showSymbol: false, smooth: false, connectNulls: false,
            sampling: 'lttb', large: true, largeThreshold: 1000,
            animation: false
        }));
    }
}

class DepthTrack extends Track {
    getXAxis() { return { ...super.getXAxis(), min: -1, max: 1 }; }
    getYAxis(commonY) {
        return {
            ...commonY, gridIndex: this.index, show: true, position: 'left',
            axisLine: { show: true, onZero: true, lineStyle: { color: THEME.borderColor } },
            axisLabel: { show: true, fontWeight: 'bold', fontSize: 11, margin: 4 },
            axisTick: { show: true }
        };
    }
}

/**
 * Helper: build the rect+text children for an interval block.
 * Clamps text position to the visible grid area so text is always on-screen.
 */
function buildIntervalBlock(item, api, params, trackData, applyPattern) {
    const yTop = api.coord([0, item.top])[1];
    const yBot = api.coord([0, item.bottom])[1];
    const xLeft = api.coord([0, 0])[0];
    const xRight = api.coord([1, 0])[0];
    const w = xRight - xLeft;
    const rawH = Math.abs(yBot - yTop);
    const midX = xLeft + w / 2;
    const yMin = Math.min(yTop, yBot);

    // Clamp to grid area for proper clipping
    const gridTop = params.coordSys.y;
    const gridBot = params.coordSys.y + params.coordSys.height;
    const clampedTop = Math.max(yMin, gridTop);
    const clampedBot = Math.min(yMin + rawH, gridBot);
    if (clampedBot <= clampedTop) return null; // fully out of view

    // Shape element
    let gs;
    if (item.shape === 'triangle-up') {
        gs = { type: 'polygon', shape: { points: [[xLeft, yBot], [xRight, yBot], [midX, yTop]] }, style: { fill: item.color || '#93c5fd' } };
    } else if (item.shape === 'triangle-down') {
        gs = { type: 'polygon', shape: { points: [[xLeft, yTop], [xRight, yTop], [midX, yBot]] }, style: { fill: item.color || '#fde047' } };
    } else {
        let st = { fill: item.color || '#fff' };
        if (applyPattern || item.lithology) {
            const patImg = getPatternImage(item.lithology);
            if (patImg) st.fill = { image: patImg, repeat: 'repeat' };
        }
        gs = { type: 'rect', shape: { x: xLeft, y: yMin, width: w, height: rawH }, style: st };
    }

    // Text: position at center of VISIBLE portion
    const textY = (clampedTop + clampedBot) / 2;
    const isVertical = trackData.textOrientation === 'vertical';

    // For vertical text, use line breaks between chars instead of rotation
    let displayText = item.name || '';
    if (isVertical && displayText.length > 0) {
        displayText = displayText.split('').join('\n');
    }

    const visibleH = clampedBot - clampedTop;
    const requiredTextHeight = isVertical ? (item.name || '').length * 14 : 14;
    const showText = visibleH >= requiredTextHeight && w >= 10;

    const children = [
        {
            ...gs,
            style: { ...gs.style, stroke: THEME.borderColor, lineWidth: 0.5 },
            clipPath: {
                type: 'rect',
                shape: { x: xLeft, y: gridTop, width: w, height: gridBot - gridTop }
            }
        }
    ];

    if (showText) {
        children.push({
            type: 'text',
            style: {
                text: displayText, x: midX, y: textY,
                textAlign: 'center', textVerticalAlign: 'middle',
                fill: THEME.textColor,
                font: `bold ${isVertical ? 11 : 10}px sans-serif`,
                lineHeight: isVertical ? 14 : undefined,
                width: isVertical ? undefined : (w - 4),
                overflow: isVertical ? undefined : 'truncate'
            },
            clipPath: {
                type: 'rect',
                shape: { x: xLeft, y: gridTop, width: w, height: gridBot - gridTop }
            }
        });
    }

    return {
        type: 'group',
        children: children
    };
}

class LithologyTrack extends Track {
    getSeries() {
        const items = this.data.data || [];
        const td = this.data;
        return [{
            type: 'custom', xAxisIndex: this.index, yAxisIndex: this.index,
            clip: true,
            encode: { x: 0, y: [1, 2] },
            renderItem: (params, api) => {
                const item = items[params.dataIndex];
                if (!item) return null;
                return buildIntervalBlock(item, api, params, td, true);
            },
            data: items.map(i => [0.5, i.top, i.bottom])
        }];
    }
}

class IntervalTrack extends Track {
    getSeries() {
        const items = this.data.data || [];
        const td = this.data;
        return [{
            type: 'custom', xAxisIndex: this.index, yAxisIndex: this.index,
            clip: true,
            encode: { x: 0, y: [1, 2] },
            renderItem: (params, api) => {
                const item = items[params.dataIndex];
                if (!item) return null;
                return buildIntervalBlock(item, api, params, td, false);
            },
            data: items.map(i => [0.5, i.top, i.bottom])
        }];
    }
}

export class WellLogChart {
    constructor(containerId) {
        this.containerId = containerId;
        this.chart = null;
        this._lastData = null;
        this._patternsReady = false;
        this._rendering = false;
    }

    _ensureInit() {
        const dom = document.getElementById(this.containerId);
        if (!dom || this.chart) return dom;
        this.chart = echarts.init(dom, null, { renderer: 'svg' });
        // Debounced resize handler to prevent infinite re-render loops
        let resizeTimer = null;
        window.addEventListener('resize', () => {
            if (resizeTimer) clearTimeout(resizeTimer);
            resizeTimer = setTimeout(() => {
                this.chart.resize();
                if (this._lastData && this.chart) {
                    let startVal = null, endVal = null;
                    const opts = this.chart.getOption();
                    if (opts && opts.dataZoom && opts.dataZoom.length > 0) {
                        startVal = opts.dataZoom[0].startValue;
                        endVal = opts.dataZoom[0].endValue;
                    }
                    this._rendering = false; // allow re-render
                    this._doRender(this._lastData, startVal, endVal);
                }
            }, 100);
        });
        return dom;
    }

    render(data) {
        if (!data) return;
        this._lastData = data;
        if (this._patternsReady) {
            this._doRender(data);
        }
    }

    onPatternsReady() {
        this._patternsReady = true;
        console.log(`[v13] Patterns ready: ${patternRegistry.size}`);
        if (this._lastData) this._doRender(this._lastData);
    }

    _doRender(data, keepStartValue = null, keepEndValue = null) {
        if (this._rendering) return;
        this._rendering = true;
        const dom = this._ensureInit();
        if (!dom) { this._rendering = false; return; }

        // Store track data for tooltip lookup
        this._trackData = data.tracks || [];

        console.log("[v14] Rendering", data.metadata.wellName);
        try {
            dom.style.width = '100%';
            dom.style.height = '100%';
            const layout = new WellLogLayout(dom.clientWidth, dom.clientHeight, data.tracks);
            if (this.chart) {
                this.chart.resize();
            }
            const grids = [], xAxes = [], yAxes = [], series = [], graphics = [];
            const yAxisIndices = [];
            const commonY = {
                type: 'value', inverse: true,
                min: data.metadata.topDepth, max: data.metadata.bottomDepth,
                axisLine: { show: true, lineStyle: { color: THEME.borderColor } },
                splitLine: { show: true, lineStyle: { color: THEME.gridLineColor } }
            };

            const parentGroups = new Map();

            (data.tracks || []).forEach((tData, i) => {
                const trackLayout = layout.getTrackLayout(i);
                let track;
                if (tData.type === 'CurveTrack') track = new CurveTrack(tData, trackLayout, i);
                else if (tData.type === 'DepthTrack') track = new DepthTrack(tData, trackLayout, i);
                else if (tData.type === 'LithologyTrack') track = new LithologyTrack(tData, trackLayout, i);
                else track = new IntervalTrack(tData, trackLayout, i);

                grids.push(track.getGrid());

                // xAxis: never trigger tooltip from x-axis
                const xAxisConfig = track.getXAxis();
                xAxisConfig.axisPointer = { type: 'none', show: false, triggerTooltip: false };
                xAxes.push(xAxisConfig);

                // yAxis: always trigger tooltip from y-axis (depth)
                const yAxisConfig = track.getYAxis(commonY);
                yAxisConfig.axisPointer = {
                    show: true, type: 'line', snap: false, triggerTooltip: true,
                    lineStyle: { color: '#334155', width: 1, type: 'dashed' },
                    label: { show: false }
                };
                yAxes.push(yAxisConfig);
                yAxisIndices.push(i);

                series.push(...track.getSeries());

                // Add hidden depth-reference series for non-curve grids
                // This gives the y-axis tooltip a standard line series to trigger
                if (tData.type !== 'CurveTrack') {
                    const topD = data.metadata.topDepth;
                    const botD = data.metadata.bottomDepth;
                    series.push({
                        type: 'line', xAxisIndex: i, yAxisIndex: i,
                        data: [[0.5, topD], [0.5, botD]],
                        lineStyle: { width: 0, opacity: 0 },
                        itemStyle: { opacity: 0 },
                        showSymbol: false, silent: true, z: -100,
                        tooltip: { show: false }
                    });
                }

                graphics.push(...track.getHeaderGraphics(!!tData.parentGroup));

                if (tData.parentGroup && !parentGroups.has(tData.parentGroup)) {
                    parentGroups.set(tData.parentGroup, layout.getGroupLayout(tData.parentGroup));
                }
            });

            parentGroups.forEach((l, name) => {
                graphics.push({
                    type: 'rect',
                    shape: { x: l.x, y: THEME.headerTop, width: l.w, height: THEME.groupHeaderHeight },
                    style: { fill: THEME.headerBg, stroke: THEME.borderColor, lineWidth: 1 }
                });
                graphics.push({
                    type: 'text',
                    position: [l.x + l.w / 2, THEME.headerTop + THEME.groupHeaderHeight / 2],
                    style: { text: name, fill: THEME.textColor, font: `bold 15px ${THEME.fontFamily}`, textAlign: 'center', textVerticalAlign: 'middle' }
                });
            });

            // Tooltip formatter closure over track data
            const trackData = this._trackData;
            let exactMouseDepth = null; // Captured from updateAxisPointer

            const tooltipFormatter = function (params) {
                if (!params || params.length === 0) return '';

                let depth = exactMouseDepth !== null ? exactMouseDepth : params[0].axisValue;
                if (params[0].axisDim === 'x' && params[0].value && exactMouseDepth === null) {
                    // Fallback: if ECharts incorrectly triggers on the X axis,
                    // grab the snapped depth (Y) from the data point array instead.
                    depth = params[0].value[1];
                }
                
                if (depth === undefined || depth === null) return '';

                let lines = [`<div style="font-weight:700;font-size:14px;margin-bottom:8px;color:#f1f5f9;border-bottom:1px solid rgba(148,163,184,0.3);padding-bottom:6px;">📍 深度: ${Number(depth).toFixed(2)} m</div>`];

                const curveValues = new Map();

                // Lookup all curve values by manual linear interpolation
                trackData.forEach(t => {
                    if (t.type === 'CurveTrack') {
                        (t.series || []).forEach(s => {
                            const pts = s.data || [];
                            let val = null;
                            for (let j = 0; j < pts.length - 1; j++) {
                                // pts[j] is [depth, value] in track data?
                                // WAIT! s.data from Python is [[depth, value]]
                                // Let's check s.data structure...
                                const d0 = pts[j][0], d1 = pts[j + 1][0];
                                const v0 = pts[j][1], v1 = pts[j + 1][1];
                                if (v0 === null || v1 === null) continue;
                                if (depth >= Math.min(d0, d1) && depth <= Math.max(d0, d1)) {
                                    const ratio = (d1 - d0) !== 0 ? (depth - d0) / (d1 - d0) : 0;
                                    val = v0 + ratio * (v1 - v0);
                                    break;
                                }
                            }
                            if (val !== null) curveValues.set(s.name, val);
                        });
                    }
                });

                // Display curve values
                curveValues.forEach((val, name) => {
                    const v = typeof val === 'number' ? val.toFixed(2) : val;
                    lines.push(`<div style="padding:2px 0;"><span style="color:#94a3b8;">📈 ${name}:</span> <span style="font-weight:600;color:#e2e8f0;">${v}</span></div>`);
                });

                // Interval data lookup
                trackData.forEach(t => {
                    if (t.type === 'IntervalTrack' || t.type === 'LithologyTrack') {
                        const items = t.data || [];
                        const match = items.find(d => depth >= d.top && depth <= d.bottom);
                        if (match && match.name) {
                            const label = t.parentGroup ? `${t.parentGroup}·${t.name}` : t.name;
                            lines.push(`<div style="padding:2px 0;"><span style="color:#94a3b8;">📋 ${label}:</span> <span style="font-weight:600;color:#e2e8f0;">${match.name}</span></div>`);
                        }
                    }
                });

                return lines.join('');
            };

            this.chart.setOption({
                animation: false,
                graphic: graphics, grid: grids, xAxis: xAxes, yAxis: yAxes, series: series,
                backgroundColor: '#ffffff',
                axisPointer: {
                    link: [{ yAxisIndex: 'all' }],
                    show: true
                },
                tooltip: {
                    trigger: 'axis',
                    axisPointer: { type: 'line', axis: 'y' },
                    backgroundColor: 'rgba(15, 23, 42, 0.88)',
                    borderColor: 'rgba(148, 163, 184, 0.4)',
                    borderWidth: 1,
                    borderRadius: 8,
                    padding: [12, 16],
                    textStyle: { color: '#e2e8f0', fontSize: 12, fontFamily: THEME.fontFamily },
                    extraCssText: 'backdrop-filter: blur(8px); box-shadow: 0 8px 32px rgba(0,0,0,0.3);',
                    formatter: tooltipFormatter,
                    confine: true
                },
                dataZoom: [
                    { 
                        type: 'inside', filterMode: 'none', 
                        yAxisIndex: Array.from({length: grids.length}, (_, i) => i) 
                    },
                    { 
                        type: 'slider', filterMode: 'none', 
                        yAxisIndex: Array.from({length: grids.length}, (_, i) => i),
                        width: 24, right: 10,
                        startValue: keepStartValue !== null ? keepStartValue : data.metadata.topDepth,
                        endValue: keepEndValue !== null ? keepEndValue : Math.min(data.metadata.bottomDepth, data.metadata.topDepth + 50),
                        labelFormatter: function (value) { return value.toFixed(0) + ' m'; },
                        fillerColor: 'rgba(49, 130, 206, 0.2)',
                        borderColor: '#cbd5e1',
                        handleSize: '100%',
                        showDataShadow: false
                    }
                ]
            }, true);

            this.chart.off('updateAxisPointer');
            this.chart.on('updateAxisPointer', function (event) {
                if (event.axesInfo && event.axesInfo.length > 0) {
                    const yAxisInfo = event.axesInfo.find(info => info.axisDim === 'y');
                    if (yAxisInfo) {
                        exactMouseDepth = yAxisInfo.value;
                    }
                }
            });

            console.log("[v14] Done");
        } catch (e) {
            console.error("[v14] FATAL:", e.message, e.stack);
        }
        this._rendering = false;
    }

    exportToSvg() {
        if (!this.chart) return '';
        const dataUrl = this.chart.getDataURL({ type: 'svg' });
        if (!dataUrl) return '';
        let svgText = dataUrl.includes('base64,') ? atob(dataUrl.split('base64,')[1]) : decodeURIComponent(dataUrl.split(',')[1]);
        if (svgText.includes('<svg')) {
            const fontStyle = `<style type="text/css">text{font-family:"Microsoft YaHei","SimHei",sans-serif!important}</style>`;
            const idx = svgText.indexOf('>');
            if (idx > 0) svgText = svgText.slice(0, idx + 1) + fontStyle + svgText.slice(idx + 1);
        }
        return svgText;
    }
}
