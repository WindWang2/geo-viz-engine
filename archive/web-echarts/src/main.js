import { WellLogChart, registerPatterns } from './geoviz-echarts-wellog.js';

const chartEngine = new WellLogChart('chart-container');
window.geoviz = chartEngine;

// Expose registerPatterns globally for Python to call
window.registerPatterns = function(patternsMap) {
    registerPatterns(patternsMap).then(() => {
        chartEngine.onPatternsReady();
    });
};

function initBridge() {
    if (typeof qt !== 'undefined' && qt.webChannelTransport) {
        new QWebChannel(qt.webChannelTransport, function (channel) {
            window.bridge = channel.objects.bridge;
            
            // Safe logging bridge
            const log = (msg) => { if (window.bridge && window.bridge.log) window.bridge.log(msg); };
            
            window.console.log = (...args) => log("[JS LOG] " + args.join(' '));
            window.console.error = (...args) => log("[JS ERROR] " + args.join(' '));

            log("JS Bridge Ready");
            window.bridge.web_ready();
        });
    }
}

document.addEventListener('DOMContentLoaded', initBridge);

window.exportChartToSvg = function() {
    return chartEngine.exportToSvg();
};
