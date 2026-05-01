import * as echarts from 'echarts';

export class WellLogChart {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        // 默认初始化为 canvas 渲染
        this.chart = echarts.init(this.container, null, { renderer: 'canvas' });
        this.currentOptions = {};
        
        // 监听窗口大小变化
        window.addEventListener('resize', () => {
            this.chart.resize();
        });
    }

    render(wellLogData) {
        this.currentOptions = this._buildEChartsOption(wellLogData);
        this.chart.setOption(this.currentOptions, true);
    }
    
    _buildEChartsOption(data) {
        // 占位
        return {
            title: { text: data.metadata.wellName }
        };
    }
}