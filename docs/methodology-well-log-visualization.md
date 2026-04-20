# 测井数据可视化方法论文档

# 方法论：测井综合解释图可视化引擎

> **文档结构说明**：本方法论遵循"先整体后局部"的原则组织。第 1 章定义问题边界与核心挑战；第 2 章建立整体可视化模型机理（坐标系统、视觉编码、形式化映射）；第 3 章描述数据从原始形态到可视数据的变换过程；第 4 章逐层展开具体算法实现；第 5 章深入沉积相这一最复杂的子模块；第 6 章阐述配置驱动架构如何将上述一切组合为可复用引擎；第 7 章给出验证方法；第 8 章讨论整体布局与自适应策略。

## 1. 问题定义

测井综合解释图是一种面向地质工程师的专业可视化形式。它不是通用图表（如折线图、柱状图），而是一种由行业实践沉淀出来的**复合图表**——将一口井十余种不同性质的地质-地球物理数据沿同一根深度轴纵向排列，通过空间邻近关系表达数据间的成因关联。理解这种可视化的特殊性，是设计引擎的前提。

### 1.1 什么是测井综合解释图

测井综合解释图是将一口井的多种地质-地球物理数据沿深度轴并排排列的复合可视化图表。它本质上是**地质学家工作台的可视化投影**：将钻孔取心、录井、测井、古生物、沉积相等原始资料和解释结论，以标准化格式浓缩到一张图纸或屏幕视图中。地质工程师通过这张图完成"从数据到认识"的认知闭环——在同一视图中完成数据浏览、趋势判断、相关分析和解释验证。

其核心特征：

- **一维深度轴**：所有数据共享同一个深度坐标（米），构成统一的纵向参照系。深度轴向下递增，与钻井方向一致，这是测井图的行业惯例
- **多道并排**：不同类型的数据占据水平方向的不同列（道），通过空间邻近表达数据间的关联。例如岩性柱紧邻自然伽马曲线，便于工程师验证"砂岩段对应 GR 低值"
- **符号编码**：岩性和沉积相通过标准化的底纹图案（而非仅靠颜色）编码，确保黑白打印仍可识别。这是中国石油行业规范（GB/T 勘探管理图件图册编制规范）的硬性要求

### 1.2 可视化目标

测井综合解释图服务于地质工程师的日常工作流程，其可视化目标与认知任务一一对应。工程师在读取测井图时，眼睛完成的是一系列"水平扫描"——在同一深度上，从左到右横跨所有列道，对比地层、岩性、曲线值、沉积相、体系域之间的关系。这种**同深度水平关联**是测井图布局设计的根本驱动力。

| 目标 | 手段 | 对应认知任务 |
|------|------|-------------|
| 连续测井曲线的定量对比 | 多曲线同道叠加、共享深度轴 | 读值、趋势判断 |
| 岩性柱的快速识别 | 标准化 SVG 底纹图案 | 分类识别 |
| 沉积环境的层次理解 | 三级（微相/亚相/相）并排 | 层次归纳 |
| 层序地层的旋回分析 | 体系域三角形 + 层序边界 | 旋回识别 |
| 岩性-曲线-相的关联推理 | 同深度行的水平扫描 | 相关分析 |

### 1.3 核心挑战

实现一个通用的测井图引擎，需要在以下四个维度上同时取得平衡。这些挑战不是独立存在的，而是相互约束的——例如为了符号可区分性而增加图案复杂度，又会影响窄列中的渲染性能。引擎的设计决策必须在这些张力之间找到折中点。

1. **异构数据统一**：连续曲线（761 个采样点）vs 离散段（17 个岩性段 vs 8 个微相段），需在同一深度轴上对齐
2. **符号可区分性**：6 种岩性 + 10 种沉积相共 16 种底纹，需在 40-80px 宽的窄列中保持可辨识
3. **深度连续性**：确保底部不截断、段间无重叠线、曲线无锯齿
4. **可扩展性**：不同井的曲线组合、岩性类型、沉积相体系不同，引擎需配置驱动

## 2. 可视化模型机理

可视化模型机理是整个引擎的理论基础。它回答一个根本问题：**如何将地质数据映射为视觉元素，使得工程师的眼睛能在最短时间内完成正确的认知判断？** 本章从坐标系统、视觉编码模型和形式化定义三个层面建立这个映射的理论框架。后续所有算法都是这个理论框架的具体实现。

### 2.1 坐标系统

整个图表建立在 **深度-属性 双轴坐标系** 上。这个坐标系统的设计不是任意选择，而是由数据的物理本质决定的——深度是唯一的共享维度（所有数据都随深度变化），而不同属性的量纲和数值范围各不相同，不可能共享一个横向坐标轴。

```
深度轴（Y，纵向，向下递增）
    ┌─────────────────────────────────────────────────────────┐
    │  yScale: D³ 线性映射                                    │
    │  domain = [depth_start, maxDepth]  (米)                 │
    │  range  = [0, gridHeight]         (SVG像素)              │
    │  pixelRatio = 14 px/m                                    │
    │                                                          │
    │  转换公式:                                                │
    │    py = (depth - depth_start) × pixelRatio               │
    │    depth = py / pixelRatio + depth_start                  │
    └─────────────────────────────────────────────────────────┘

属性轴（X，横向，每道独立）
    每条曲线在自己的道内有独立的 xScale:
    xScale = d3.scaleLinear()
              .domain([display_min, display_max])  // 物理量程
              .range([colX + 2, colX + colWidth - 2])  // 像素范围
```

**关键设计决策**：深度轴全局共享（统一参照系），属性轴道内独立（各曲线量程不同）。

**为什么用 D3 的 `scaleLinear` 而非手动计算**：D3 尺度对象提供 `invert()` 方法，这是交互层坐标反算的基础。手动实现需要同时维护正向和反向公式，且容易在浮点精度上出错。D3 的 `scaleLinear` 将两者封装为一个不可分割的整体。

**深度轴的边界处理**：`yScale` 的 domain 为 `[depth_start, maxDepth]` 而非 `[depth_start, depth_end]`，这是因为某些段（如最后一个沉积相段）可能延伸到 `depth_end` 之下。取 `maxDepth = max(allItems.bottom, depth_end)` 确保所有数据都在可视范围内。range 为 `[0, gridHeight]`（而非从 `bodyStart` 开始），因为 body 已经通过 `transform: translate(0, bodyStart)` 偏移，所有渲染函数在 body 的局部坐标系内工作。

### 2.2 视觉编码模型

视觉编码模型定义了"数据→视觉元素"的映射规则。测井图中涉及六种数据类型，每种需要不同的视觉通道组合。选择视觉通道的依据是 Cleveland & McGill 的感知精度排序——位置编码最精确，颜色编码中等，图案编码适合分类。

```
数据类型          主要视觉通道          辅助通道
─────────────    ─────────────────    ──────────────────
测井曲线          位置(Y=深度,X=值)     颜色(区分曲线)、线型(实/虚)
岩性段            面积填充(图案)         颜色(底色分类)
沉积相段          面积填充(图案)         颜色(底色分类)、文字标注
地层段            矩形边界线            旋转文字标注
体系域            几何形状(三角形)       填充色(TST蓝/HST黄)
深度标尺          刻度线+数字           等间距(5m)
```

**为什么用图案而非纯色**：
- 地质行业标准要求黑白打印可辨识
- 同色系岩性（如"砂岩"vs"细砂岩"vs"粉砂岩"）仅靠颜色难以区分
- 图案携带语义信息（散点=碎屑颗粒、水平线=层理、砖块=化学沉积）

**视觉通道选择的认知科学依据**：

Cleveland & McGill（1984）的图形感知实验表明，人类对不同视觉通道的判断精度存在显著差异。从最精确到最不精确的排序为：位置 > 长度 > 角度/斜率 > 面积 > 体积 > 颜色色相 > 饱和度。测井图的视觉编码遵循这个排序原则：

- **曲线数据**使用位置编码（最精确），因为工程师需要定量读值（"这个深度的 GR 值是多少？"）
- **地层边界**使用位置 + 线段（精确），因为工程师需要精确定位深度界面
- **岩性/沉积相**使用面积 + 图案编码（中等精度），因为工程师只需要分类识别（"这是砂岩还是泥岩？"），不需要定量读值
- **颜色**只作为辅助通道（曲线区分、TST/HST 标识），不承载核心信息

这种"按认知任务精度需求选择通道"的策略，确保了每种数据类型都使用最合适的视觉通道，避免了信息过载和通道冲突。

### 2.3 深度-属性映射的形式化定义

为了消除自然语言描述的歧义，将整个可视化过程定义为一个可组合的函数。这个形式化定义使得每一个渲染步骤都可以独立测试和替换——这正是后续配置驱动架构的理论基础。

```
V: (Data, Config) → SVG

其中:
  Data  = { curves, intervals: { lithology, facies: {phase, sub_phase, micro_phase},
           systems_tract, sequence, series, system, formation } }
  Config = { columns: ColumnDef[], mappings, pixelRatio, ... }

V 的分解:
  V = Layout ∘ Render ∘ Encode

  Layout(D, C) → { colX[], gridHeight, yScale, totalWidth, totalHeight }
  Render(body, D, C, Layout) → SVG elements (rect, line, path, text)
  Encode(name, mapping) → fill pattern/color
```

## 3. 数据模型与变换

数据模型是连接原始数据与可视渲染的桥梁。测井图涉及的数据来源多样（Excel 表格、LAS 文件、人工解释成果），格式各异（连续采样 vs 离散区间），需要经过一套统一的变换链才能进入渲染管线。本章从变换链的全局视角出发，再逐个分析每种数据的几何特征和变换方法。

