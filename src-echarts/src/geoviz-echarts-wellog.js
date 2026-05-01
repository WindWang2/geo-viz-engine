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
        this._lastData = wellLogData;
        this.currentOptions = this._buildEChartsOption(wellLogData);
        this.chart.setOption(this.currentOptions, true);
    }

    exportToSvg() {
        // 1. 创建一个临时的、不可见的 DOM 容器
        const tempContainer = document.createElement('div');
        tempContainer.style.position = 'absolute';
        tempContainer.style.top = '-9999px'; // Hide off-screen
        // 必须设置确切的宽高，否则 ECharts 无法渲染
        tempContainer.style.width = this.container.clientWidth + 'px';
        tempContainer.style.height = this.container.scrollHeight + 'px'; // 导出全长
        document.body.appendChild(tempContainer);
        
        // 2. 使用 'svg' 渲染器初始化
        const exportChart = echarts.init(tempContainer, null, { renderer: 'svg' });
        
        // 3. 构建全新的 Option，避免 JSON 序列化导致函数丢失
        const exportOptions = this._buildEChartsOption(this._lastData);
        if (exportOptions.dataZoom) {
            delete exportOptions.dataZoom; // 导出全图
        }
        // 强制确保全局字体包含中文字库，这很关键
        exportOptions.textStyle = { fontFamily: '"Microsoft YaHei", "SimHei", sans-serif' };
        exportOptions.animation = false; // 保证同步渲染

        exportChart.setOption(exportOptions, true);
        
        // 4. 提取 SVG DOM
        const svgNode = tempContainer.querySelector('svg');
        const svgString = svgNode ? svgNode.outerHTML : '';
        
        // 清理
        exportChart.dispose();
        tempContainer.remove();
        
        return svgString;
    }
    
    _buildEChartsOption(data) {
        const metadata = data?.metadata || { wellName: 'Unknown Well', topDepth: 0, bottomDepth: 1000 };
        const tracks = data?.tracks || [];
        const grids = [];
        const xAxes = [];
        const yAxes = [];
        const series = [];
        const titles = [
            { text: metadata.wellName, left: 'center', top: '2%', textStyle: { fontSize: 16, fontWeight: 'bold' } }
        ];
        
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
            const trackWidth = Number(track.width || 15);
            
            // 1. 配置独立的 Grid
            grids.push({
                left: `${currentLeft}%`,
                width: `${trackWidth}%`,
                top: '12%',
                bottom: '5%'
            });

            // 表头标题逻辑
            let trackTitle = track.name || '';
            if (!trackTitle) {
                if (track.type === 'CurveTrack') {
                    trackTitle = track.series.map(s => s.name).join('/');
                } else if (track.type === 'LithologyTrack') {
                    trackTitle = '岩性';
                } else if (track.type === 'DepthTrack') {
                    trackTitle = '深度';
                } else {
                    trackTitle = '区间';
                }
            }

            titles.push({
                text: trackTitle,
                left: `${currentLeft + trackWidth / 2}%`,
                top: '7%',
                textAlign: 'center',
                backgroundColor: '#eee',
                borderColor: '#333',
                borderWidth: 1,
                padding: [2, 5],
                textStyle: { fontSize: 12, fontWeight: 'bold' }
            });
            
            // 2. 为非第一道的网格同步不可见的 Y 轴
            if (index > 0) {
                yAxes.push({
                    type: 'value', inverse: true, min: metadata.topDepth, max: metadata.bottomDepth,
                    gridIndex: index, show: false
                });
            }
            
            if (track.type === 'DepthTrack') {
                xAxes.push({ type: 'value', gridIndex: index, show: false });
                // 深度道显示 Y 轴刻度
                yAxes[index].show = true;
                yAxes[index].axisLabel = { show: true, fontWeight: 'bold' };
            } else if (track.type === 'CurveTrack') {
                // X 轴位于顶部
                xAxes.push({
                    type: 'value', gridIndex: index, position: 'top',
                    show: true, nameGap: 25 // 隐藏原本的 name，由 title 代替
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
                    type: 'value', gridIndex: index, show: false, min: 0, max: 1, position: 'top'
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
            } else if (track.type === 'IntervalTrack') {
                xAxes.push({
                    type: 'value', gridIndex: index, position: 'top',
                    show: true, min: 0, max: 1
                });
                
                const dataItems = (track.data || []).map(item => ({
                    name: item.name,
                    value: [0, 1, item.top, item.bottom],
                    itemStyle: { color: item.color || '#fff', borderColor: '#333', borderWidth: 1 },
                    shape: item.shape // 传递形状
                }));

                series.push({
                    type: 'custom',
                    xAxisIndex: index,
                    yAxisIndex: index,
                    renderItem: (params, api) => {
                        const yTop = api.coord([0, api.value(2)])[1];
                        const yBot = api.coord([0, api.value(3)])[1];
                        const xLeft = api.coord([0, 0])[0];
                        const xRight = api.coord([1, 0])[0];
                        const rectWidth = xRight - xLeft;
                        const rectHeight = Math.abs(yBot - yTop);
                        const yPos = Math.min(yTop, yBot);
                        
                        const shapeType = params.data.shape;
                        let graphicShape;
                        
                        if (shapeType === 'triangle-up') {
                            // TST (蓝色向上三角形 - 示意)
                            graphicShape = {
                                type: 'polygon',
                                shape: {
                                    points: [[xLeft, yBot], [xRight, yBot], [xLeft + rectWidth / 2, yTop]]
                                },
                                style: api.style()
                            };
                        } else if (shapeType === 'triangle-down') {
                            // HST (黄色向下三角形 - 示意)
                            graphicShape = {
                                type: 'polygon',
                                shape: {
                                    points: [[xLeft, yTop], [xRight, yTop], [xLeft + rectWidth / 2, yBot]]
                                },
                                style: api.style()
                            };
                        } else {
                            graphicShape = {
                                type: 'rect',
                                shape: { x: xLeft, y: yPos, width: rectWidth, height: rectHeight },
                                style: api.style()
                            };
                        }

                        return {
                            type: 'group',
                            children: [
                                graphicShape,
                                {
                                    type: 'text',
                                    rotation: track.textOrientation === 'vertical' ? Math.PI / 2 : 0,
                                    style: {
                                        text: params.data.name,
                                        x: xLeft + rectWidth / 2,
                                        y: yPos + rectHeight / 2,
                                        textAlign: 'center',
                                        textVerticalAlign: 'middle',
                                        fill: '#000',
                                        fontWeight: 'bold',
                                        fontSize: 12
                                    }
                                }
                            ]
                        };
                    },
                    data: dataItems
                });
            }
            
            currentLeft += trackWidth + 2; // +2% 为间隔
        });

        return {
            title: titles,
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