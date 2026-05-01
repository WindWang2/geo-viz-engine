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
    
    _buildEChartsOption(data) {
        // 占位
        return {
            title: { text: data.metadata.wellName }
        };
    }
}