### 3.1 原始数据到可视数据的变换链

数据从原始来源到最终渲染需要经过四个阶段。每个阶段的职责边界清晰——parse 阶段只负责格式转换，不解释地质含义；transform 阶段只负责筛选和组织，不修改数值。这种严格的分层确保了数据流的可追溯性。

```
Excel (.xls) ──parse──→ Python Objects ──serialize──→ JSON ──deserialize──→ TypeScript Objects ──transform──→ Render Data

每步变换:
  parse:      Sheet → [{name, top, bottom}]  (11 个 sheet 独立解析)
  serialize:  Pydantic model → JSON           (类型安全)
  deserialize: JSON → TypeScript interface     (运行时类型)
  transform:  curves.filter(curveFilter)       (按道分组)
              intervals[key]                    (按列取数据)
```

### 3.2 两种数据几何

测井图中的所有数据可以归为两种几何类型：**连续点序列**（曲线）和**离散区间段**（岩性、沉积相、地层）。这两种几何的渲染策略截然不同——连续数据需要插值和路径生成，离散数据需要矩形绘制和图案填充。理解这种几何二分法是理解渲染管线设计的关键。

```
CurveData = {
  depth: number[761]    // 等间距 0.125m 采样
  data:  number[761]    // 对应深度点的测量值
}

可视化变换:
  1. 采样降频: 761点 → max 600点 (step = max(1, floor(N/600)))
  2. D3.line 插值: [{depth, val}] → SVG <path> d 属性
  3. xScale 映射: display_range → 列像素范围
```

**离散数据（段）**：顶底界定的区间

```
IntervalItem = { top: number, bottom: number, name: string }

可视化变换:
  1. yScale 映射: top → y1, bottom → y2 (像素坐标)
  2. 矩形生成: <rect x y width height>
  3. 填充映射: name → pattern/color (通过 Encode 函数)
```

### 3.3 沉积相层次数据模型

沉积相数据是测井图中最复杂的结构，因为它具有**层次性**——从粗粒度（相级）到细粒度（微相级）共三级。如何存储这种层次关系，直接影响渲染效率和编辑操作的一致性。我们选择了"平铺而非嵌套"的策略，这是一个经过权衡的关键设计决策。

```
FaciesData {
  phase:       IntervalItem[]   // 相级: "潮坪相"、"陆棚相"
  sub_phase:   IntervalItem[]   // 亚相级: "混积潮坪"、"碎屑岩浅水陆棚"
  micro_phase: IntervalItem[]   // 微相级: "砂坪"、"云质砂坪"、"泥质陆棚"
}
```

**为什么平铺而非嵌套**：

| 方面 | 嵌套树 | 平铺数组 |
|------|--------|---------|
| 渲染 | 需递归遍历 | 直接遍历 |
| 编辑 | 需维护父子一致性 | 各级独立修改 |
| 边界对齐 | 自动保证 | 数据质量保证 |
| 存储 | 冗余（父节点存深度范围） | 无冗余 |

**实际数据验证**（老龙1井，2515-2610m）：

```
微相(8段) → 亚相(6段) → 相(4段)

微相粒度: avg 11.9m/段 (最细)
亚相粒度: avg 15.8m/段
相粒度:   avg 23.8m/段 (最粗)

边界关系:
  微相边界 ⊂ 亚相边界 ⊂ 相边界 (理想情况)
  实际存在 0.1m 以内的对齐误差（数据质量决定）
```

### 3.4 岩性-沉积相的交叉关系

岩性柱和微相柱是**两套独立的分类体系**，但存在成因关联。岩性描述的是岩石的物理组成（矿物成分、粒度、颜色），而沉积相描述的是沉积环境的解释结论（潮坪、陆棚等）。它们之间的关系不是一对一的映射，而是一种多对多的成因关联——同一个沉积环境可以产出不同的岩石类型，同一种岩石也可以出现在不同的环境中。理解这种关系对于设计交互功能（如点击编辑后的数据一致性维护）至关重要。

```
岩性(物理属性)              微相(环境解释)
─────────────              ──────────────
深灰色砂质白云岩 ──────────→ 云质砂坪        (碳酸盐岩+砂质 → 潮坪环境)
灰色白云质细砂岩 ──────────→ 云质砂坪
浅灰色砂岩       ──────────→ 砂坪           (纯砂岩 → 高能潮坪)
深灰色泥质细砂岩 ──────────→ 砂泥质陆棚      (砂岩夹泥 → 陆棚过渡)
灰绿色页岩       ──────────→ 泥质陆棚        (纯泥质 → 低能陆棚)
紫红色泥岩       ──────────→ 泥质陆棚夹...   (复合微相)
灰色砂质白云岩   ──────────→ 砂质陆棚        (白云岩+砂质 → 混积陆棚)
```

**映射规则**：非严格一一对应。一个微相可对应多种岩性（如"砂泥质陆棚"对应砂岩、粉砂岩、泥岩），一种岩性也可出现在不同微相中。这是两个独立的地质解释维度。

## 4. 可视化算法

本章是方法论的核心实现层。在前面建立了模型机理和数据模型之后，这里给出每一步渲染的具体算法。算法以伪代码形式表达，既独立于编程语言，又足够精确到可以直接翻译为 D3.js/SVG 代码。按照渲染管线的执行顺序，依次介绍总体流程、布局计算、曲线绘制、底纹编码、图案设计、交互处理和导出功能。

### 4.1 总体渲染管线

渲染管线是整个引擎的主控制流。它采用**单次遍历、逐列分派**的策略——先计算全局布局参数（这些参数对所有列通用），然后遍历列配置，按列类型分派到对应的渲染函数。这种设计保证了添加新列类型时无需修改管线本身，只需添加新的渲染分支。

```
输入: WellLogData + ChartConfig
输出: SVG DOM

算法 RENDER(data, config):
  1. LAYOUT ← 计算布局参数(data, config)
  2. SVG    ← 创建画布(LAYOUT.totalWidth, LAYOUT.totalHeight)
  3. DEFS   ← SVG.append('defs')
     3a. REGISTER_PATTERNS(DEFS)           // 注册 16 种底纹
     3b. for i in 0..N:                     // 每列一个裁剪区
           DEFS.append('clipPath#clip-i')
  4. DRAW_TITLE(SVG, data, config)
  5. BODY ← DRAW_GRID(SVG, LAYOUT)         // 表头+网格+分割线
  6. for col in config.columns:             // 遍历列配置
       DRAW_COLUMN(BODY, col, data, LAYOUT) // 按类型分派渲染
  7. SETUP_INTERACTION(SVG, BODY, data)     // 十字准线+tooltip
  return SVG
```

### 4.2 布局计算算法

布局计算是渲染管线的第一步，也是唯一一个需要全局视角的步骤——它决定了 SVG 画布的总尺寸、每列的起始位置、深度到像素的映射函数。布局参数一旦确定，后续每个渲染函数只在自己的列范围内工作，互不干扰。这种"先全局后局部"的计算策略确保了列间对齐的正确性。

```
算法 LAYOUT(data, config):
  colWidths ← config.columns.map(c => c.width)
  totalWidth ← sum(colWidths)
  
  colX ← []
  for i, w in enumerate(colWidths):
    colX[i] ← sum(colWidths[0..i])
  
  allItems ← 所有 interval 段的并集
  maxDepth ← max(allItems.bottom, data.depth_end)
  
  gridHeight ← (maxDepth - data.depth_start) × config.pixelRatio
  bodyStart  ← 40 + HEADER_H1 + HEADER_H2    // 标题40 + 表头80
  totalHeight ← bodyStart + gridHeight + 2
  
  yScale ← linear_scale(
    domain = [data.depth_start, maxDepth],
    range  = [0, gridHeight]
  )
  
  return { colX, colWidths, totalWidth, totalHeight, gridHeight,
           bodyStart, yScale, maxDepth }
```

**关键不变量**：
- `totalHeight = bodyStart(120) + gridHeight + 2`（确保底部不截断）
- `maxDepth ≥ data.depth_end`（取所有段底界的最大值，防止段超出范围）
- `pixelRatio = 14 px/m`（经验值：在 A4 纵向打印时，95m 井段约 1330px，适合阅读）

**垂直布局分层**（从上到下，共 5 层）：

```
┌─────────────────────────────────────────────┐ y = 0
│              标题区 (40px)                    │  井名 + 深度范围
├─────────────────────────────────────────────┤ y = 40
│           表头第一行 (50px)                    │  列标签 + 曲线图例
├─────────────────────────────────────────────┤ y = 90
│           表头第二行 (30px)                    │  列子标签
├─────────────────────────────────────────────┤ y = 120 ← bodyStart
│                                              │
│              图表主体 (gridHeight px)          │  所有数据列在此渲染
│              body = <g transform="translate(  │  使用 <clipPath> 裁剪
│                0, bodyStart)">                │
│                                              │
├─────────────────────────────────────────────┤ y = 120 + gridHeight
│              底边线 (2px 余量)                 │  防止最后一段被截断
└─────────────────────────────────────────────┘ y = totalHeight
```

这个分层结构决定了所有渲染函数的坐标参考系：标题和表头直接添加到 `svg` 根元素（全局坐标），数据列添加到 `body` 组（局部坐标，原点在 bodyStart 处）。交互层的十字准线和 tooltip 也添加到 `body` 中，因此它们的 y 坐标直接对应 `yScale` 的 range 值，无需额外偏移。

### 4.3 曲线渲染算法

曲线渲染是测井图中计算量最大的部分。每条曲线包含数百个采样点，需要在 D3 的线性尺度下映射为 SVG `<path>` 元素。关键的性能优化是**降频采样**——在保证视觉无损的前提下减少实际绘制的点数。

