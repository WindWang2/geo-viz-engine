import { WellLogChart } from './geoviz-echarts-wellog.js';

const mockData = {
    metadata: { wellName: "Test Well 1", topDepth: 1000, bottomDepth: 1100 },
    tracks: []
};

document.addEventListener('DOMContentLoaded', () => {
    const chartEngine = new WellLogChart('chart-container');
    chartEngine.render(mockData);
    // 挂载到 window 供控制台测试
    window.geoviz = chartEngine;
});