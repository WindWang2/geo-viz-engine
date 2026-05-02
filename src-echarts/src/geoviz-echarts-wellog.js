import * as echarts from 'echarts';

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

    getTitles(index, top, hasParent) {
        const backgroundColor = hasParent ? '#ffffff' : '#f8fafc';
        return [{
            text: this.name,
            left: this._calculatedLeft + '%',
            width: this.width + '%',
            top: top,
            textAlign: 'center',
            backgroundColor: backgroundColor,
            borderColor: '#cbd5e0',
            borderWidth: 1,
            padding: [2, 0],
            textStyle: { fontSize: 11 }
        }];
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

    getTitles(index, top, hasParent) {
        let headerText = '{title|' + (this.name || '') + '}\n';
        const rich = { title: { fontWeight: 'bold', fontSize: 11 } };
        
        (this.data.series || []).forEach(s => {
            const line = s.lineStyle === 'dashed' ? '- - ' : '— ';
            const safeName = s.name.replace(/[^a-zA-Z0-9]/g, '_');
            headerText += `{${safeName}|${line}${s.name} ${s.rangeLabel || ''}}\n`;
            rich[safeName] = { color: s.color, fontSize: 10, fontWeight: 'bold' };
        });

        const backgroundColor = hasParent ? '#ffffff' : '#f8fafc';
        return [{
            text: headerText,
            left: this._calculatedLeft + '%',
            width: this.width + '%',
            top: top,
            textAlign: 'center',
            backgroundColor: backgroundColor,
            borderColor: '#cbd5e0',
            borderWidth: 1,
            padding: [2, 0],
            textStyle: { fontSize: 11, rich: rich }
        }];
    }
}

class DepthTrack extends BaseTrack {
    getYAxis(index, commonY) {
        return {
            ...commonY,
            gridIndex: index,
            show: true,
            axisLabel: { show: true, fontWeight: 'bold' }
        };
    }
}

class LithologyTrack extends BaseTrack {
    getSeries(index) {
        const dataItems = (this.data.data || []).map(item => {
            let style = { borderColor: '#94a3b8', borderWidth: 0.5 };
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
                                fill: '#1e293b', 
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
        const titles = [];
        
        let currentLeft = 1; // %
        const TRACK_GAP = 0.2;
        const GRID_TOP = '13%';
        const HEADER_TOP_Y = '4%';
        const HEADER_SUB_Y = '8.5%';

        // 1. Instantiate tracks and identify groups
        const tracks = [];
        const groups = [];
        let activeGroup = null;
        
        trackDatas.forEach((trackData) => {
            const track = TrackFactory.createTrack(trackData);
            const gName = track.parentGroup;
            if (gName) {
                if (!activeGroup || activeGroup.name !== gName) {
                    activeGroup = { name: gName, startLeft: currentLeft, width: 0 };
                    groups.push(activeGroup);
                }
                activeGroup.width += track.width + TRACK_GAP;
            } else {
                activeGroup = null;
            }
            track.setCalculatedLeft(currentLeft);
            currentLeft += track.width + TRACK_GAP;
            tracks.push(track);
        });

        // 2. Render parent group titles
        groups.forEach(g => {
            titles.push({
                text: g.name,
                left: g.startLeft + '%',
                width: (g.width - TRACK_GAP) + '%',
                top: HEADER_TOP_Y,
                textAlign: 'center',
                backgroundColor: '#f1f5f9',
                borderColor: '#94a3b8',
                borderWidth: 1,
                padding: [4, 0],
                textStyle: { fontSize: 12, fontWeight: 'bold', color: '#1e293b' }
            });
        });

        // 3. Common Y Axis config
        const commonY = {
            type: 'value',
            inverse: true,
            min: metadata.topDepth,
            max: metadata.bottomDepth,
            axisLine: { show: true, lineStyle: { color: '#94a3b8' } },
            axisTick: { show: true },
            splitLine: { 
                show: true, 
                lineStyle: { color: '#e2e8f0', type: 'solid' } 
            }
        };

        // 4. Process tracks
        tracks.forEach((track, index) => {
            const hasParent = !!track.parentGroup;
            
            grids.push(track.getGrid(index, GRID_TOP, '5%'));
            
            const trackTitles = track.getTitles(index, hasParent ? HEADER_SUB_Y : HEADER_TOP_Y, hasParent);
            titles.push(...trackTitles);

            yAxes.push(track.getYAxis(index, commonY));
            xAxes.push(track.getXAxis(index));
            series.push(...track.getSeries(index));
        });

        return {
            title: titles,
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