```
算法 DRAW_CURVES(body, curves, colIdx, layout):
  x ← layout.colX[colIdx]
  w ← layout.colWidths[colIdx]
  g ← body.append('g', clip-path = 'url(#clip-colIdx)')
  
  for curve in curves:
    xScale ← linear_scale(
      domain = [curve.display_min, curve.display_max],
      range  = [x + 2, x + w - 2]
    )
    
    points ← curve.depth.map((d, i) => {depth: d, val: curve.data[i]})
    
    // 降频采样: 保留 ≤600 个点（性能优化）
    step ← max(1, floor(points.length / 600))
    sampled ← points.filter((_, i) => i % step == 0 OR i == last)
    
    // D3 路径生成
    lineGen ← d3.line()
      .x(d => xScale(d.val))
      .y(d => layout.yScale(d.depth))
    
    g.append('path')
      .attr('d', lineGen(sampled))
      .attr('stroke', curve.color)
      .attr('stroke-width', 1.2)
      .attr('stroke-dasharray', line_style_to_dash(curve.line_style))
```

**降频采样原理**：原始 761 点（0.125m 间隔），在 14px/m 下相邻点仅距 1.75px，SVG 渲染器无法区分。降至 600 点后每点间距 2.2px，视觉效果无损。

### 4.4 底纹图案编码算法

这是岩性和沉积相可视化的核心——将地质术语映射为可区分的 SVG 图案。编码算法的设计面临一个现实挑战：地质命名不统一。同一种岩石在不同井中可能有不同的描述方式（如"砂质白云岩"vs"含砂白云岩"），精确匹配会导致大量遗漏。因此我们选择了**关键词模糊匹配**策略，以映射表的定义顺序作为优先级，解决了复合名称的匹配歧义。

```
算法 ENCODE(name, mapping):
  // 第一步：图案匹配
  for (keyword, patternId) in mapping.patterns:  // 按表顺序
    if name.includes(keyword):
      return "url(#pat-{patternId})"              // SVG pattern 引用
  
  // 第二步：颜色兜底（无匹配图案时）
  for (keyword, color) in mapping.colors:
    if name.includes(keyword):
      return color                                // 纯色填充
  
  return '#f3f4f6'                                // 默认浅灰
```

**匹配策略分析**：选择 `includes()` 模糊匹配而非精确匹配的原因：

```
输入: "深灰色砂质白云岩"
  精确匹配: ❌ (需枚举所有可能的全称)
  关键词匹配: "白云岩" ∈ name → patternId = 'dolomite' ✅

输入: "泥质陆棚夹砂泥质陆棚"
  关键词匹配: 按映射表顺序
    "砂泥质" ∈ name? ❌
    "泥质"   ∈ name? ✅ → patternId = 'muddy_shelf'
```

**优先级问题**：映射表中的顺序即为匹配优先级。将更具体的词放在前面（如"砂泥质"在"砂质"前），避免误匹配。

### 4.5 SVG Pattern 设计算法

SVG `<pattern>` 是实现地质底纹的技术载体。每种底纹通过一个可平铺的"图案砖"（tile）定义，浏览器自动重复平铺覆盖整个矩形区域。设计图案砖时需要平衡三个目标：**语义可读性**（图案应反映岩石特征）、**可区分性**（不同图案必须一眼可辨）、**渲染性能**（基元数量控制在合理范围内）。

```
算法 CREATE_PATTERN(defs, id, background, primitives):
  pattern ← defs.append('pattern')
    .attr('id', 'pat-{id}')
    .attr('patternUnits', 'userSpaceOnUse')
    .attr('width', tileW)
    .attr('height', tileH)
  
  // 必选：背景底色矩形
  pattern.append('rect')
    .attr('width', tileW).attr('height', tileH)
    .attr('fill', background)
  
  // 可选：图案基元
  for primitive in primitives:
    pattern.append(primitive.tag)
      .set(primitive.attrs)
```

**6 种岩性图案的基元设计**（参考 GB/T 勘探管理图件图册编制规范 附录M）：

| 图案 | Tile 大小 | 基元 | 设计原理 |
|------|----------|------|---------|
| sandstone | 20×20 | 10 个 `<circle>` r=0.8-1.2 | 不规则散点模拟碎屑颗粒 |
| siltstone | 12×12 | 10 个 `<circle>` r=0.3-0.5 | 更小更密的点模拟粉砂级颗粒 |
| mudstone | 16×8 | 3 条不连续 `<line>` | 短横线模拟不连续水平层理 |
| shale | 16×6 | 2 条连续 `<line>` | 密集平行线模拟页理 |
| limestone | 24×16 | 6 条 `<line>` 组成砖块网格 | 砖块状模拟化学沉积块状构造 |
| dolomite | 16×16 | 2 条水平 `<line>` + 4 条斜 `<line>` | 菱形网格模拟白云石化晶粒 |

**10 种沉积相图案的基元设计**（参考 附录O 碳酸盐岩台地相）：

| 图案 | Tile | 基元 | 环境语义 |
|------|------|------|---------|
| tidal_flat | 20×10 | 2 条贝塞尔 `<path>` | 潮汐波状层理 |
| shelf | 16×8 | 2 条水平 `<line>` | 浅海稳定沉积 |
| sand_flat | 14×14 | 5 个 `<circle>` | 潮间砂质 |
| mud_flat | 16×8 | 2 条短 `<line>` | 潮间泥质 |
| mixed | 16×12 | 2 个 `<circle>` + 2 条 `<line>` | 混合沉积 |
| clastic_shelf | 14×10 | 3 条交错 `<line>` | 陆源碎屑输入 |
| dolomitic_flat | 16×12 | 2 个 `<circle>` + 2 条斜 `<line>` | 白云石化 |
| muddy_shelf | 12×8 | 3 条密集短 `<line>` | 悬浮质沉积 |
| sandy_shelf | 14×14 | 4 个 `<circle>` | 陆棚砂体 |
| sand_mud_shelf | 16×10 | 2 个 `<circle>` + 2 条 `<line>` | 砂泥互层 |

**区分度保证**：16 种图案通过 **基元类型**（circle/line/path）× **排列方式**（随机/平行/交错/网格）× **密度**（稀疏/中等/密集）的三维组合实现可区分性。

### 4.6 交互层算法

交互层为静态的 SVG 图表赋予"可查询"的能力。交互的核心机制是**坐标反算**——将鼠标在屏幕上的像素位置，通过 SVG 坐标变换矩阵（CTM）反算回深度坐标，然后在数据空间中完成查询和命中检测。这保证了无论 SVG 被缩放、平移还是嵌入滚动容器中，交互行为始终正确。

**交互层由三个视觉元素组成**：

1. **水平十字准线**：贯穿整个图表宽度的红色虚线，跟随鼠标纵向移动。它提供精确的深度定位参照，帮助工程师判断当前查看的深度位置。
2. **深度标签**：位于十字准线左端的红色小徽章，实时显示当前深度值（如 `2543.5m`）。它省去了工程师在深度标尺列中手动查找对应深度的认知负担。
3. **信息 Tooltip**：位于图表右上角的浮动面板，汇总显示当前深度下的所有数据值。Tooltip 的内容按"深度 → 曲线值 → 岩性 → 沉积相"的固定顺序排列，与图表的左到右列顺序一致，符合工程师的阅读习惯。

这三个元素全部添加到一个专门的 `interaction-layer` 组中，该组设置 `pointer-events: none` 以避免拦截鼠标事件。只有 Tooltip 内的矩形接收点击事件用于编辑功能。

```
算法 ON_MOUSEMOVE(event):
  // 坐标转换：屏幕像素 → SVG 本体坐标
  ctm ← bodyNode.getScreenCTM()
  mx ← (event.clientX - ctm.e) / ctm.a
  my ← (event.clientY - ctm.f) / ctm.d
  
  // 边界检查
  if my < 0 OR my > gridHeight OR mx < 0 OR mx > totalWidth:
    HIDE(crosshair, tooltip)
    return
  
  // 深度反算
  depth ← yScale.invert(my)
  
  // 曲线插值
  for curve in data.curves:
    value ← INTERPOLATE(curve, depth)
    // 线性插值: 找到 depth 两侧的采样点 (d0, v0) 和 (d1, v1)
    // v = v0 × (1-t) + v1 × t, 其中 t = (depth - d0) / (d1 - d0)
  
  // 段命中检测
  lithoHit ← intervals.lithology.find(iv => depth >= iv.top AND depth <= iv.bottom)
  for level in [micro_phase, sub_phase, phase]:
    faciesHit ← intervals.facies[level].find(iv => depth >= iv.top AND depth <= iv.bottom)
  
  // 更新视觉元素
  UPDATE(crosshair.y = my)
  UPDATE(tooltip.content = [depth, curves, litho, facies])
  UPDATE(tooltip.position = clamp(ty, 0, gridHeight - tooltipH))
```

#### 点击编辑

```
算法 ON_EDIT_CLICK(intervalArray, index, level, data):
  newName ← prompt('请输入新名称:', intervalArray[index].name)
  if newName == null OR newName.trim() == oldName:
    return  // 取消或未改
  
  updated ← structuredClone(data)              // 不可变更新
  updated.intervals.facies[level][index].name ← newName.trim()
  onDataChange(updated)                         // 触发 React 重渲染
```

### 4.7 导出算法

导出功能将浏览器中的动态 SVG 转化为可分发、可打印的静态文件。三种导出格式各有用途：SVG 保留矢量精度适合后续编辑，PNG 适合嵌入报告和演示，PDF 适合正式提交和打印。导出的关键技术挑战是**剥离交互层**（交互元素不应出现在导出结果中）和**保持图案完整性**（Canvas 渲染 SVG pattern 时需要正确的尺寸声明）。

