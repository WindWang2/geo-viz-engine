import * as echarts from 'echarts';

export class WellLogChart {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        // 默认初始化为 canvas 渲染
        this.chart = echarts.init(this.container, null, { renderer: 'canvas' });
        this.currentOptions = {};
        
        // 监听窗口大小变化，并保存绑定函数以便解绑
        this._resizeHandler = () => {
            this.chart.resize();
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
        this.currentOptions = this._buildEChartsOption(wellLogData);
        this.chart.setOption(this.currentOptions, true);
    }

    exportToSvg() {
        // 1. 创建一个临时的、不可见的 DOM 容器
        const tempContainer = document.createElement('div');
        // 必须设置确切的宽高，否则 ECharts 无法渲染
        tempContainer.style.width = this.container.clientWidth + 'px';
        tempContainer.style.height = this.container.scrollHeight + 'px'; // 导出全长
        
        // 2. 使用 'svg' 渲染器初始化
        const exportChart = echarts.init(tempContainer, null, { renderer: 'svg' });
        
        // 3. 复制当前的 Option，为了防止全长压缩，移除 dataZoom 或设定起止
        const exportOptions = JSON.parse(JSON.stringify(this.currentOptions));
        if (exportOptions.dataZoom) {
            delete exportOptions.dataZoom; // 导出全图
        }
        // 强制确保全局字体包含中文字库，这很关键
        exportOptions.textStyle = { fontFamily: '"Microsoft YaHei", "SimHei", sans-serif' };

        exportChart.setOption(exportOptions, true);
        
        // 4. 提取 SVG DOM
        let svgString = tempContainer.querySelector('svg').outerHTML;
        
        // 清理
        exportChart.dispose();
        
        return svgString;
    }
    
    _buildEChartsOption(data) {
        const metadata = data?.metadata || { wellName: 'Unknown Well', topDepth: 0, bottomDepth: 1000 };
        const tracks = data?.tracks || [];
        const grids = [];
        const xAxes = [];
        const yAxes = [];
        const series = [];
        
        let currentLeft = 5; // 左侧初始边距 %
        
        // 唯一共享的深度轴（倒序）
        yAxes.push({
            type: 'value',
            inverse: true,
            min: metadata.topDepth,
            max: metadata.bottomDepth,
            gridIndex: 0,
            position: 'left',
            axisLine: { onZero: false }
        });

        tracks.forEach((track, index) => {
            const trackWidthStr = track.width || 15; // 使用传入的百分比宽度或默认15%
            
            // 1. 配置独立的 Grid
            grids.push({
                left: `${currentLeft}%`,
                width: `${trackWidthStr}%`,
                top: '10%',
                bottom: '5%'
            });
            
            // 2. 为非第一道的网格同步不可见的 Y 轴
            if (index > 0) {
                yAxes.push({
                    type: 'value', inverse: true, min: metadata.topDepth, max: metadata.bottomDepth,
                    gridIndex: index, show: false
                });
            }
            
            if (track.type === 'CurveTrack') {
                // X 轴位于顶部
                xAxes.push({
                    type: 'value', gridIndex: index, position: 'top',
                    name: track.series.map(s => s.name).join('/'),
                    nameLocation: 'middle', nameGap: 25
                });
                
                // 将数据 [depth, val] 转换为 [val, depth] 以适应 X/Y
                track.series.forEach(s => {
                    series.push({
                        name: s.name,
                        type: 'line',
                        xAxisIndex: index,
                        yAxisIndex: index,
                        data: s.data.map(point => [point[1], point[0]]),
                        itemStyle: { color: s.color },
                        showSymbol: false,
                        lineStyle: { width: 1 }
                    });
                });
            } else if (track.type === 'LithologyTrack') {
                // X 轴对岩性道无意义，隐藏
                xAxes.push({
                    type: 'value', gridIndex: index, show: false, min: 0, max: 1, position: 'top', name: '岩性'
                });
                
                // 将岩性区间映射为 custom series 渲染矩形
                const dataItems = track.data.map(item => {
                    let imagePattern = null;
                    const imgEl = document.getElementById(`pat-${item.lithology}`);
                    if (imgEl) {
                         imagePattern = { image: imgEl, repeat: 'repeat' };
                    }
                    return {
                        name: item.description,
                        value: [
                            0, // x start
                            1, // x end
                            item.top, // y top
                            item.bottom // y bot
                        ],
                        itemStyle: {
                            color: imagePattern || item.color || '#ccc',
                            borderColor: '#333',
                            borderWidth: 1
                        }
                    };
                });

                series.push({
                    type: 'custom',
                    xAxisIndex: index,
                    yAxisIndex: index,
                    renderItem: (params, api) => {
                        const yTop = api.coord([0, api.value(2)])[1];
                        const yBot = api.coord([0, api.value(3)])[1];
                        const xLeft = api.coord([0, 0])[0];
                        const xRight = api.coord([1, 0])[0];
                        
                        return {
                            type: 'rect',
                            shape: { x: xLeft, y: yTop, width: xRight - xLeft, height: yBot - yTop },
                            style: api.style()
                        };
                    },
                    data: dataItems
                });
            }
            
            currentLeft += trackWidthStr + 2; // +2% 为间隔
        });

        return {
            title: { text: metadata.wellName, left: 'center' },
            tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
            dataZoom: [
                { type: 'inside', yAxisIndex: grids.map((_, i) => i) },
                { type: 'slider', yAxisIndex: grids.map((_, i) => i), right: 10 } // 增加可视化缩放条
            ],
            grid: grids,
            xAxis: xAxes,
            yAxis: yAxes,
            series: series
        };
    }
}