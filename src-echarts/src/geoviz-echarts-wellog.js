import * as echarts from 'echarts';

const THEME = {
    headerHeight: 60, // px
    subHeaderHeight: 30, // px
    borderColor: '#94a3b8',
    headerBg: '#f1f5f9',
    subHeaderBg: '#ffffff',
    textColor: '#1e293b',
    gridLineColor: '#e2e8f0'
};

/**
 * Base class for all track types
 */
class BaseTrack {
    constructor(trackData) {
        this.data = trackData;
        this.name = trackData.name || '';
        this.width = trackData.width || 10;
        this.type = trackData.type;
        this.parentGroup = trackData.parentGroup;
        this._calculatedLeft = 0;
    }

    setCalculatedLeft(left) {
        this._calculatedLeft = left;
    }

    getGrid(index, top, bottom) {
        return {
            left: this._calculatedLeft + '%',
            width: this.width + '%',
            top: top,
            bottom: bottom,
            containLabel: false
        };
    }

    getXAxis(index) {
        return { type: 'value', gridIndex: index, show: false, min: 0, max: 1 };
    }

    getYAxis(index, commonY) {
        return {
            ...commonY,
            gridIndex: index,
            show: false,
            axisLabel: { show: false }
        };
    }

    getSeries(index) {
        return [];
    }

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
}

class CurveTrack extends BaseTrack {
    getXAxis(index) {
        return { 
            type: 'value', 
            gridIndex: index, 
            show: false, 
            min: this.data.min || 0, 
            max: this.data.max || 100 
        };
    }

    getSeries(index) {
        return (this.data.series || []).map(s => ({
            name: s.name, 
            type: 'line', 
            xAxisIndex: index, 
            yAxisIndex: index,
            data: (s.data || []).map(p => [p[1], p[0]]),
            lineStyle: { width: 1.5, type: s.lineStyle || 'solid', color: s.color },
            showSymbol: false, 
            smooth: true
        }));
    }

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
}

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
            position: 'left',
            axisLine: { 
                show: true,
                onZero: true, 
                symbol: ['none', 'none'], 
                lineStyle: { color: THEME.borderColor } 
            },
            axisLabel: { 
                show: true, 
                fontWeight: 'bold', 
                color: THEME.textColor,
                margin: 4
            },
            axisTick: { show: true }
        };
    }
}

class LithologyTrack extends BaseTrack {
    getSeries(index) {
        if (!this.data || !this.data.data) return [];

        const dataItems = (this.data.data || []).map(item => {
            let style = { borderColor: THEME.borderColor, borderWidth: 0.5 };
            if (item.lithology) {
                const img = document.getElementById(`pat-${item.lithology}`);
                if (img) style.color = { image: img, repeat: 'repeat' };
                else style.color = item.color || '#cbd5e0';
            } else {
                style.color = item.color || '#fff';
            }
            return { 
                name: item.name || item.description, 
                value: [0, 1, item.top, item.bottom], 
                itemStyle: style, 
                shape: item.shape 
            };
        });

        return [{
            type: 'custom', 
            xAxisIndex: index, 
            yAxisIndex: index,
            renderItem: (params, api) => {
                if (!params.data) return null;

                const yTop = api.coord([0, api.value(2)])[1];
                const yBot = api.coord([0, api.value(3)])[1];
                const xLeft = api.coord([0, 0])[0];
                const xRight = api.coord([1, 0])[0];
                const w = xRight - xLeft;
                const h = Math.abs(yBot - yTop);
                const midX = xLeft + w / 2;
                
                let shape;
                if (params.data.shape === 'triangle-up') {
                    shape = { type: 'polygon', shape: { points: [[xLeft, yBot], [xRight, yBot], [midX, yTop]] }, style: api.style() };
                } else if (params.data.shape === 'triangle-down') {
                    shape = { type: 'polygon', shape: { points: [[xLeft, yTop], [xRight, yTop], [midX, yBot]] }, style: api.style() };
                } else {
                    shape = { type: 'rect', shape: { x: xLeft, y: Math.min(yTop, yBot), width: w, height: h }, style: api.style() };
                }

                return {
                    type: 'group',
                    children: [
                        shape,
                        {
                            type: 'text',
                            rotation: this.data.textOrientation === 'vertical' ? Math.PI / 2 : 0,
                            style: {
                                text: params.data.name, 
                                x: midX, 
                                y: Math.min(yTop, yBot) + h / 2,
                                textAlign: 'center', 
                                textVerticalAlign: 'middle',
                                fill: THEME.textColor, 
                                fontWeight: 'bold', 
                                fontSize: 10
                            }
                        }
                    ]
                };
            },
            data: dataItems
        }];
    }
}

class IntervalTrack extends LithologyTrack {}

class TrackFactory {
    static createTrack(trackData) {
        switch (trackData.type) {
            case 'CurveTrack':
                return new CurveTrack(trackData);
            case 'DepthTrack':
                return new DepthTrack(trackData);
            case 'LithologyTrack':
                return new LithologyTrack(trackData);
            case 'IntervalTrack':
                return new IntervalTrack(trackData);
            default:
                console.warn(`Unknown track type: ${trackData.type}, fallback to BaseTrack`);
                return new BaseTrack(trackData);
        }
    }
}