```
算法 EXPORT_SVG(svgElement):
  cloned ← svgElement.cloneNode(true)
  cloned.querySelectorAll('.interaction-layer').remove()  // 移除交互层
  svgString ← XMLSerializer.serializeToString(cloned)
  download(svgString, 'wellName_start-endm.svg')

算法 EXPORT_PNG(svgElement, scale=3):
  canvas ← SVG_TO_CANVAS(svgElement, scale)   // 见下文
  download(canvas.toDataURL('image/png'), 'wellName_start-endm.png')

算法 SVG_TO_CANVAS(svgElement, scale):
  cloned ← svgElement.cloneNode(true)
  remove('.interaction-layer')
  blob ← Blob([serializeToString(cloned)], type='image/svg+xml')
  url ← URL.createObjectURL(blob)
  img ← Image(); img.src ← url
  await img.load()
  canvas ← Canvas(img.width × scale, img.height × scale)
  ctx ← canvas.getContext('2d')
  ctx.scale(scale, scale)
  ctx.fillStyle ← '#ffffff'
  ctx.fillRect(0, 0, img.width, img.height)
  ctx.drawImage(img, 0, 0)
  return canvas
```

### 4.8 性能与复杂度分析

测井图引擎的性能瓶颈不在计算，而在 SVG DOM 操作。理解每个渲染步骤的 DOM 输出量，是优化性能的基础。

**DOM 节点数量分析**（老龙1井基准）：

| 渲染步骤 | 产出 DOM 节点 | 占比 |
|---------|-------------|------|
| `<defs>` (pattern + clipPath) | 16 pattern × ~10 基元 + 14 clipPath ≈ 174 | 7% |
| 标题 + 表头 | ~30 (text, rect, line) | 1% |
| 网格线 | ~95 line (每 1m) + 13 colDivider | 4% |
| 6 条曲线 | 6 path (降频后) | <1% |
| 17 岩性段 | 17 × (rect + text) ≈ 34 | 1% |
| 18 沉积相段 (三级) | 18 × (rect + text + tspan) ≈ 54 | 2% |
| 8 体系域段 | 8 × (polygon/rect + text) ≈ 16 | <1% |
| 其他列 (地层、深度等) | ~80 | 3% |
| 交互层 | ~20 (line + rect + text) | <1% |
| **合计** | **~510** | |

**关键性能特征**：

- **DOM 规模与井段长度线性相关**：主要贡献者是网格线（每米一条）。100m 井段约 100 条线，1000m 井段约 1000 条。总 DOM 节点数 = O(depthRange × columns)。
- **曲线采样降频**将渲染复杂度从 O(N) 降到 O(600)，N 为原始采样点数。这意味着无论原始数据多密（0.125m 间距还是 0.01m 间距），每条曲线的 DOM 贡献始终是一个 `<path>` 元素。
- **React 重渲染开销**：当前实现在 `useEffect` 中执行 `svg.selectAll('*').remove()` 清空后重绘。这是一个"全量重绘"策略，在数据不变时（如窗口 resize）不会触发。数据变化时（如编辑沉积相名称），整个 SVG DOM 被重建。对于 ~510 个节点的规模，这个开销在 16ms 帧预算内完全可以接受。

**优化策略（按需启用）**：

| 场景 | 瓶颈 | 优化方案 |
|------|------|---------|
| 超深井 >1000m | DOM 节点 >5000 | 深度虚拟滚动（策略 C，见 8.3.3） |
| 高频编辑 | 全量重绘抖动 | D3 enter/update/exit 模式替代全量清除 |
| 多井并行 | 多个 SVG 实例 | Web Worker 预计算布局参数 |
| 导出大图 | Canvas 像素 >10000px | 分块渲染后拼接 |

### 4.9 边界条件与错误处理

测井图引擎需要处理一系列来自真实数据的边界条件。这些情况不常出现，但如果不处理会导致渲染崩溃或视觉错误。

**数据层面的边界条件**：

| 条件 | 表现 | 处理策略 |
|------|------|---------|
| 空数据（某类 interval 为空数组） | 对应列完全空白 | 正常渲染，不创建任何矩形 |
| 段间隙 >0（两段间有空隙） | 空隙处显示白色背景 | 允许，不自动填充 |
| 段重叠（两段深度范围交叉） | 矩形重叠渲染 | 后绘制的覆盖先绘制的，不报错 |
| 曲线数据为空 | 曲线列无路径 | 跳过 `g.append('path')` |
| 深度点超出 [start, end] 范围 | 曲线在列外绘制 | `clipPath` 自动裁剪 |

**渲染层面的边界条件**：

| 条件 | 表现 | 处理策略 |
|------|------|---------|
| 段高度 <8px | 文字放不下 | `if h > 10` 跳过文字，只画矩形 |
| 文字超出列宽 | 换行后仍超长 | `WRAP_TEXT` 的 `maxChars <= 0` 时跳过 |
| 映射表中无匹配项 | 无图案无颜色 | 返回默认浅灰 `#f3f4f6` |
| pattern 引用不存在 | SVG 无填充 | `lookupPattern` 返回 null 时回退到纯色 |
| 重复边界线（相邻段共享边界） | 视觉上加粗 | 接受——重叠线在 0.5px 级别不可感知 |

**交互层面的边界条件**：

| 条件 | 表现 | 处理策略 |
|------|------|---------|
| 鼠标移出图表区域 | 十字准线停在边缘 | `mouseleave` 事件隐藏所有交互元素 |
| Tooltip 超出网格高度 | 被裁剪 | `clamp(ty, 0, gridHeight - tooltipH)` |
| 用户取消编辑（prompt 点取消） | `newName == null` | 直接 return，不触发状态更新 |
| 用户输入空字符串 | `newName.trim() == ""` | 等同取消，不更新 |

## 5. 沉积相子模块分解与实现

沉积相是测井图中最复杂的数据维度——它既有多级层次结构（相→亚相→微相），又需要图案编码和交互编辑。本章将沉积相关能分解为四个职责明确的层次，从底层数据结构到顶层交互行为逐层展开。这种分层不是过度设计，而是由沉积相数据本身的复杂性决定的——每一层都可以独立测试、独立修改、甚至独立替换。

### 5.1 四层架构

四层架构将沉积相的实现划分为**数据→映射→渲染→交互**四个垂直层。每层只依赖下层的接口，不依赖具体实现。这种严格分层的好处是：修改映射策略（比如换一套图案）不影响渲染逻辑；修改交互方式（比如从弹窗改为下拉选择）不影响数据结构和映射规则。

```
┌─────────────────────────────────────────┐
│           交互层 (Interaction)          │  点击编辑、悬停 Tooltip
├─────────────────────────────────────────┤
│           渲染层 (Renderer)             │  SVG rect + pattern + text
├─────────────────────────────────────────┤
│           映射层 (Mapping)              │  中文术语 → 图案/颜色
├─────────────────────────────────────────┤
│           数据层 (Data)                 │  FaciesData 三级平铺结构
└─────────────────────────────────────────┘
```

每层的职责边界严格分离：

| 层 | 输入 | 输出 | 依赖 |
|----|------|------|------|
| 数据层 | Excel/JSON | `IntervalItem[]` | 无 |
| 映射层 | `name: string` | `patternId: string` | 映射配置表 |
| 渲染层 | `IntervalItem[]` + patternId | SVG DOM 节点 | 布局参数 |
| 交互层 | MouseEvent + data | UI 反馈 | 渲染层产物 |

### 5.2 数据层实现

数据层是整个沉积相模块的基石。它的职责是：定义数据如何存储、如何从原始来源解析、如何验证完整性。存储结构选择了"三级平铺数组"而非嵌套树——这是一个反直觉但正确的决策，因为渲染是扁平遍历而非递归展开，编辑是独立修改各级数组而非维护父子一致性。

```typescript
interface FaciesData {
  phase: IntervalItem[];       // 相: "潮坪相"、"陆棚相"
  sub_phase: IntervalItem[];   // 亚相: "混积潮坪"、"碎屑岩浅水陆棚"
  micro_phase: IntervalItem[]; // 微相: "砂坪"、"云质砂坪"、"泥质陆棚"
}
```

**解析算法**（从 Excel）：

```
算法 PARSE_FACIES_SHEET(sheet, sheetName):
  rows ← sheet.parse_rows()
  result ← []
  for row in rows:
    if row.name 非空:
      result.append({
        top:    parseFloat(row['顶深']),
        bottom: parseFloat(row['底深']),
        name:   row['名称'].trim()
      })
  
  // 按顶深排序（保证渲染顺序）
  result.sort((a, b) => a.top - b.top)
  
  // 验证连续性
  for i in 1..result.length:
    gap ← result[i].top - result[i-1].bottom
    assert gap < 0.5, "段间间隙过大: {gap}m at {result[i].top}m"
  
  return result
```

**层次约束验证**：

```
算法 VALIDATE_FACIES_HIERARCHY(facies):
  for micro in facies.micro_phase:
    sub ← facies.sub_phase.find(s => s.top <= micro.top AND s.bottom >= micro.bottom)
    assert sub != null, "微相 {micro.name} 未被任何亚相包含"
    // 检查微相名称与亚相名称的语义一致性
    assert is_consistent(micro.name, sub.name),
           "微相 {micro.name} 与亚相 {sub.name} 不一致"
  
  for sub in facies.sub_phase:
    phase ← facies.phase.find(p => p.top <= sub.top AND p.bottom >= sub.bottom)
    assert phase != null, "亚相 {sub.name} 未被任何相包含"
```

### 5.3 映射层实现

