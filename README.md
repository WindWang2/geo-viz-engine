# GeoViz Engine - 地质可视化引擎

基于 Tauri + WebView + Python 的地质数据可视化桌面应用。

## 技术架构

```
桌面壳: Tauri (Rust)
前端渲染: WebGL/WebGPU + D3.js + Three.js/CesiumJS
后端处理: Python (FastAPI + segyio + lasio + GDAL)
```

## 功能模块

- 测井可视化：标准测井道图、岩性柱状图、多井对比
- 地震可视化：剖面渲染、水平切片、任意线切割
- 平面图可视化：等值线/填色图、交互编辑
- 三维可视化：地质体、井轨迹（V2）
- 图件管理：PNG/PDF/SVG 导出

## 开发状态

🚧 项目规划中

## License

MIT