export class WellLogChart {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`Container #${containerId} not found`);
        }
        // 默认初始化为 canvas 渲染
        this.chart = echarts.init(this.container, null, { renderer: 'canvas' });
        this.currentOptions = {};
        this._lastData = null;
        
        // 监听窗口大小变化，并保存绑定函数以便解绑
        this._resizeHandler = () => {
            if (this.chart) this.chart.resize();
        };
        window.addEventListener('resize', this._resizeHandler);
    }

    dispose() {
        if (this._resizeHandler) {
            window.removeEventListener('resize', this._resizeHandler);
            this._resizeHandler = null;
        }
        if (this.chart && !this.chart.isDisposed()) {
            this.chart.dispose();
            this.chart = null;
        }
    }

    render(wellLogData) {
        console.log("Rendering well data", wellLogData);
        if (!wellLogData) return;
        
        try {
            this._lastData = wellLogData;
            this.currentOptions = this._buildEChartsOption(wellLogData);
            this.chart.setOption(this.currentOptions, true);
        } catch (err) {
            console.error("Error during ECharts render:", err);
        }
    }

    exportToSvg() {
        if (!this._lastData) return '';
        
        // 1. 创建一个临时的、不可见的 DOM 容器
        const tempContainer = document.createElement('div');
        tempContainer.style.position = 'absolute';
        tempContainer.style.top = '-9999px';
        tempContainer.style.width = this.container.clientWidth + 'px';
        tempContainer.style.height = (this.container.scrollHeight || 2000) + 'px'; 
        document.body.appendChild(tempContainer);
        
        try {
            // 2. 使用 'svg' 渲染器初始化
            const exportChart = echarts.init(tempContainer, null, { renderer: 'svg' });
            
            // 3. 构建全新的 Option
            const exportOptions = this._buildEChartsOption(this._lastData);
            if (exportOptions.dataZoom) {
                delete exportOptions.dataZoom;
            }
            exportOptions.textStyle = { fontFamily: '"Microsoft YaHei", "SimHei", sans-serif' };
            exportOptions.animation = false;

            exportChart.setOption(exportOptions, true);
            
            // 4. 提取 SVG DOM
            const svgNode = tempContainer.querySelector('svg');
            const svgString = svgNode ? svgNode.outerHTML : '';
            
            exportChart.dispose();
            return svgString;
        } finally {
            tempContainer.remove();
        }
    }
    
    _buildEChartsOption(data) {
        const metadata = data.metadata || { wellName: 'Unknown Well', topDepth: 0, bottomDepth: 1000 };
        const trackDatas = data.tracks || [];
        const grids = [];
        const xAxes = [];
        const yAxes = [];
        const series = [];
        const graphics = [];
        
        // --- 精确物理布局计算器 ---
        const totalWeight = trackDatas.reduce((sum, t) => sum + (t.width || 10), 0);
        const availableWidth = 98; // % 留出 2% 边距
        let currentLeft = 1; // % 从 1% 开始
        
        const GRID_TOP = THEME.headerHeight + THEME.subHeaderHeight + 10; // px
        const HEADER_TOP_Y = 5; // px
        const HEADER_SUB_Y = THEME.headerHeight + 5; // px

        // 1. 实例化轨道并计算位置
        const tracks = [];
        const groups = [];
        let activeGroup = null;
        
        trackDatas.forEach((trackData) => {
            const track = TrackFactory.createTrack(trackData);
            
            // 计算归一化后的百分比宽度
            const actualWidth = ((trackData.width || 10) / totalWeight) * availableWidth;
            track.width = actualWidth; 
            
            const gName = track.parentGroup;
            if (gName) {
                if (!activeGroup || activeGroup.name !== gName) {
                    activeGroup = { name: gName, startLeft: currentLeft, width: 0 };
                    groups.push(activeGroup);
                }
                activeGroup.width += actualWidth;
            } else {
                activeGroup = null;
            }
            
            track.setCalculatedLeft(currentLeft);
            currentLeft += actualWidth;
            tracks.push(track);
        });

        // 2. 渲染父组标题 (Group Headers)
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

        // 3. 通用 Y 轴配置
        const commonY = {
            type: 'value',
            inverse: true,
            min: metadata.topDepth,
            max: metadata.bottomDepth,
            axisLine: { show: true, lineStyle: { color: THEME.borderColor } },
            axisTick: { show: true },
            splitLine: { 
                show: true, 
                lineStyle: { color: THEME.gridLineColor, type: 'solid' } 
            }
        };

        // 4. 处理各轨道配置
        tracks.forEach((track, index) => {
            const hasParent = !!track.parentGroup;
            
            grids.push(track.getGrid(index, GRID_TOP, '5%'));
            
            const titleTop = hasParent ? HEADER_SUB_Y : HEADER_TOP_Y;
            const titleHeight = hasParent ? THEME.subHeaderHeight : (THEME.headerHeight + THEME.subHeaderHeight);
            
            graphics.push(track.getGraphicElements(index, titleTop, titleHeight, hasParent));

            yAxes.push(track.getYAxis(index, commonY));
            xAxes.push(track.getXAxis(index));
            series.push(...track.getSeries(index));
        });

        return {
            graphic: graphics,
            grid: grids,
            xAxis: xAxes,
            yAxis: yAxes,
            series: series,
            tooltip: { trigger: 'axis' },
            dataZoom: [
                { type: 'inside', yAxisIndex: grids.map((_, i) => i) }, 
                { type: 'slider', yAxisIndex: grids.map((_, i) => i), right: 5 }
            ],
            backgroundColor: '#ffffff'
        };
    }
}
