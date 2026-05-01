import { WellLogChart } from './geoviz-echarts-wellog.js';

const mockData = {
    metadata: { wellName: "Test Well (Curves)", topDepth: 1000, bottomDepth: 1100 },
    tracks: [
        {
            type: "CurveTrack",
            series: [
                { name: "GR", color: "green", data: [[1000, 45], [1050, 80], [1100, 30]] },
                { name: "AC", color: "red", data: [[1000, 200], [1050, 180], [1100, 220]] }
            ]
        },
        {
            type: "CurveTrack",
            series: [
                { name: "RT", color: "blue", data: [[1000, 10], [1050, 50], [1100, 5]] }
            ]
        }
    ]
};

document.addEventListener('DOMContentLoaded', () => {
    const chartEngine = new WellLogChart('chart-container');
    chartEngine.render(mockData);
    // 挂载到 window 供控制台测试
    window.geoviz = chartEngine;
});