映射层是连接"地质术语"与"视觉编码"的桥梁。它解决的核心问题是：给定一个中文沉积相名称（如"砂泥质陆棚"），应该填充什么图案？映射层的设计需要在**覆盖率**（能匹配所有遇到的名称）和**精确性**（不误匹配相似但不同的名称）之间取得平衡。

```typescript
interface PatternMapping {
  patterns: Record<string, string>;  // 关键词 → 图案标识
  colors: Record<string, string>;    // 关键词 → 底色
}
```

**查找算法**（有序优先匹配）：

```
算法 LOOKUP(name, mapping):
  // Phase 1: 图案匹配
  entries ← Object.entries(mapping.patterns)  // 保持定义顺序
  for (keyword, patternId) in entries:
    if name.includes(keyword):
      return { type: 'pattern', value: "url(#pat-{patternId})" }
  
  // Phase 2: 颜色匹配
  for (keyword, color) in Object.entries(mapping.colors):
    if name.includes(keyword):
      return { type: 'color', value: color }
  
  // Phase 3: 默认
  return { type: 'color', value: '#f3f4f6' }
```

**优先级设计示例**：

```
映射表定义顺序（老龙1井）:
  "潮坪" → tidal_flat       // 优先级 1
  "陆棚" → shelf            // 优先级 2
  "砂坪" → sand_flat        // 优先级 3
  "泥坪" → mud_flat         // 优先级 4
  "混积" → mixed            // 优先级 5
  "碎屑岩" → clastic_shelf  // 优先级 6
  "云质" → dolomitic_flat   // 优先级 7
  "泥质" → muddy_shelf      // 优先级 8
  "砂质" → sandy_shelf      // 优先级 9
  "砂泥质" → sand_mud_shelf // 优先级 10

测试:
  "泥质陆棚夹砂泥质陆棚"
    → "砂泥质" ∉ "泥质陆棚夹砂泥质陆棚"? 
      "砂泥质" ∉? 让我们检查: "泥质陆棚夹砂泥质陆棚".includes("砂泥质") = true ✅
    → 匹配 "砂泥质" → sand_mud_shelf

注意: "砂泥质" 必须排在 "砂质" 和 "泥质" 之前!
  如果 "泥质" 在前: "泥质陆棚夹砂泥质陆棚".includes("泥质") = true → muddy_shelf (错误!)
```

### 5.4 渲染层实现

渲染层将映射结果转化为 SVG DOM 节点。它的工作是纯函数式的——给定一组区间段和映射结果，输出一组 SVG 元素。渲染层不需要知道数据从哪里来、图案是什么含义，只需要按照布局参数绘制矩形和文字。

```
算法 DRAW_FACIES_COLUMN(body, items, colIdx, level, ctx, onDataChange):
  x ← ctx.colX[colIdx]
  w ← ctx.colWidths[colIdx]
  g ← body.append('g', clip-path = 'url(#clip-colIdx)')
  
  for (iv, idx) in enumerate(items):
    y1 ← ctx.yScale(iv.top)
    h  ← ctx.yScale(iv.bottom) - y1
    
    // 编码：名称 → 填充
    fill ← ENCODE(iv.name, ctx.config.faciesMapping)
    
    // 渲染矩形
    g.append('rect')
      .attr('x', x+1).attr('y', y1)
      .attr('width', w-2).attr('height', h)
      .attr('fill', fill)
      .attr('stroke', '#00000030').attr('stroke-width', 0.5)
      .attr('cursor', 'pointer')
      .on('click', () => ON_EDIT_CLICK(items, idx, level, ctx.data))
    
    // 渲染文字（高度足够时）
    if h > 10:
      fs ← min(11, h × 0.5)             // 自适应字号
      t ← g.append('text')
        .attr('x', x + w/2).attr('y', y1 + h/2)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('font-size', fs)
        .attr('fill', '#1f2937')
        .attr('pointer-events', 'none')  // 文字不拦截鼠标
      WRAP_TEXT(t, iv.name, w - 8, fs)
```

**文字自动换行算法**：

```
算法 WRAP_TEXT(parent, text, maxWidth, fontSize):
  charWidth ← fontSize × 0.85        // 中文字符宽度经验值
  maxChars ← floor(maxWidth / charWidth)
  
  if maxChars <= 0 OR text.length == 0:
    return
  
  if text.length <= maxChars:
    parent.text(text)                 // 单行，直接设置
    return
  
  // 多行分割
  lines ← []
  remaining ← text
  while remaining.length > maxChars:
    lines.append(remaining[0..maxChars])
    remaining ← remaining[maxChars..]
  if remaining.length > 0:
    lines.append(remaining)
  
  // TSpan 渲染 + 垂直居中
  lineH ← fontSize × 1.25
  totalH ← lines.length × lineH
  
  for (line, li) in enumerate(lines):
    tspan ← parent.append('tspan')
      .attr('x', parent.attr('x'))
      .text(line)
    if li == 0:
      // 第一行向上偏移，使多行整体垂直居中
      dy ← -(totalH / 2) + lineH × 0.35
      tspan.attr('dy', '{dy}px')
    else:
      tspan.attr('dy', '{lineH}px')
```

### 5.5 交互层实现

交互层为沉积相列赋予"可编辑"能力。它的核心机制是**深度反算 + 段命中**——将鼠标位置转换为深度坐标，然后在线性数组中查找包含该深度的段。对于沉积相的 ≤20 段数据，O(N) 线性扫描足够高效，不需要空间索引结构。交互层通过 `structuredClone` 实现不可变更新，确保 React 的状态管理能正确触发重渲染。

## 6. 配置驱动架构

配置驱动架构是将前面所有算法和模块组合为可复用引擎的关键。它的核心思想是：**引擎代码写一次，配置数据写 N 次**。每一口新井的可视化，只需要编写一份 JSON 格式的配置文件——定义有哪些列、每列多宽、映射什么数据、用什么图案——无需修改任何引擎代码。这种架构将"变化的"（每口井不同的列组合、岩性类型、沉积相体系）与"不变的"（渲染算法、交互机制、导出流程）彻底分离。

### 6.1 配置即规格

新井可视化的核心工作是编写配置，而非修改引擎。配置文件本身就是一份**可视化规格说明**——它精确地定义了最终图表的每个维度（列数、宽度、数据来源、图案映射）。这意味着非程序员（如地质工程师）在理解配置结构后，也可以参与新井的可视化配置工作。

```typescript
interface ChartConfig {
  // 列定义：每列的类型、宽度、数据源
  columns: ColumnDef[];
  
  // 表头：标题模板、标签、合并规则
  header: HeaderConfig;
  
  // 岩性映射：关键词 → 图案/颜色
  lithologyMapping: PatternMapping;
  
  // 沉积相映射：关键词 → 图案/颜色
  faciesMapping: PatternMapping;
  
  // 布局参数
  pixelRatio: number;      // 像素/米 (通常 14)
  gridInterval: number;    // 格网线间距 (通常 1)
  eventNamespace: string;  // D3 事件命名空间
}
```

### 6.2 列类型系统

7 种列类型是引擎覆盖能力的边界。每种列类型封装了特定的数据几何和渲染策略。添加新的列类型（如"孔隙度-渗透率交会图"）只需要在渲染管线中增加一个新的 `case` 分支，不影响已有类型的实现。

| 类型 | 数据绑定 | 视觉表现 | 适用场景 |
|------|---------|---------|---------|
| `intervals` | `dataKey` | 矩形+旋转文字 | 地层、组、层序 |
| `curves` | `curveFilter` | 折线路径 | AC/GR, RT/RXO, SH/PERM/PHIE |
| `depth` | yScale | 刻度线+数字 | 深度标尺 |
| `lithology` | `dataKey` | 底纹填充矩形 | 岩性柱 |
| `description` | `dataKey` | 文字+点击编辑 | 岩性描述 |
| `facies` | `faciesLevel` | 底纹填充+编辑 | 微相/亚相/相 |
| `systems_tract` | fixed | 三角形/矩形 | TST/HST |

**各列类型的渲染管线差异**：

每种列类型虽然共享 `yScale` 和 `clipPath` 基础设施，但在数据变换、视觉编码和交互支持上各有特点：

- **`intervals`**：最简单的列类型。数据绑定通过 `dataKey` 从 `intervals` 对象中取对应的数组（如 `series`、`system`、`formation`）。渲染只涉及矩形边界线和文字标注。当 `rotate: true` 时，文字旋转 90° 并使用纵向空间计算换行——这是地层列的典型需求，因为地层名（如"寒武系"）在窄列中横排放不下。

- **`curves`**：唯一使用独立 `xScale` 的列类型。每条曲线有自己的 `display_range`（物理量程），映射到列的像素范围。多条曲线同道叠加时，颜色和线型（实线/虚线/点线）是区分它们的唯一手段。曲线通过 `curveFilter` 按名称筛选，支持正则匹配——例如 `{ curveFilter: ['AC', 'GR'] }` 会匹配所有包含这两个名称的曲线。

- **`depth`**：不绑定任何数据，直接从 `yScale` 的 domain 中生成刻度。每 5m 一个主刻度，刻度线从列的左右两端向内各延伸 6px，数字居中显示。这是唯一不需要 `clipPath` 的列类型。

- **`lithology`** 与 **`facies`**：两者的渲染逻辑几乎相同（底纹矩形 + 文字），区别在于：`lithology` 使用 `lithologyMapping`，`facies` 使用 `faciesMapping`；`facies` 支持点击编辑（因为沉积相是解释结论，可能需要修正），`lithology` 不支持（岩性是录井事实数据）。

