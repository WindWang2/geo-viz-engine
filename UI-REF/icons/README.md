# GeoViz Engine — 图标系统 / Icon Pack

线性图标库 · 24×24 网格 · 描边 1.6px · 圆角端点 · currentColor 跟随主题

## 结构
- nav/   导航图标（8 个核心模块）
- ui/    功能图标（30 个）
- brand/ 品牌标记（geoviz-mark.svg, 64×64, 蓝铜渐变）

## 用法
所有图标 stroke="currentColor"，可用 CSS color 改色：
```html
<img src="icons/nav/well.svg" width="20" style="filter:none">
<!-- 或内联后用 color 控制 -->
<span style="color:#1f66d4"><!-- inline svg --></span>
```
建议主色 #1f66d4（蓝铜）；中性描边 #586878。

## 清单
导航：map=地图总览、paleo=古地理图、well=井剖面、cross=连井对比、seismic=地震3D、plots=平面图件、data=数据管理、tools=工具箱
功能：search=搜索、settings=设置、layers=图层、export=导出、download=下载、upload=导入、zoomIn=放大、zoomOut=缩小、fit=适应、ruler=量距、compass=指北、play=播放、undo=撤销、redo=重做、plus=新建、filter=筛选、pin=井位、fault=断层、grid3d=体网格、table=表格、wave=波形、contour=等值线、chevR=箭头、globe=语言、palette=色标、convert=转换、share=分享、doc=文档、check=校验、crosshair=标定
