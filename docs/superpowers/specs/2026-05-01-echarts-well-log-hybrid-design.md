# ECharts 混合渲染架构设计：测井可视化引擎 (Geoviz ECharts Well-Log)

## 背景与痛点

在迁移到 PySide6 单进程桌面架构（见 `2026-04-29-desktop-migration-pyside6-design.md`）后，我们通过 `pyqtgraph` 获得了极高的性能。然而，在实现**“高质量矢量图（SVG）导出”**以及**“复杂的岩性纹理（Pattern）填充”**时，桌面端原生绘图框架（Qt）与 Web 原生技术（如 D3.js）之间存在巨大的体验和质量鸿沟。

**核心挑战：**
1. 桌面原生框架的 SVG 导出经常出现图层错乱、纹理丢失、不支持 CSS 混合模式等问题。
2. 我们需要类似 `@equinor/videx-wellog` 的高度模块化“列/轨道（Track）”管理能力，能轻松应对多曲线合并、地层相区间的嵌套渲染。

## 架构决策：混合渲染架构 (Hybrid Web Rendering)

采用**“Python 核心 + Web 渲染”**的架构方案。具体来说，不在 Python 端进行最终的图表绘制，而是使用 `QWebEngineView` 嵌入一个基于 **Apache ECharts** 封装的专用 JavaScript 绘图包。

### 为什么选择 ECharts？
1. **高性能与矢量兼得：** ECharts 支持双渲染引擎（Canvas 和 SVG）。日常交互使用 Canvas/WebGL（极高帧率），导出时一键切换至 SVG 渲染器，获得完美的矢量图。
2. **多 Grid/Axis 支持：** 测井图的“多列同深度”布局，完美契合 ECharts 中的多个 `grid` 共享同一个垂直 `yAxis`（深度轴）的设计。
3. **纹理与自定义图案：** ECharts 的 `graphic` 组件和 `areaStyle` 支持载入 SVG Image 作为纹理填充（岩性 pattern）。

---

## 核心设计：`geoviz-echarts-wellog` 专用包

我们不仅是“在 Python 里写一点 JS 配置”，而是要沉淀出一个专用于测井数据的 ECharts 封装层，对标 `videx-wellog` 的体验。

### 1. 模块化组件设计 (Track-based API)

该 JS 包对外部（即 Python 宿主）暴露领域驱动的 API，而不是让 Python 去拼凑海量的 ECharts 配置项（Option）。

*   **`WellLogChart` (容器)：** 管理全局的 `dataZoom` (深度缩放)、统一的 `yAxis` 刻度，以及 ECharts 实例的生命周期。
*   **`CurveTrack` (测井曲线道)：** 自动配置 ECharts 的 `line` series。支持多条曲线在一列中合并显示，自动计算量程（min/max）。
*   **`LithologyTrack` (岩性道)：** 使用 ECharts 的 `custom` series 或组合的 `bar` series。关键在于其内部维护了一个**“岩性映射表”**，将“砂岩”等字符串自动映射为预加载的 SVG 纹理（`image://` 格式）。
*   **`IntervalTrack` (区间/相道)：** 渲染地层、沉积相（微相/亚相/相）。使用多级矩形块，内部处理文本居中与换行。

### 2. 岩性纹理填充 (Texture Fills) 方案

在 ECharts 中实现岩性 SVG 的重复填充是关键难点。

**方案：**
1. PySide6 启动时，将 `src/patterns/*.svg` 资产读取为 Base64 字符串（如 `data:image/svg+xml;base64,...`）。
2. 在初始化 JS 包时，将这些资源注册为 ECharts 可识别的模式（Pattern）。
3. 使用 ECharts 的对象配置：
   ```javascript
   areaStyle: {
       color: {
           image: document.getElementById('sandstone-img'), // 或 HTMLImageElement
           repeat: 'repeat'
       }
   }
   ```

### 3. 高保真 SVG 导出与一致性 (Export Consistency)

这是本架构的核心价值所在。必须保证屏幕所见即导出所得。

**导出管线 (The Export Pipeline)：**
1. 用户在 PySide6 界面点击【导出为 SVG】。
2. PySide6 通过 `QWebChannel` 向内部 JS 包发送 `trigger_export()` 信号。
3. JS 包**在内存中创建一个不可见的 ECharts 实例**，其渲染器强制设为 `'svg'`。
   ```javascript
   const exportChart = echarts.init(document.createElement('div'), null, { renderer: 'svg' });
   // 注入当前完全相同的 options
   exportChart.setOption(currentOptions); 
   ```
4. JS 包提取纯净的 `<svg>` DOM 字符串。
5. **字体后处理 (CJK Support)：** 遍历提取出的 SVG 字符串，确保 `<text>` 标签或全局 `<style>` 显式包含中文字体栈声明（如 `font-family: "Microsoft YaHei", "SimHei", sans-serif;`），防止在其他机器或 Adobe Illustrator 中打开时中文字符变成乱码（豆腐块）。
6. JS 通过 `QWebChannel` 将处理好的字符串返回给 Python。
7. Python 将字符串写入 `.svg` 文件。

---

## Python 与 JS 的数据桥接 (QWebChannel)

为了彻底解耦，定义统一的 JSON 数据契约。

### 1. 数据载荷 (JSON Payload)
Python 端的 `pandas` 将数据清洗后，转为如下结构的 JSON 传给 JS 端：

```json
{
  "metadata": { "wellName": "老龙1", "topDepth": 1000, "bottomDepth": 3000 },
  "tracks": [
    {
      "type": "CurveTrack",
      "width": 150,
      "series": [
        { "name": "GR", "data": [[1000, 45], [1000.1, 46], ...], "color": "#00FF00" }
      ]
    },
    {
      "type": "LithologyTrack",
      "width": 100,
      "data": [
        { "top": 1000, "bottom": 1200, "lithology": "sandstone", "description": "细砂岩" }
      ]
    }
  ]
}
```

### 2. 通信流程
1. PySide6 启动，加载 `index.html`（内含构建好的 JS 产物）。
2. JS 初始化完成后，通过 QWebChannel 发出 `Ready` 信号。
3. PySide6 接收到信号，发送第一批 JSON 数据 `load_well_data(payload)`。
4. ECharts 渲染。
5. PySide6 窗口 Resize 时，触发 ECharts 的 `resize()`。

---

## 落地路径建议

1. **环境准备：** 在项目中新建 `src-echarts/` 目录，使用 Vite 初始化一个原生的 JS/TS 项目，作为打包专用库。
2. **离线开发：** 先在纯浏览器环境下（Mock JSON 数据）开发 `geoviz-echarts-wellog` 包，跑通曲线、岩性纹理、中文显示和 SVG 纯文本导出功能。
3. **集成：** 编译 JS 产物（单一的 `.js` 和 `.css`），放入 PySide6 资源目录，打通 `QWebChannel` 链路。
4. **废弃：** 完全移除 `pyqtgraph` 和相关的 Python 图形渲染代码。