- **`description`**：唯一使用左对齐文字的列类型（其他都是居中）。文字从列左侧 5px 处开始，支持点击编辑。渲染时跳过高度不足 8px 的段（避免文字溢出）。

- **`systems_tract`**：最特殊的列类型。不使用矩形，而是根据段名称绘制不同形状：名称包含 "TST"（海侵体系域）时绘制向上收窄的三角形（蓝色填充），包含 "HST"（高位体系域）时绘制向下收窄的三角形（黄色填充），其他情况绘制普通矩形。三角形的形状语义直接编码了体系域的沉积特征——TST 代表海侵深化（向上变细），HST 代表加积充填（向上变粗）。

### 6.3 新井适配流程

将一口新井接入可视化引擎，遵循五个标准步骤。这个流程的设计原则是**最小侵入**——只需添加配置和数据，不修改引擎源码。只有在遇到新的岩性或沉积相类型时，才需要扩展图案注册表。

```
新井数据
  │
  ├─ Step 1: 整理为 WellLogData 格式 (JSON)
  │
  ├─ Step 2: 定义列配置 columns[]
  │    └─ 选择列类型、宽度、数据绑定
  │
  ├─ Step 3: 定义映射表
  │    ├─ lithologyMapping (岩性名 → 图案)
  │    └─ faciesMapping    (相名 → 图案)
  │
  ├─ Step 4: 注册新图案（如需）
  │    └─ registerFaciesPatterns() 中添加 SVG pattern
  │
  └─ Step 5: 使用通用组件
       └─ <WellLogChart data={data} config={config} />
```

## 7. 验证方法

验证方法确保引擎的每个渲染步骤都产生正确的结果。由于测井图是专业可视化而非通用图表，"正确"的标准不是美学评价，而是**信息完整性**（所有数据都被渲染）和**精确性**（坐标映射无误、图案匹配正确）。验证分为自动化检查（编译、测试、DOM 结构检查）和渲染指标基准（像素尺寸、图案数量等）两个层次。

### 7.1 自动化验证清单

自动化验证是每次代码变更后必须执行的检查项。从编译检查到 DOM 结构验证，覆盖了从类型安全到渲染完整性的全链路。其中"底部截断检查"和"重复线检查"是测井图特有的验证项——它们针对的是深度轴连续性这个核心约束。

| 检查项 | 方法 | 验证标准 |
|-------|------|---------|
| 编译 | `npx tsc --noEmit` | 零错误 |
| 单元测试 | `npm test` | 35 tests pass |
| SVG 结构 | Playwright DOM 检查 | pattern 数量=16, clipPath 数量=列数 |
| 底部截断 | `totalHeight ≥ bodyStart + gridHeight` | maxDepth 段完全可见 |
| 重复线 | 逐段检查边界线 | 相邻段不画重复 top 线 |
| 图案匹配 | 遍历所有 lithology/facies 名称 | 每个名称都有对应图案或颜色 |
| 导出 | SVG/PNG/PDF 导出 | 无交互层、无截断 |

### 7.2 渲染验证指标

渲染指标是量化验证的基准值。以老龙1井为基准数据集，这些数值在每次重构后都必须保持一致。任何偏离都意味着渲染逻辑发生了意外变化。

```
老龙1井基准数据 (2515-2610m, 14 px/m):
  SVG 尺寸:        1070 × 1452 px
  图案注册:        16 种 (6 岩性 + 10 沉积相)
  裁剪路径:        14 个 (每列一个)
  曲线采样:        761 → 600 点 (降频 21%)
  文字换行:        最长描述 8 字符/行 (在 150px 列宽中)
  格网线:          95 条 (每 1m, 高度 95m × 14px = 1330px)
```

## 8. 整体布局与自适应方法

整体布局决定了图表在屏幕和纸面上的呈现方式。与前面章节聚焦于"如何渲染每个元素"不同，本章关注的是"如何将这些元素组织为一个整体的视觉结构，并在不同设备和使用场景下保持可用性"。这是从局部到整体的视角切换——前面解决的是"画什么"，这里解决的是"放在哪里、多大、如何适配"。

测井图的布局面临一个独特的矛盾：**工业标准要求固定比例尺，但现代用户期待响应式体验**。我们的策略是"渐进式自适应"——默认保持固定比例尺以确保专业精度，然后根据使用场景逐步引入缩放、重排和虚拟滚动等自适应能力。

### 8.1 布局模型

测井图的布局本质上是一个 **固定比例的 SVG 画布嵌入可滚动的 HTML 容器**。这个选择由测井图的物理特性决定：深度轴的像素/米比（`pixelRatio`）是经过标定的工程参数，不是可以随意拉伸的视觉装饰。

```
┌───────────────────────────────────────────────────────────────┐
│ 浏览器视口 (viewport)                                          │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │ HTML 容器 (flex column, overflow-auto)                    │ │
│  │  ┌──────────────────────────────────────────────────────┐│ │
│  │  │ 工具栏 (sticky bottom)                                ││ │
│  │  ├──────────────────────────────────────────────────────┤│ │
│  │  │ 可滚动区域                                            ││ │
│  │  │  ┌────────────────────────────────────────────────┐  ││ │
│  │  │  │ SVG 画布 (固定像素尺寸)                          │  ││ │
│  │  │  │  width  = Σ(colWidths) = 1070px                 │  ││ │
│  │  │  │  height = bodyStart + gridHeight + 2            │  ││ │
│  │  │  │  viewBox = "0 0 1070 1452"                      │  ││ │
│  │  │  └────────────────────────────────────────────────┘  ││ │
│  │  └──────────────────────────────────────────────────────┘│ │
│  └──────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

**为什么选择固定尺寸而非响应式缩放**：

1. **深度轴的物理精度**：`pixelRatio = 14 px/m` 是经过标定的值，保证文字在 40px 宽列中可读、曲线细节可辨。缩放会破坏这个精度。
2. **底纹图案的一致性**：SVG `<pattern>` 的 `patternUnits="userSpaceOnUse"` 意味着图案密度与画布坐标绑定。缩放画布会导致图案过密或过疏。
3. **测井图的工业标准**：纸质测井图有固定比例尺（如 1:200），数字版本保持等比例是行业惯例。

### 8.2 当前布局策略

当前采用最简单的布局策略：固定尺寸 + 居中 + 滚动。这个策略的优势是零实现成本且渲染结果完全确定——在任何设备上看到的都是同一个像素级的图表。劣势是在小屏幕设备上需要大量滚动，在大屏幕上两侧留白过多。

```
算法 CURRENT_LAYOUT(svg, container):

  // SVG 尺寸由数据决定，不随视口变化
  svgWidth  ← Σ(config.columns.map(c => c.width))    // 1070px
  svgHeight ← bodyStart + gridHeight + 2              // ~1452px

  // 容器策略：居中 + 滚动
  container.style ← "flex justify-center py-4 px-4"
  
  // 当 svgWidth > viewportWidth:
  //   → 水平滚动条自动出现（overflow-auto）
  // 当 svgHeight > viewportHeight:
  //   → 垂直滚动条自动出现
  
  return { 无缩放, 居中对齐, 双向滚动 }
```

**当前行为实测**：

| 视口宽度 | SVG 渲染宽度 | 行为 |
|----------|-------------|------|
| 375px (手机) | 1070px | 水平滚动，完整显示 |
| 1024px (平板) | 1070px | 水平滚动，完整显示 |
| 1400px (桌面) | 1070px | 居中，两侧留白 |
| 1920px (大屏) | 1070px | 居中，两侧大面积留白 |

### 8.3 自适应优化策略

针对不同使用场景，提出三种自适应策略。三种策略不是互斥的，而是可以组合使用的——例如策略 A（缩放）和策略 C（深度虚拟滚动）可以同时应用于移动端的超深井查看。策略选择的依据是使用场景（桌面分析 vs 移动查看 vs 大屏展示）和井段长度。

#### 8.3.1 策略 A：视口适配缩放（推荐）

当视口宽度小于 SVG 宽度时，等比缩小 SVG 使其完全可见；视口足够宽时保持原始尺寸。这是推荐的首选策略，因为它在 SVG 内部坐标系完全不变的前提下，仅通过 CSS transform 实现视觉缩放——图案密度、曲线精度、文字尺寸都保持原始标定值。

```
算法 ADAPTIVE_FIT(svg, viewportWidth):
  svgNaturalWidth ← Σ(config.columns.map(c => c.width))
  padding ← 32  // px, 两侧 padding
  
  availableWidth ← viewportWidth - padding * 2
  
  if availableWidth >= svgNaturalWidth:
    // 视口足够宽：原始尺寸，居中
    scale ← 1.0
  else:
    // 视口不足：等比缩放
    scale ← availableWidth / svgNaturalWidth
  
  // 使用 CSS transform 缩放（保留 SVG 内部坐标系不变）
  svg.style.transform ← "scale(scale)"
  svg.style.transformOrigin ← "top left"
  container.style.width ← svgNaturalWidth × scale + "px"
  container.style.height ← svgNaturalHeight × scale + "px"
  
  // 交互坐标修正
  mouseToSVG(mouseX, mouseY):
    screenPoint ← { x: mouseX, y: mouseY }
    ctm ← svg.getScreenCTM()
    svgPoint ← screenPoint.matrixTransform(ctm.inverse())
    // CTM 自动包含 transform 缩放，坐标无需额外修正
  
  return { scale, 无滚动 }
