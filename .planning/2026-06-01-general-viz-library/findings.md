# Findings & Design Docs: GeoViz Engine — 通用可视化与等值线插值渲染库

## 包架构与目录结构设计 (Package Architecture)

新建的独立子包将命名为 `geoviz_plots`，其内部物理结构如下：

```
packages/geoviz_plots/
├── pyproject.toml
├── geoviz_plots/
│   ├── __init__.py
│   ├── chart/                # 二维通用图表模块 (Line/Scatter)
│   │   ├── __init__.py
│   │   ├── plot_widget.py    # 通用 QPainter 二维图表画布
│   │   ├── axes.py           # 坐标轴标定与 Nice Ticks 计算
│   │   └── series.py         # 线/散点序列数据模型
│   ├── interpolation/        # 空间三维散点插值模块 (IDW/Kriging)
│   │   ├── __init__.py
│   │   ├── idw.py            # NumPy 向量化反距离权重算法
│   │   └── scipy_grid.py     # Scipy 克里金/样条/RBF 插值封装
│   └── surface/              # 等值线/色斑图面渲染模块
│       ├── __init__.py
│       ├── marching_squares.py # 矢量等值线/色斑路径提取
│       └── surface_widget.py # 高品质热力色斑+等值线渲染画布
└── tests/                    # 单元测试与基准测试
```

---

## 核心算法设计方案 (Core Algorithm Designs)

### 1. 坐标轴自适应刻度标定 (Axis Nice Ticks Algorithm)
为了使通用图表的坐标轴刻度显示自然、美观（如步长为 0.1, 0.2, 0.5, 1, 2, 5 等），采用 Heckbert 算法计算 "Nice Numbers"：

```python
def nice_number(value: float, round_flag: bool) -> float:
    exponent = math.floor(math.log10(value))
    fraction = value / (10 ** exponent)
    if round_flag:
        if fraction < 1.5: nice_fraction = 1.0
        elif fraction < 3.0: nice_fraction = 2.0
        elif fraction < 7.0: nice_fraction = 5.0
        else: nice_fraction = 10.0
    else:
        if fraction <= 1.0: nice_fraction = 1.0
        elif fraction <= 2.0: nice_fraction = 2.0
        elif fraction <= 5.0: nice_fraction = 5.0
        else: nice_fraction = 10.0
    return nice_fraction * (10 ** exponent)
```
利用该算法，对任意输入的数据极值范围 $[v_{min}, v_{max}]$ 均能自动计算出美观的刻度间隔 `tick_spacing` 以及精准的起止轴界。

### 2. NumPy 向量化反距离权重插值 (Vectorized IDW)
对于输入的散点数据集 $P = \{(x_i, y_i, z_i)\}_{i=1}^N$ 和目标规则渲染网格 $G \in \mathbb{R}^{H \times W}$，NumPy 广播加速的 IDW 实现公式为：

$$d_i(x, y) = \sqrt{(x - x_i)^2 + (y - y_i)^2}$$

$$w_i(x, y) = \frac{1}{d_i(x, y)^p}$$

$$\hat{z}(x, y) = \frac{\sum_{i=1}^N w_i(x, y) \cdot z_i}{\sum_{i=1}^N w_i(x, y)}$$

在 NumPy 中，通过开辟三维广播空间进行矩阵化距离和权重运算，可将数千个点插值到 $200 \times 200$ 网格的耗时压降至 10ms 以内，支持地图拖拽时的实时重算。

### 3. 等值线与色斑面矢量路径提取 (Contour Extraction)
- **纯 Python/NumPy 方案：** 编写轻量级 Marching Squares（行进双立方）提取算法，在每一个 $2 \times 2$ 的网格单元中，通过 4 个顶点的二进制状态（大于/小于等值面 $c$）的 16 种拓扑情况，计算出等值线段的精确交点。
- **高级拓扑包络方案（推荐）：** 封装底层非 GUI 的 `matplotlib._contour` 拓扑路径提取模块。它可以高效处理复杂的等值多边形嵌套关系（例如：盆地中的高地——岛屿，以及高地中的凹陷——湖泊），输出完美的闭合 `QPainterPath` 列表。
- **等值线标签 (Contour Labels) 绘制技巧：** 
  为了实现专业的出版级效果，等值线标签文字不能与线条重叠。
  * **实现方法**：在绘制等值线 `QPainterPath` 时，利用 `QFontMetrics` 测量标注数值的文本盒宽度 $W_{txt}$；使用路径的切线向量，在文本居中位置计算出一个“打断区间”，并将等值线路径分割为两段画出，中间留白处绘制带旋转角度的数值文本。

---

## 技术路线对比 (Technology Selection)

| 方案 | 渲染引擎 | 依赖性 | DPR 表现 | 导出支持 |
|---|---|---|---|---|
| **Matplotlib 嵌入** | 像素 Agg 静态图 | 极重 (`matplotlib`, `kiwisolver`) | 差，高分辨率缩放模糊卡顿 | 差，仅能保存为静态图片流 |
| **PyQtGraph 嵌入** | OpenGL/QGraphics | 较重 | 中，字体与线宽抗锯齿效果一般 | 较差，矢量格式不完美 |
| **自研 QPainter 矢量库** | **Qt QPainter 纯矢量** | **极轻 (`numpy`, `scipy`)** | **极佳，天然适应屏幕 DPR** | **极佳，完美支持 SVG/PDF 矢量导出** |

**最终决策：** 采用 **纯 QPainter 矢量库** 技术路线，与整个 GeoViz Engine 自研内核高度吻合，可以复用 `Viewport` 及 `PaintScheduler` 架构，实现极致的交互平滑度。
