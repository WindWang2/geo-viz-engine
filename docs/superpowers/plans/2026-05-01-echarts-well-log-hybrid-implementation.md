# ECharts 混合渲染架构实现计划 (Geoviz ECharts Well-Log)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 PySide6 的测井图渲染引擎从 `pyqtgraph` 迁移为内嵌的 `QWebEngineView`，并基于 Apache ECharts 实现专门的 `geoviz-echarts-wellog` 前端包，支持岩性纹理填充和高保真 SVG 导出。

**Architecture:** PySide6 负责数据读取和管理，通过 QWebChannel 将 JSON 传给内嵌的本地 HTML 页面。HTML 页面挂载基于 ECharts 封装的 `WellLogChart` 组件。前端实现曲线绘制、岩性纹理贴图，并提供特定的 SVG 文本导出接口。

**Tech Stack:** PySide6, PyQtWebEngine, Python, Apache ECharts, JavaScript (ES6+), Vite.

---

## 阶段 1：前端基建与 ECharts 封装 (独立在纯 Web 环境下开发)

此阶段不涉及任何 Python 代码，我们将在 `src-echarts/` 目录下搭建并开发 `geoviz-echarts-wellog` 包的核心逻辑。

### Task 1: 初始化 Vite 项目与 ECharts 依赖

**Files:**
- Create: `src-echarts/package.json`
- Create: `src-echarts/vite.config.js`
- Create: `src-echarts/index.html`
- Create: `src-echarts/src/main.js`
- Create: `src-echarts/src/geoviz-echarts-wellog.js`

- [ ] **Step 1: 创建目录并初始化 Vite 配置**

```bash
mkdir -p src-echarts/src
cd src-echarts
npm init -y
npm install echarts qwebchannel
npm install --save-dev vite
```

创建 `vite.config.js`:
```javascript
import { defineConfig } from 'vite';

export default defineConfig({
  build: {
    // 编译为一个单独的文件，方便被 PySide6 加载
    rollupOptions: {
      output: {
        entryFileNames: `assets/[name].js`,
        chunkFileNames: `assets/[name].js`,
        assetFileNames: `assets/[name].[ext]`
      }
    }
  }
});
```

创建 `src/geoviz-echarts-wellog.js` (基础框架):
```javascript
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
```

- [ ] **Step 2: 创建测试入口页面 `index.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>ECharts Well-Log Dev</title>
    <style>
        body, html { margin: 0; padding: 0; width: 100%; height: 100%; }
        #chart-container { width: 100%; height: 100%; }
    </style>
</head>
<body>
    <div id="chart-container"></div>
    <script type="module" src="/src/main.js"></script>
</body>
</html>
```

- [ ] **Step 3: 编写 `main.js` 提供 Mock 数据测试**

```javascript
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
```

- [ ] **Step 4: 运行并验证**

```bash
cd src-echarts && npm run dev
```
验证浏览器出现 "Test Well 1" 标题。

- [ ] **Step 5: 提交**
```bash
git add src-echarts/
git commit -m "feat(web): initialize echarts well-log frontend package"
```

### Task 2: 实现核心轨道引擎 (Track Engine - 曲线道)

这里我们将解析 `CurveTrack` 数据，将其映射为 ECharts 的多 `grid` 和并排的 `xAxis`。

**Files:**
- Modify: `src-echarts/src/geoviz-echarts-wellog.js`
- Modify: `src-echarts/src/main.js`

- [ ] **Step 1: 在 `geoviz-echarts-wellog.js` 中实现 Grid 布局计算**

修改 `_buildEChartsOption`:

```javascript
    _buildEChartsOption(data) {
        const { metadata, tracks } = data;
        const grids = [];
        const xAxes = [];
        const yAxes = [];
        const series = [];
        
        let currentLeft = 5; // 左侧初始边距 %
        const trackWidthStr = 15; // 假设每道宽度 15%
        
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
            }
            
            currentLeft += trackWidthStr + 2; // +2% 为间隔
        });

        return {
            title: { text: metadata.wellName, left: 'center' },
            tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
            dataZoom: [{ type: 'inside', yAxisIndex: grids.map((_, i) => i) }], // 深度统一缩放
            grid: grids,
            xAxis: xAxes,
            yAxis: yAxes,
            series: series
        };
    }
```

- [ ] **Step 2: 在 `main.js` 加入曲线测试数据**

```javascript
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
```

- [ ] **Step 3: 运行验证**
在浏览器中确认出现了两列图表，第一列包含红色和绿色两条曲线，第二列包含蓝色曲线。鼠标滚轮可实现所有列的深度同步缩放。

- [ ] **Step 4: 提交**
```bash
git add src-echarts/src/
git commit -m "feat(web): implement track grid layout and curve rendering"
```

### Task 3: 岩性纹理填充支持 (Texture Fills)

**Files:**
- Modify: `src-echarts/src/geoviz-echarts-wellog.js`
- Modify: `src-echarts/src/main.js`

- [ ] **Step 1: 在 HTML 中注入 Base64 纹理测试资产**

修改 `index.html` 的 `head`，添加一些隐式的 img 标签（模拟未来 Python 注入的行为）：
```html
    <!-- 简化的 SVG Base64，代表砂岩 (点状) -->
    <img id="pat-sandstone" src="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMCIgaGVpZ2h0PSIxMCI+PGNpcmNsZSBjeD0iNSIgY3k9IjUiIHI9IjEiIGZpbGw9ImJsYWNrIi8+PC9zdmc+" style="display:none;">
```

- [ ] **Step 2: 处理 LithologyTrack 逻辑**

在 `_buildEChartsOption` 中的 `tracks.forEach` 循环内加入分支：

```javascript
            if (track.type === 'CurveTrack') {
                // ... 之前的代码
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
```

- [ ] **Step 3: 更新 Mock 数据测试**

在 `main.js` 添加 `LithologyTrack` 数据：
```javascript
        {
            type: "LithologyTrack",
            data: [
                { top: 1000, bottom: 1050, lithology: "sandstone", description: "细砂岩" },
                { top: 1050, bottom: 1100, color: "#a52a2a", description: "泥岩(无纹理)" }
            ]
        }
```

- [ ] **Step 4: 运行并验证**
检查第三列是否出现了矩形，上半部分用圆点 SVG 重复填充，下半部分为纯色。

- [ ] **Step 5: 提交**
```bash
git commit -am "feat(web): implement custom series for lithology texture filling"
```

### Task 4: 实现高保真 SVG 导出接口 (带 CJK 修复)

**Files:**
- Modify: `src-echarts/src/geoviz-echarts-wellog.js`

- [ ] **Step 1: 添加导出方法**

```javascript
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
```

- [ ] **Step 2: 添加全局挂载，供后续 QWebChannel 调用**
在 `main.js` 末尾：
```javascript
window.exportChartToSvg = function() {
    return window.geoviz.exportToSvg();
};
```

- [ ] **Step 3: 构建产物**
```bash
npm run build
```
这将在 `src-echarts/dist` 生成静态文件。

- [ ] **Step 4: 提交**
```bash
git commit -am "feat(web): add exportToSvg pipeline with CJK font support"
```

---

## 阶段 2：PySide6 宿主集成

在 Python 端引入 `QWebEngineView` 并打通 `QWebChannel`。

### Task 5: 配置 Python QWebChannel 与宿主页面

我们需要安装依赖并在 Python 中提供一个桥接对象。

**Files:**
- Modify: `src/renderers/well_log/chart_engine.py` (废弃 pyqtgraph, 改用 WebEngine)
- Modify: `pyproject.toml` 或 `src-python/requirements.txt` (如果还没加 PySide6-WebEngine)

