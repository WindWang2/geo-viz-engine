const fs = require('fs');
const code = fs.readFileSync('src-echarts/src/geoviz-echarts-wellog.js', 'utf8');
console.log(code.match(/xAxisConfig\.triggerTooltip/g));