```

**优势**：图案密度不变、曲线精度不变、交互坐标自动正确（`getScreenCTM()` 包含 transform）。

**实现方式**：

```typescript
// WellLogChart.tsx 或 Dashboard 中
function useAdaptiveScale(svgRef: RefObject<SVGSVGElement>) {
  const [scale, setScale] = useState(1);
  
  useEffect(() => {
    const observer = new ResizeObserver(entries => {
      const vw = entries[0].contentRect.width;
      const naturalW = 1070; // 从 config 计算
      const avail = vw - 64;
      setScale(avail >= naturalW ? 1 : avail / naturalW);
    });
    observer.observe(svgRef.current!.parentElement!);
    return () => observer.disconnect();
  }, []);
  
  return scale;
}
```

#### 8.3.2 策略 B：列宽自适应

根据视口宽度动态调整各列宽度，重新分配像素空间。与策略 A 的区别在于：策略 A 是整体等比缩放，策略 B 是按列重新分配宽度。策略 B 的优势是能充分利用大屏幕的横向空间，劣势是需要重新渲染整个图表（因为列宽变化会影响所有坐标计算）。

```
算法 ADAPTIVE_COLUMNS(config, viewportWidth):
  minWidths ← config.columns.map(c => c.minWidth ?? 30)
  totalMin ← sum(minWidths)
  
  if viewportWidth < totalMin:
    // 最小宽度也无法满足，退回策略 A
    return ADAPTIVE_FIT(...)
  
  // 按比例分配额外空间
  extraSpace ← viewportWidth - totalMin
  baseWeights ← config.columns.map(c => c.width / sum(config.columns.map(c => c.width)))
  
  newWidths ← columns.map((c, i) => 
    minWidths[i] + floor(extraSpace × baseWeights[i])
  )
  
  // 重新计算布局
  return LAYOUT(data, { ...config, columns: applyWidths(config.columns, newWidths) })
```

**权衡**：列宽变化会影响文字换行和曲线精度，需要设置 `minWidth` 下限。适合大屏展示。

#### 8.3.3 策略 C：深度范围自适应（纵向）

对于超深井（如 >500m），通过视口高度控制可见深度范围，实现纵向虚拟滚动。这是三种策略中实现复杂度最高的——它要求渲染管线从"一次性全量渲染"改为"按需增量渲染"，只绘制当前可视窗口内的元素。适合超深井和低性能设备场景。

```
算法 DEPTH_VIEWPORT(data, viewportHeight):
  pixelRatio ← config.pixelRatio  // 14 px/m
  visibleHeight ← viewportHeight - bodyStart - padding
  visibleDepthRange ← visibleHeight / pixelRatio
  
  // 计算当前可见深度窗口
  viewWindow ← {
    top: currentScrollDepth,
    bottom: currentScrollDepth + visibleDepthRange
  }
  
  // 渲染优化：只绘制可见范围内的元素
  yScale ← linear_scale(
    domain = [viewWindow.top, viewWindow.bottom],
    range  = [0, visibleHeight]
  )
  
  // 曲线数据采样优化
  visiblePoints ← curve.data.filter((d, i) => 
    curve.depth[i] >= viewWindow.top - margin &&
    curve.depth[i] <= viewWindow.bottom + margin
  )
  
  return { yScale, visiblePoints, viewWindow }
```

### 8.4 pixelRatio 自适应

`pixelRatio`（像素/米比）是控制图表纵向密度的核心参数。它决定了每米井段在屏幕上占多少像素——值越大图表越长、细节越清晰，但需要更多滚动。不同深度范围应使用不同比例：短井段（如取心段 50m）用高比例展示细节，长井段（如全井段 500m）用低比例总览趋势。自适应算法根据深度范围自动选择合适的比例尺。

```
算法 ADAPTIVE_PIXEL_RATIO(depthRange):
  // 经验规则：保持图表总高度在 800-2000 px 之间
  targetHeight ← 1200  // px, 目标高度
  
  idealRatio ← targetHeight / depthRange
  
  // 约束到合理范围
  minRatio ← 4   // px/m, 低于此值文字不可读
  maxRatio ← 20  // px/m, 高于此值浪费空间
  
  ratio ← clamp(idealRatio, minRatio, maxRatio)
  
  // 量化到 0.5 的整数倍（保持刻度整齐）
  ratio ← round(ratio × 2) / 2
  
  return ratio
```

| 井段长度 | 自适应 pixelRatio | 图表高度 | 适用场景 |
|----------|------------------|---------|---------|
| 50m | 20 px/m | 1000 px | 详细分析 |
| 95m | 14 px/m (老龙1) | 1330 px | 常规解释 |
| 200m | 6 px/m | 1200 px | 区域概览 |
| 500m | 4 px/m | 2000 px | 全井段浏览 |

### 8.5 导出布局

导出时脱离浏览器视口约束，使用独立的布局参数。导出布局与屏幕布局的核心区别在于：屏幕布局追求"可交互浏览"，导出布局追求"信息完整性"——所有数据必须出现在导出文件中，不能因为视口裁剪而遗漏。不同格式有各自的约束：SVG 保持矢量精度无尺寸限制，PNG 需要 3 倍渲染保证 300 DPI 打印质量，PDF 需要适配 A4 纸张的物理尺寸。

```
算法 EXPORT_LAYOUT(svg, format):
  match format:
    "SVG":
      // 直接序列化 SVG DOM，保持原始比例
      return serializeSVG(svg)
    
    "PNG":
      scale ← 3  // 3 倍渲染，确保 300 DPI 质量
      canvas ← svgToCanvas(svg, scale)
      // canvas 实际尺寸: 3210 × 4356 px
      return canvas.toBlob("image/png")
    
    "PDF":
      // A4 纵向: 210 × 297mm, 有效区域约 190 × 277mm
      a4WidthMM ← 190
      a4HeightMM ← 277
      
      // 计算适配比例
      svgAspect ← svgWidth / svgHeight
      a4Aspect ← a4WidthMM / a4HeightMM
      
      if svgAspect > a4Aspect:
        // 以宽度为准
        printWidth ← a4WidthMM
        printHeight ← a4WidthMM / svgAspect
      else:
        // 以高度为准
        printHeight ← a4HeightMM
        printWidth ← a4HeightMM × svgAspect
      
      // 居中放置
      offsetX ← (210 - printWidth) / 2
      offsetY ← (297 - printHeight) / 2
      
      return { printWidth, printHeight, offsetX, offsetY }
```

### 8.6 推荐实施路径

自适应策略的引入应该渐进式推进，每个阶段独立可用、独立验证。推荐的实施路径从最简单（零成本）到最复杂（需要改造渲染管线），每个阶段都建立在前一个阶段的验证基础上。

```
阶段 1 (当前): 固定尺寸 + 滚动
  └─ 适用于: 桌面端专业分析
  └─ 成本: 零（已实现）

阶段 2: 视口适配缩放 (策略 A)
  └─ 适用于: 移动端查看、演示汇报
  └─ 实现: ResizeObserver + CSS transform
  └─ 影响: 仅 Dashboard 层，引擎层不变

阶段 3: 列宽自适应 (策略 B)
  └─ 适用于: 大屏展示、全屏模式
  └─ 实现: config.columns[i].width 动态化
  └─ 影响: 需要重新渲染（useEffect 依赖变化）

阶段 4: 深度虚拟滚动 (策略 C)
  └─ 适用于: 超深井（>500m）、低性能设备
  └─ 实现: 可视窗口裁剪 + 增量渲染
  └─ 影响: 需要改造渲染管线
```

### 8.7 布局自适应的约束条件

任何自适应策略必须遵守以下硬约束。这些约束是从测井图的工业标准、人因工程和 SVG 技术限制中提炼出来的——违反任何一条都会导致图表失去专业可用性。约束条件同时提供了检查方法，用于在每次布局变更后验证合规性。

| 约束 | 原因 | 检查方法 |
|------|------|---------|
| `pixelRatio ≥ 4 px/m` | 文字最小 6pt 需要足够像素 | `gridHeight / depthRange ≥ 4` |
| `minColumnWidth ≥ 30px` | 底纹图案最小可辨识尺寸 | `colWidths.every(w => w >= 30)` |
| `totalHeight = bodyStart + gridHeight + 2` | 底部不截断 | 渲染后检查最后一段 |
| 图案 `patternUnits` 不随缩放变化 | 密度一致性 | `getComputedStyle(pattern)` |
| 交互坐标通过 `getScreenCTM()` 获取 | 自动包含所有变换 | 鼠标悬停值验证 |

---

## 附录 A: 老龙1井完整实例走查

本附录通过一个完整的实例——老龙1井 2515-2610m 井段——将前文所有章节的内容串联起来。读者可以沿着数据流的路径，从原始 Excel 到最终渲染，验证每个方法论步骤的具体实现。

### A.1 数据概况

```
井名: 老龙1
深度范围: 2515m - 2610m (共 95m)
数据来源: 11 个 Excel sheet (laolong1_well_data.xls)

数据维度:
  曲线: 6 条 (AC, GR, RT, RXO, SH, PERM/PHIE), 761 个采样点/条
  地层: series(3段), system(3段), formation(4段)
  岩性: 17 段
  沉积相: phase(4段), sub_phase(6段), micro_phase(8段)
  体系域: systems_tract(4段)
  层序: sequence(3段)