- [ ] **Step 1: 安装依赖 (假定已在虚拟环境)**
```bash
pip install PySide6-WebEngine
```
*注意：如果没有，可能需要在项目根配置中添加此依赖。*

- [ ] **Step 2: 修改 `chart_engine.py` 为 QWebEngineView**

```python
import json
import os
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtCore import QObject, Slot, Signal

class Bridge(QObject):
    # 此信号由于 Web 准备就绪时发出
    ready = Signal()
    # 接收导出的 SVG
    svg_received = Signal(str)

    @Slot()
    def web_ready(self):
        self.ready.emit()

    @Slot(str)
    def receive_svg(self, svg_str: str):
        self.svg_received.emit(svg_str)

class ChartEngine(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.view = QWebEngineView()
        self.layout.addWidget(self.view)
        
        # 配置 WebChannel
        self.channel = QWebChannel()
        self.bridge = Bridge()
        self.channel.registerObject("bridge", self.bridge)
        self.view.page().setWebChannel(self.channel)
        
        # 加载本地打包好的页面
        # 实际项目中应将 src-echarts/dist 复制到可被正确引用的路径
        dist_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../src-echarts/dist/index.html"))
        if os.path.exists(dist_path):
            self.view.load(f"file://{dist_path}")
            
    def render_data(self, well_data_json: str):
        # 调用 JS 函数 render()
        self.view.page().runJavaScript(f"window.geoviz.render({well_data_json});")
        
    def export_svg(self):
        # 调用 JS，然后把返回值发给 Python
        js = """
        var svgStr = window.exportChartToSvg();
        bridge.receive_svg(svgStr);
        """
        self.view.page().runJavaScript(js)
```

- [ ] **Step 3: 调整 HTML 接入 QWebChannel**
修改 `src-echarts/index.html`，引入 qwebchannel.js (通过静态包含或直接写入)：

在 `<head>` 加上：
```html
<script src="qwebchannel.js"></script>
```
*(需将 PyQt 提供的 `qwebchannel.js` 放到 `src-echarts/public` 目录)*

在 `main.js` 初始化桥接：
```javascript
new QWebChannel(qt.webChannelTransport, function (channel) {
    window.bridge = channel.objects.bridge;
    window.bridge.web_ready();
});
```

- [ ] **Step 4: 提交**
```bash
git commit -am "feat(python): integrate QWebEngineView and QWebChannel bridge"
```

### Task 6: 联调与导出保存功能

**Files:**
- Modify: `src/pages/well_log_page.py`

- [ ] **Step 1: 在界面增加【导出SVG】按钮**

在 `WellLogPage` 的 Toolbar 增加按钮，连接到导出功能：
```python
    def on_export_clicked(self):
        # 监听 SVG 返回
        self.chart_engine.bridge.svg_received.connect(self.save_svg_to_disk)
        self.chart_engine.export_svg()
        
    def save_svg_to_disk(self, svg_str: str):
        self.chart_engine.bridge.svg_received.disconnect(self.save_svg_to_disk) # 避免重复触发
        
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "保存 SVG", "well_log.svg", "SVG Files (*.svg)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(svg_str)
```

- [ ] **Step 2: 转换实际加载逻辑 (Python -> JSON)**
将原先直接实例化 `CurveTrack` 对象的逻辑，改为构建上一阶段定义的 JSON 结构并序列化后传入 `self.chart_engine.render_data(json.dumps(payload))`。

- [ ] **Step 3: 运行验证**
在桌面端打开软件，验证测井图在 WebEngine 中高速渲染。点击“导出SVG”，保存文件。使用外部浏览器或 Illustrator 打开 SVG，确认岩性填充和中文均正常显示且未栅格化。

- [ ] **Step 4: 提交**
```bash
git commit -am "feat(python): implement SVG export save dialog and JSON data conversion"
```

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-01-echarts-well-log-hybrid-implementation.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**