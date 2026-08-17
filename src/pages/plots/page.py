import numpy as np
import math
from PySide6.QtCore import Qt, QRectF, QMarginsF
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QGroupBox, QComboBox, QSlider,
    QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QDoubleSpinBox, QTabWidget
)

from PySide6.QtGui import QIcon, QPainter, QPageSize, QPageLayout, QFont, QColor, QPen
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtPrintSupport import QPrinter

from geoviz_plots import SurfaceWidget, InterpolationWorker
from geoviz_plots.chart.cross_plot_widget import CrossPlotWidget
from geoviz_plots.interpolation.idw import interpolate_idw
from geoviz_plots.interpolation.scipy_grid import interpolate_scipy

from geoviz.jobs import CancellationToken, JobCancelled


class _CancellableInterpolationWorker(InterpolationWorker):
    """InterpolationWorker 的页面侧子类：通过 CancellationToken 协作式取消，替代 QThread.terminate()。

    IDW 引擎 interpolate_idw 在分块循环内检查 token；SciPy 引擎不接受 token，
    仅在调用前后检查，取消后页面会丢弃其结果。
    """

    def __init__(self, *args, cancellation_token=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cancellation_token = cancellation_token

    def run(self):
        token = self.cancellation_token
        try:
            if token is not None:
                token.raise_if_cancelled()
            if self.method == "idw":
                grid_z = interpolate_idw(
                    self.x, self.y, self.z,
                    self.grid_x, self.grid_y,
                    power=self.power,
                    cancellation_token=token,
                )
            else:
                grid_z = interpolate_scipy(
                    self.x, self.y, self.z,
                    self.grid_x, self.grid_y,
                    method=self.method,
                    mask_convex_hull=self.mask_convex_hull,
                )
            if token is not None:
                token.raise_if_cancelled()
            self.result_ready.emit(grid_z)
        except JobCancelled:
            pass  # 协作式取消：静默结束，不视为错误
        except Exception as e:
            self.error.emit(str(e))


class PlotsPage(QWidget):
    """Page exposing the premium 2D plotting, IDW/SciPy spatial interpolation, contour mapping, and Cross-Plot Analytics."""

    def _get_ui_icon(self, name: str) -> QIcon:
        """Resolve icon from project resources."""
        from src.utils.paths import get_resources_dir
        path = get_resources_dir() / "icons" / "ui" / name
        if path.exists():
            return QIcon(str(path))
        return QIcon()

    def __init__(self):
        super().__init__()
        
        # Default scattered points data
        self.points_x = []
        self.points_y = []
        self.points_z = []
        
        # Active interpolation worker
        self._worker = None
        # 超时未退出的旧 worker，保留引用待其自然结束（detach 保护，避免销毁运行中的线程）
        self._retired_workers: list = []

        self._build_ui()
        self._generate_demo_data()

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ------------------ Left Main Plot Canvas ------------------
        plot_container = QWidget()
        plot_container_layout = QVBoxLayout(plot_container)
        plot_container_layout.setContentsMargins(0, 0, 0, 0)
        plot_container_layout.setSpacing(0)

        self._tab_widget = QTabWidget()
        self.surface_plot = SurfaceWidget(self)
        self._cross_plot_widget = CrossPlotWidget(self)

        self._tab_widget.addTab(self.surface_plot, "🗺️ 属性等值线图")
        self._tab_widget.addTab(self._cross_plot_widget, "📈 交叉图分析 (Cross-Plot)")

        # Populate demo cross-plot data
        x = np.random.uniform(20, 150, 200)
        y = np.random.uniform(0.1, 0.45, 200)
        z = np.random.uniform(1000, 3000, 200)
        self._cross_plot_widget.set_scatter_data(x, y, z, x_label="GR (API)", y_label="NPHI (v/v)", z_label="Depth (m)")

        plot_container_layout.addWidget(self._tab_widget, 1)

        # Status row (TDD requires #faf9f5)
        self.status_bar = QLabel(" 就绪")
        self.status_bar.setFixedHeight(22)
        self.status_bar.setStyleSheet("""
            font-size: 11px;
            color: #586878;
            border-top: 1px solid #e5eaf1;
            background: #faf9f5;
        """)
        plot_container_layout.addWidget(self.status_bar)

        main_layout.addWidget(plot_container, 1)

        # ------------------ Right Control Panel (200px) ------------------
        self.control_panel = QWidget()
        self.control_panel.setFixedWidth(200)
        self.control_panel.setStyleSheet("""
            QWidget {
                background: #ffffff;
                border-left: 1px solid #e5eaf1;
            }
        """)
        panel_layout = QVBoxLayout(self.control_panel)
        panel_layout.setContentsMargins(12, 12, 12, 12)
        panel_layout.setSpacing(10)

        # Title
        title_label = QLabel(" 属性等值线图")
        title_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #1a2433; padding-bottom: 2px; border: none;")
        panel_layout.addWidget(title_label)

        self._setup_control_panel(panel_layout)
        main_layout.addWidget(self.control_panel)


    def export_cross_plot_pdf(self, output_path: str):
        """Export 300 DPI vector PDF or SVG for Cross-Plot report."""
        if output_path.endswith(".svg"):
            generator = QSvgGenerator()
            generator.setFileName(output_path)
            generator.setSize(generator.size())
            generator.setResolution(300)
            painter = QPainter(generator)
            self._render_cross_plot_report(painter, 297.0 * 3.7795, 210.0 * 3.7795)
            painter.end()
        else:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Landscape, QMarginsF(0, 0, 0, 0)))
            printer.setOutputFileName(output_path)

            painter = QPainter(printer)
            rect = printer.pageRect(QPrinter.Unit.Point)
            self._render_cross_plot_report(painter, rect.width(), rect.height())
            painter.end()

    def _render_cross_plot_report(self, painter: QPainter, width: float, height: float):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(QRectF(0, 0, width, height), QColor(255, 255, 255))
        painter.setPen(QColor(31, 102, 212))
        painter.setFont(QFont("SimSun", 16, QFont.Weight.Bold))
        painter.drawText(QRectF(20, 20, width - 40, 40), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "油田地质属性交叉图分析报告 (Cross-Plot Report)")

    def _setup_control_panel(self, panel_layout):
        # Group 1: Discrete points
        pts_group = QGroupBox(" 离散数据源")
        pts_group.setStyleSheet("QGroupBox { font-size: 11px; font-weight: bold; color: #1a2433; }")
        pts_layout = QVBoxLayout(pts_group)
        pts_layout.setSpacing(6)
        pts_layout.setContentsMargins(4, 12, 4, 4)

        gen_btn = QPushButton(" 随机生成测点")
        gen_btn.setIcon(self._get_ui_icon("plus.svg"))
        gen_btn.setStyleSheet("QPushButton { font-size: 10.5px; padding: 4px; border-radius: 6px; } QPushButton:hover { background: #f1f4f9; }")
        gen_btn.clicked.connect(self._generate_demo_data)
        pts_layout.addWidget(gen_btn)

        self.points_table = QTableWidget(0, 3)
        self.points_table.setHorizontalHeaderLabels(["井名", "坐标", "数值"])
        self.points_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.points_table.verticalHeader().setVisible(False)
        self.points_table.setFixedHeight(100)
        self.points_table.setStyleSheet("QTableWidget { font-size: 10px; border: 1px solid #e5eaf1; }")
        pts_layout.addWidget(self.points_table)
        panel_layout.addWidget(pts_group)

        # Group 2: Interpolation settings
        interp_group = QGroupBox(" 空间插值配置")
        interp_group.setStyleSheet("QGroupBox { font-size: 11px; font-weight: bold; color: #1a2433; }")
        interp_layout = QVBoxLayout(interp_group)
        interp_layout.setSpacing(8)
        interp_layout.setContentsMargins(4, 12, 4, 4)


        # Method
        method_label = QLabel("插值算法:")
        method_label.setStyleSheet("font-size: 10.5px; color: #586878; border: none;")
        self.method_combo = QComboBox()
        self.method_combo.addItems(["IDW (权重)", "SciPy Linear", "SciPy Cubic", "SciPy Nearest", "SciPy RBF (径向基)"])
        self.method_combo.currentIndexChanged.connect(self._on_settings_changed)
        self.method_combo.setStyleSheet("QComboBox { font-size: 11px; border: 1px solid #d3dbe6; border-radius: 6px; padding: 2px 8px; }")
        interp_layout.addWidget(method_label)
        interp_layout.addWidget(self.method_combo)

        # IDW Power
        self.power_row = QHBoxLayout()
        self.power_label = QLabel("权重系数:")
        self.power_label.setStyleSheet("font-size: 10.5px; color: #586878; border: none;")
        self.power_slider = QSlider(Qt.Orientation.Horizontal)
        self.power_slider.setMinimum(10)
        self.power_slider.setMaximum(40)
        self.power_slider.setValue(20)
        self.power_slider.setSingleStep(5)
        self.power_slider.setStyleSheet("""
            QSlider::groove:horizontal { height: 4px; background: #e2e8f0; border-radius: 2px; }
            QSlider::handle:horizontal { background: #1f66d4; width: 10px; height: 10px; margin: -3px 0; border-radius: 5px; }
        """)
        self.power_slider.valueChanged.connect(self._on_power_changed)
        self.power_row.addWidget(self.power_label)
        self.power_row.addWidget(self.power_slider)
        interp_layout.addLayout(self.power_row)

        # Mask Convex Hull
        self.mask_checkbox = QCheckBox(" 外插凸包截断裁剪")
        self.mask_checkbox.setChecked(True)
        self.mask_checkbox.stateChanged.connect(self._on_settings_changed)
        self.mask_checkbox.setStyleSheet("QCheckBox { font-size: 10.5px; color: #586878; }")
        interp_layout.addWidget(self.mask_checkbox)

        # Grid Resolution
        res_label = QLabel("网格分辨率:")
        res_label.setStyleSheet("font-size: 10.5px; color: #586878; border: none;")
        self.res_combo = QComboBox()
        self.res_combo.addItems(["50 x 50", "100 x 100", "200 x 200", "300 x 300"])
        self.res_combo.setCurrentIndex(1)  # Default 100x100
        self.res_combo.currentIndexChanged.connect(self._on_settings_changed)
        self.res_combo.setStyleSheet("QComboBox { font-size: 11px; border: 1px solid #d3dbe6; border-radius: 6px; padding: 2px 8px; }")
        interp_layout.addWidget(res_label)
        interp_layout.addWidget(self.res_combo)

        panel_layout.addWidget(interp_group)

        # Group 3: Contours and Colors
        contour_group = QGroupBox(" 渲染样式")
        contour_group.setStyleSheet("QGroupBox { font-size: 11px; font-weight: bold; color: #1a2433; }")
        contour_layout = QVBoxLayout(contour_group)
        contour_layout.setSpacing(8)
        contour_layout.setContentsMargins(4, 12, 4, 4)

        # Colormap
        cmap_label = QLabel("标准色标:")
        cmap_label.setStyleSheet("font-size: 10.5px; color: #586878; border: none;")
        self.cmap_combo = QComboBox()
        self.cmap_combo.addItem("cnpc_strat (岩相)", "cnpc_strat")
        self.cmap_combo.addItem("cnpc_fluid (流体)", "cnpc_fluid")
        self.cmap_combo.addItem("viridis (经典)", "viridis")
        self.cmap_combo.addItem("thermal (冷热)", "thermal")
        self.cmap_combo.currentIndexChanged.connect(self._on_colormap_changed)
        self.cmap_combo.setStyleSheet("QComboBox { font-size: 11px; border: 1px solid #d3dbe6; border-radius: 6px; padding: 2px 8px; }")
        contour_layout.addWidget(cmap_label)
        contour_layout.addWidget(self.cmap_combo)

        # Step
        step_row = QHBoxLayout()
        step_label = QLabel("线距:")
        step_label.setStyleSheet("font-size: 10.5px; color: #586878; border: none;")
        self.step_spin = QDoubleSpinBox()
        self.step_spin.setRange(0.1, 10.0)
        self.step_spin.setValue(1.0)
        self.step_spin.setSingleStep(0.5)
        self.step_spin.valueChanged.connect(self._on_settings_changed)
        self.step_spin.setStyleSheet("QDoubleSpinBox { font-size: 11px; border: 1px solid #d3dbe6; border-radius: 6px; padding: 2px 8px; }")
        step_row.addWidget(step_label)
        step_row.addWidget(self.step_spin)
        contour_layout.addLayout(step_row)

        # Stats
        self.stats_label = QLabel("数值范围: [—, —]")
        self.stats_label.setStyleSheet("font-size: 10.5px; color: #586878; font-style: italic; border: none;")
        contour_layout.addWidget(self.stats_label)

        panel_layout.addWidget(contour_group)

        # Group 4: Export Vector Graphics
        export_group = QGroupBox(" 成果导出")
        export_group.setStyleSheet("QGroupBox { font-size: 11px; font-weight: bold; color: #1a2433; }")
        export_layout = QHBoxLayout(export_group)
        export_layout.setSpacing(6)
        export_layout.setContentsMargins(4, 12, 4, 4)

        export_svg_btn = QPushButton(" SVG")
        export_svg_btn.setIcon(self._get_ui_icon("export.svg"))
        export_svg_btn.clicked.connect(self._export_svg)
        export_svg_btn.setStyleSheet("QPushButton { font-size: 10.5px; padding: 4px; border-radius: 6px; } QPushButton:hover { background: #f1f4f9; }")
        export_pdf_btn = QPushButton(" PDF")
        export_pdf_btn.setIcon(self._get_ui_icon("export.svg"))
        export_pdf_btn.clicked.connect(self._export_pdf)
        export_pdf_btn.setStyleSheet("QPushButton { font-size: 10.5px; padding: 4px; border-radius: 6px; } QPushButton:hover { background: #f1f4f9; }")
        export_layout.addWidget(export_svg_btn)
        export_layout.addWidget(export_pdf_btn)

        panel_layout.addWidget(export_group)
        panel_layout.addStretch()

    def _generate_demo_data(self):

        """Generate a random elegant set of discrete porosity/thickness well values."""
        # Clean up
        self.points_x.clear()
        self.points_y.clear()
        self.points_z.clear()

        # Seed data coordinates
        np.random.seed(42)
        well_count = 15
        
        # Coordinate limits simulating map area
        self.points_x = np.random.uniform(1000.0, 5000.0, well_count).tolist()
        self.points_y = np.random.uniform(1000.0, 5000.0, well_count).tolist()
        # Sand thickness simulating standard geology
        self.points_z = (np.random.uniform(2.0, 14.0, well_count) + np.sin(np.array(self.points_x) / 1000.0) * 2.0).tolist()

        # Fill table UI
        self.points_table.setRowCount(well_count)
        for i in range(well_count):
            self.points_table.setItem(i, 0, QTableWidgetItem(f"{self.points_x[i]:.0f}"))
            self.points_table.setItem(i, 1, QTableWidgetItem(f"{self.points_y[i]:.0f}"))
            self.points_table.setItem(i, 2, QTableWidgetItem(f"{self.points_z[i]:.2f}"))

        min_val, max_val = min(self.points_z), max(self.points_z)
        self.stats_label.setText(f"数据值范围: [{min_val:.2f}, {max_val:.2f}]")

        self._trigger_interpolation()

    def _on_power_changed(self, value):
        power_val = value / 10.0
        self.power_label.setText(f"IDW 权重系数 ({power_val:.1f}):")
        self._trigger_interpolation()

    def _on_settings_changed(self):
        self._trigger_interpolation()

    def _on_colormap_changed(self):
        cmap_name = self.cmap_combo.currentData()
        self.surface_plot.colormap_name = cmap_name
        self.surface_plot.update()

    def _trigger_interpolation(self):
        """Asynchronously compute the grid interpolation using QThread to preserve fluid UI performance."""
        if len(self.points_x) == 0:
            return

        # Disable controls slightly
        self.status_bar.setText("正在执行三维空间插值计算中...")
        
        # Extract settings
        method_idx = self.method_combo.currentIndex()
        methods = ["idw", "linear", "cubic", "nearest", "rbf"]
        method = methods[method_idx]

        # Power for IDW
        power = self.power_slider.value() / 10.0
        self.power_slider.setEnabled(method == "idw")

        # Mask Convex Hull
        mask = self.mask_checkbox.isChecked()

        # Grid Resolution
        res_text = self.res_combo.currentText()
        res = int(res_text.split("x")[0].strip())

        # Define grid bounds based on discrete points coordinates
        xmin, xmax = min(self.points_x), max(self.points_x)
        ymin, ymax = min(self.points_y), max(self.points_y)
        
        # Add 10% margin padding
        dx = xmax - xmin
        dy = ymax - ymin
        xmin -= dx * 0.1
        xmax += dx * 0.1
        ymin -= dy * 0.1
        ymax += dy * 0.1

        grid_x = np.linspace(xmin, xmax, res)
        grid_y = np.linspace(ymin, ymax, res)

        # 协作式取消当前任务（替代原 QThread.terminate 强杀）
        if self._worker is not None:
            self._cancel_worker(self._worker)

        # Instantiate async worker
        worker = _CancellableInterpolationWorker(
            self.points_x, self.points_y, self.points_z,
            grid_x, grid_y, method=method,
            mask_convex_hull=mask, power=power,
            cancellation_token=CancellationToken(),
        )
        self._worker = worker
        worker.result_ready.connect(lambda grid_z, w=worker, gx=grid_x, gy=grid_y: self._on_interpolation_complete(w, gx, gy, grid_z))
        worker.error.connect(self._on_interpolation_error)
        worker.finished.connect(lambda w=worker: self._retire_worker(w))
        worker.error.connect(lambda _m, w=worker: self._retire_worker(w))
        worker.start()

    def _cancel_worker(self, worker):
        """请求 worker 协作式取消；等待有限时间，超时则 detach 保留引用（不 terminate）。"""
        if worker is None:
            return
        try:
            token = getattr(worker, "cancellation_token", None)
            if token is not None:
                token.cancel()
            if worker.isRunning():
                if not worker.wait(1500):
                    # 超时未退出：detach，待其自然结束后再回收，避免销毁运行中的线程
                    self._retired_workers.append(worker)
            else:
                worker.deleteLater()
        except RuntimeError:
            pass

    def _retire_worker(self, worker):
        """Worker 结束后回收：从 detach 列表移除；非当前 worker 可直接 deleteLater。"""
        if worker in self._retired_workers:
            self._retired_workers.remove(worker)
        if worker is not self._worker:
            worker.deleteLater()

    def cleanup(self):
        """离开页面时停止插值 worker（协作式取消，不强制 terminate）。"""
        worker = self._worker
        self._worker = None
        if worker is not None:
            self._cancel_worker(worker)

    def _on_interpolation_complete(self, worker, grid_x, grid_y, grid_z):
        """Update the canvas plot bounds when background calculation thread finishes."""
        if self._worker is not worker:
            return  # 过期结果：任务已被新任务替换或页面已清理，丢弃
        token = getattr(worker, "cancellation_token", None)
        if token is not None and token.is_cancelled:
            return  # 已取消任务的迟到结果，丢弃
        step = self.step_spin.value()
        
        # Clean grid_z values (handle NaNs cleanly)
        valid_z = grid_z[~np.isnan(grid_z)]
        if len(valid_z) == 0:
            levels = [0.0, 1.0]
        else:
            zmin = float(np.min(valid_z))
            zmax = float(np.max(valid_z))
            # Build nice round levels matching step
            start = math.floor(zmin / step) * step
            end = math.ceil(zmax / step) * step
            levels = np.arange(start, end + step, step).tolist()

        cmap_name = self.cmap_combo.currentData()

        # Update Surface Widget
        self.surface_plot.set_grid_data(grid_x, grid_y, grid_z, levels, cmap_name)
        self.surface_plot.autofit()
        
        self.status_bar.setText(f"插值完成 ({self.method_combo.currentText()}) — 网格尺度: {len(grid_x)}x{len(grid_y)}，等值线数: {len(levels)}")

    def _on_interpolation_error(self, err_msg):
        self.status_bar.setText(f"插值计算失败: {err_msg}")
        QMessageBox.critical(self, "计算错误", f"插值过程中发生错误:\n{err_msg}")

    def _export_svg(self):
        """Direct high-fidelity vector SVG export."""
        path, _ = QFileDialog.getSaveFileName(self, "导出成果图为 SVG 矢量图", "contour_map.svg", "SVG (*.svg)")
        if path:
            generator = QSvgGenerator()
            generator.setFileName(path)
            generator.setSize(self.surface_plot.size())
            generator.setViewBox(self.surface_plot.rect())
            generator.setTitle("GeoViz Surface Contour Map")
            
            painter = QPainter(generator)
            painter.setRenderHint(QPainter.Antialiasing)
            self.surface_plot.render_surface(painter, self.surface_plot.width(), self.surface_plot.height())
            painter.end()
            QMessageBox.information(self, "导出成功", f"图件已成功导出为高分辨率 SVG 矢量图件。\n保存路径: {path}")

    def _export_pdf(self):
        """Export to premium, publication-grade PDF file."""
        path, _ = QFileDialog.getSaveFileName(self, "导出成果图为高保真 PDF 矢量文件", "contour_map.pdf", "PDF (*.pdf)")
        if path:
            from PySide6.QtPrintSupport import QPrinter
            from PySide6.QtGui import QPageLayout, QPageSize

            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(path)
            printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            printer.setPageOrientation(QPageLayout.Orientation.Landscape)
            
            page_layout = printer.pageLayout()
            paint_rect = page_layout.paintRectPixels(300)  # 300 DPI high fidelity
            
            painter = QPainter(printer)
            painter.setRenderHint(QPainter.Antialiasing)
            self.surface_plot.render_surface(painter, paint_rect.width(), paint_rect.height())
            painter.end()
            QMessageBox.information(self, "导出成功", f"图件已成功保存为高保真出版级 PDF。\n保存路径: {path}")