```

### A.2 配置定义（configs/laolong1.ts）

老龙1井的配置定义了 14 列布局，从左到右依次为：

```
列 0: 地层系统-系     (40px, intervals, dataKey='series', rotate=true)
列 1: 地层系统-统     (40px, intervals, dataKey='system', rotate=true)
列 2: 组/段           (60px, intervals, dataKey='formation', rotate=true)
列 3: 深度标尺        (40px, depth)
列 4: AC/GR 曲线      (100px, curves, curveFilter=['AC','GR'])
列 5: RT/RXO 曲线     (100px, curves, curveFilter=['RT','RXO'])
列 6: SH 曲线         (80px, curves, curveFilter=['SH'])
列 7: PERM/PHIE 曲线  (80px, curves, curveFilter=['PERM','PHIE'])
列 8: 岩性柱          (50px, lithology, dataKey='lithology')
列 9: 岩性描述        (150px, description)
列 10: 微相           (70px, facies, faciesLevel='micro_phase')
列 11: 亚相           (70px, facies, faciesLevel='sub_phase')
列 12: 相             (70px, facies, faciesLevel='phase')
列 13: 体系域         (60px, systems_tract)
```

**列宽计算**: `40+40+60+40+100+100+80+80+50+150+70+70+70+60 = 1070px`

**列宽设计原则**：
- 间隔列（地层）最窄（40-60px），因为只有旋转文字
- 曲线列较宽（80-100px），保证曲线细节可辨
- 描述列最宽（150px），因为中文岩性描述较长
- 沉积相列中等（70px），既要显示图案又要显示文字

### A.3 布局计算过程

```
Step 1: 确定最大深度
  allItems = series(3) + system(3) + formation(4) + lithology(17) + ...
  maxDepth = max(allItems.bottom) = 2610.0m
  depth_start = 2515.0m
  depthRange = 2610 - 2515 = 95m

Step 2: 计算画布尺寸
  gridHeight = 95m × 14px/m = 1330px
  bodyStart = 40 + 50 + 30 = 120px
  totalHeight = 120 + 1330 + 2 = 1452px
  totalWidth = 1070px

Step 3: 创建 D3 线性尺度
  yScale = d3.scaleLinear()
    .domain([2515, 2610])
    .range([0, 1330])

  验证: yScale(2515) = 0, yScale(2610) = 1330 ✓
  中间值: yScale(2550) = (2550-2515)×14 = 490px

Step 4: 创建列坐标数组
  colX = [0, 40, 80, 140, 180, 280, 380, 460, 540, 590, 740, 810, 880, 950]
  colWidths = [40, 40, 60, 40, 100, 100, 80, 80, 50, 150, 70, 70, 70, 60]

Step 5: 创建曲线分组
  curveGroups[4] = [AC, GR]      // 列4的曲线
  curveGroups[5] = [RT, RXO]     // 列5的曲线
  curveGroups[6] = [SH]           // 列6的曲线
  curveGroups[7] = [PERM, PHIE]  // 列7的曲线
```

### A.4 关键渲染步骤

**岩性柱渲染（列 8）**：

```
以"深灰色砂质白云岩"段 (2515.0-2525.5m) 为例:

  y1 = yScale(2515.0) = 0px
  y2 = yScale(2525.5) = 147px
  h = 147px

  ENCODE("深灰色砂质白云岩", lithologyMapping):
    patterns: { "白云岩": "dolomite", "砂岩": "sandstone", ... }
    "白云岩" ∈ "深灰色砂质白云岩"? ✅
    → fill = "url(#pat-dolomite)"

  渲染: <rect x=541 y=0 width=48 height=147 fill="url(#pat-dolomite)">
```

**体系域渲染（列 13）**：

```
以 TST 段为例:

  输入: { name: "TST(海侵体系域)", top: 2543.5, bottom: 2575.0 }
  y1 = yScale(2543.5) = 399px
  y2 = yScale(2575.0) = 840px
  h = 441px
  cmx = 950 + 60/2 = 980px

  name.includes("TST") → true
  → 绘制三角形 (向上收窄):
    points = "980,401 952,838 1008,838"
    fill = "#bfdbfe" (蓝色)
```

**曲线渲染（列 4, AC 曲线）**：

```
  xScale = d3.scaleLinear()
    .domain([AC.display_min, AC.display_max])  // 如 [40, 240] μs/ft
    .range([182, 278])                          // 列4的像素范围

  原始数据: 761 个点 (2515.0 到 2610.0, 每 0.125m)
  降频: step = max(1, floor(761/600)) = 1 (无需降频, 761 ≤ 600×1.27)
  实际采样: 保留所有 761 点

  lineGen.x(d => xScale(d.val)).y(d => yScale(d.depth))
  → <path d="M182,0 L183,1.75 L185,3.5 ..." stroke="#2563eb">
```

### A.5 交互层行为

**鼠标悬停在深度 2550.0m 处**：

```
坐标转换:
  mouseY (body局部坐标) = yScale(2550.0) = 490px
  mouseX = 列4 范围内 (180-280)

曲线插值:
  AC: 在 depth=2550.0 处插值 → 85.32 μs/ft
  GR: 在 depth=2550.0 处插值 → 23.45 API

段命中:
  lithology: find(iv => 2550.0 >= iv.top && 2550.0 <= iv.bottom)
    → { name: "灰色白云质细砂岩", top: 2540.0, bottom: 2558.0 }
  micro_phase: → { name: "云质砂坪", top: 2543.5, bottom: 2558.0 }
  sub_phase: → { name: "混积潮坪", top: 2543.5, bottom: 2575.0 }
  phase: → { name: "潮坪相", top: 2543.5, bottom: 2575.0 }

Tooltip 显示:
  深度: 2550.00m
  AC: 85.320 μs/ft
  GR: 23.450 API
  岩性: 灰色白云质细砂岩
  微相: 云质砂坪
  亚相: 混积潮坪
  相: 潮坪相
```

### A.6 导出

**SVG 导出**: 克隆 SVG DOM → 移除 `.interaction-layer` → 序列化为 XML → 下载为 `老龙1_2515-2610m.svg`

**PNG 导出**: SVG → Canvas (3× scale) → 3210×4356px → 下载为 `老龙1_2515-2610m.png`

**PDF 导出**: A4 纵向，SVG 宽高比 = 1070/1452 = 0.737，A4 有效区域宽高比 = 190/277 = 0.686。因 SVG 更宽，以 A4 高度为准：printHeight = 277mm, printWidth = 277 × 0.737 = 204mm（超出 A4 有效宽度），改为以宽度为准：printWidth = 190mm, printHeight = 190/0.737 = 258mm，居中放置。

---

## 附录 B: 图案参考速查表

本附录为图案设计提供快速参考，涵盖当前引擎注册的全部 16 种底纹图案及其适用条件。

### B.1 岩性图案（6 种）

| 图案 ID | 关键词 | Tile | 基元类型 | 底色 | 标准依据 |
|---------|-------|------|---------|------|---------|
| `sandstone` | 砂岩 | 20×20 | 10 圆 (r=0.8-1.2) | #fef3c7 | 附录M: 碎屑岩-砂岩 |
| `siltstone` | 粉砂岩 | 12×12 | 10 圆 (r=0.3-0.5) | #fde68a | 附录M: 碎屑岩-粉砂岩 |
| `mudstone` | 泥岩 | 16×8 | 3 短线 | #e7e5e4 | 附录M: 碎屑岩-泥岩 |
| `shale` | 页岩 | 16×6 | 2 长线 | #d6d3d1 | 附录M: 碎屑岩-页岩 |
| `limestone` | 石灰岩/灰岩 | 24×16 | 6 线 (砖块网格) | #dbeafe | 附录M: 碳酸盐岩-石灰岩 |
| `dolomite` | 白云岩 | 16×16 | 2 水平线 + 4 斜线 | #e0e7ff | 附录M: 碳酸盐岩-白云岩 |

### B.2 沉积相图案（10 种）

| 图案 ID | 关键词 | Tile | 基元类型 | 底色 | 环境语义 |
|---------|-------|------|---------|------|---------|
| `tidal_flat` | 潮坪 | 20×10 | 2 贝塞尔路径 | #ecfdf5 | 潮汐波状层理 |
| `shelf` | 陆棚 | 16×8 | 2 水平线 | #eff6ff | 浅海稳定沉积 |
| `sand_flat` | 砂坪 | 14×14 | 5 圆 | #fef9c3 | 潮间高能砂质 |
| `mud_flat` | 泥坪 | 16×8 | 2 短线 | #f5f5f4 | 潮间低能泥质 |
| `mixed` | 混积 | 16×12 | 2 圆 + 2 线 | #f0fdf4 | 混合碳酸盐-碎屑沉积 |
| `clastic_shelf` | 碎屑岩 | 14×10 | 3 交错线 | #fef2f2 | 陆源碎屑输入 |
| `dolomitic_flat` | 云质 | 16×12 | 2 圆 + 2 斜线 | #faf5ff | 白云石化改造 |
| `muddy_shelf` | 泥质 | 12×8 | 3 密集短线 | #f5f5f4 | 悬浮质低能沉积 |
| `sandy_shelf` | 砂质 | 14×14 | 4 圆 | #fff7ed | 陆棚砂体 |
| `sand_mud_shelf` | 砂泥质 | 16×10 | 2 圆 + 2 线 | #fffbeb | 砂泥互层韵律 |

### B.3 扩展指南

添加新图案的步骤：

1. 在 `engine/patterns.ts` 的 `registerLithoPatterns()` 或 `registerFaciesPatterns()` 中添加 SVG `<pattern>` 定义
2. 在井配置的 `lithologyMapping.patterns` 或 `faciesMapping.patterns` 中添加关键词映射
3. 在 `colors` 中添加对应的底色映射
4. 验证：确认新图案在 30-80px 宽的矩形中可辨识，且与已有 15 种图案可区分

**图案设计检查清单**：
- [ ] Tile 尺寸 ≤ 24×24px（保证在窄列中至少重复 2 次）
- [ ] 基元数量 ≤ 12 个（控制 DOM 节点数）
- [ ] 线宽 ≥ 0.5px（低于此值在屏幕上不可见）
- [ ] 圆半径 ≥ 0.3px（同上）
- [ ] 底色与相邻图案有明显区分
- [ ] 缩小到 40px 宽列中仍可辨认
