import numpy as np
import os
import math
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QGroupBox, QComboBox, QSlider,
    QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QDoubleSpinBox
)
from PySide6.QtGui import QColor, QFont

from geoviz_plots import (
    SurfaceWidget, InterpolationWorker,
    extract_contour_lines, extract_filled_contours
)

class PlotsPage(QWidget):
    """Page exposing the premium 2D plotting, IDW/SciPy spatial interpolation, and contour mapping (SurfaceWidget)."""

    def __init__(self):
        super().__init__()
        
        # Default scattered points data
        self.points_x = []
        self.points_y = []
        self.points_z = []
        
        # Active interpolation worker
        self._worker = None

        self._build_ui()
        self._generate_demo_data()

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # ------------------ Left Control Panel ------------------
        control_panel = QWidget()
        control_panel.setFixedWidth(310)
        control_panel.setStyleSheet("""
            QWidget {
                background: #f7fafc;
                border-right: 1px solid #e2e8f0;
            }
            QLabel {
                font-size: 12px;
                color: #4a5568;
                font-weight: 500;
            }
            QGroupBox {
                font-size: 13px;
                font-weight: bold;
                color: #2d3748;
                margin-top: 10px;
                border: 1px solid #cbd5e0;
                border-radius: 6px;
                padding-top: 15px;
            }
            QPushButton {
                background-color: #3182ce;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2b6cb0;
            }
            QPushButton:disabled {
                background-color: #a0aec0;
            }
            QComboBox, QDoubleSpinBox {
                background: white;
                border: 1px solid #cbd5e0;
                border-radius: 4px;
                padding: 3px 6px;
                font-size: 12px;
                color: #2d3748;
            }
        """)
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setContentsMargins(0, 0, 10, 0)
        panel_layout.setSpacing(12)

        # Title
        title_label = QLabel("平面等值线色斑图")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2d3748; padding-bottom: 5px;")
        panel_layout.addWidget(title_label)

        # Group 1: Discrete points
        pts_group = QGroupBox("离散数据源 (Scattered Points)")
        pts_layout = QVBoxLayout(pts_group)
        pts_layout.setSpacing(8)

        gen_btn = QPushButton("随机生成测井测点")
        gen_btn.clicked.connect(self._generate_demo_data)
        pts_layout.addWidget(gen_btn)

        self.points_table = QTableWidget(0, 3)
        self.points_table.setHorizontalHeaderLabels(["X", "Y", "Z (厚度)"])
        self.points_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.points_table.verticalHeader().setVisible(False)
        self.points_table.setStyleSheet("""
            QTableWidget {
                background: white;
                border: 1px solid #cbd5e0;
                font-size: 11px;
                color: #2d3748;
            }
        """)
        self.points_table.setFixedHeight(160)
        pts_layout.addWidget(self.points_table)
        panel_layout.addWidget(pts_group)

        # Group 2: Interpolation settings
        interp_group = QGroupBox("空间三维网格插值")
        interp_layout = QVBoxLayout(interp_group)
        interp_layout.setSpacing(10)

        # Method
        method_row = QHBoxLayout()
        method_label = QLabel("插值算法:")
        self.method_combo = QComboBox()
        self.method_combo.addItems(["IDW (反距离权重)", "SciPy Linear", "SciPy Cubic", "SciPy Nearest", "SciPy RBF (径向基)"])
        self.method_combo.currentIndexChanged.connect(self._on_settings_changed)
        method_row.addWidget(method_label)
        method_row.addWidget(self.method_combo)
        interp_layout.addLayout(method_row)

        # IDW Power
        self.power_row = QHBoxLayout()
        self.power_label = QLabel("IDW 权重系数 (2.0):")
        self.power_slider = QSlider(Qt.Orientation.Horizontal)
        self.power_slider.setMinimum(10)
        self.power_slider.setMaximum(40)
        self.power_slider.setValue(20)
        self.power_slider.setSingleStep(5)
        self.power_slider.valueChanged.connect(self._on_power_changed)
        self.power_row.addWidget(self.power_label)
        self.power_row.addWidget(self.power_slider)
        interp_layout.addLayout(self.power_row)

        # Mask Convex Hull
        mask_row = QHBoxLayout()
        self.mask_checkbox = QCheckBox("外插凸包截断裁剪")
        self.mask_checkbox.setChecked(True)
        self.mask_checkbox.stateChanged.connect(self._on_settings_changed)
        mask_row.addWidget(self.mask_checkbox)
        interp_layout.addLayout(mask_row)

        # Grid Resolution
        res_row = QHBoxLayout()
        res_label = QLabel("网格剖分精度:")
        self.res_combo = QComboBox()
        self.res_combo.addItems(["50 x 50", "100 x 100", "200 x 200", "300 x 300"])
        self.res_combo.setCurrentIndex(1)  # Default 100x100
        self.res_combo.currentIndexChanged.connect(self._on_settings_changed)
        res_row.addWidget(res_label)
        res_row.addWidget(self.res_combo)
        interp_layout.addLayout(res_row)

        panel_layout.addWidget(interp_group)

        # Group 3: Contours and Colors
        contour_group = QGroupBox("等值线样式与渲染")
        contour_layout = QVBoxLayout(contour_group)
        contour_layout.setSpacing(10)

        # Colormap
        cmap_row = QHBoxLayout()
        cmap_label = QLabel("标准地质色标:")
        self.cmap_combo = QComboBox()
        self.cmap_combo.addItem("cnpc_strat (岩相标准)", "cnpc_strat")
        self.cmap_combo.addItem("cnpc_fluid (流体标准)", "cnpc_fluid")
        self.cmap_combo.addItem("viridis (火山经典)", "viridis")
        self.cmap_combo.addItem("thermal (冷热分布)", "thermal")
        self.cmap_combo.currentIndexChanged.connect(self._on_colormap_changed)
        cmap_row.addWidget(cmap_label)
        cmap_row.addWidget(self.cmap_combo)
        contour_layout.addLayout(cmap_row)

        # Step
        step_row = QHBoxLayout()
        step_label = QLabel("等值线间距:")
        self.step_spin = QDoubleSpinBox()
        self.step_spin.setRange(0.1, 10.0)
        self.step_spin.setValue(1.0)
        self.step_spin.setSingleStep(0.5)
        self.step_spin.valueChanged.connect(self._on_settings_changed)
        step_row.addWidget(step_label)
        step_row.addWidget(self.step_spin)
        contour_layout.addLayout(step_row)

        # Stats
        self.stats_label = QLabel("数值范围: [—, —]")
        self.stats_label.setStyleSheet("font-size: 11px; color: #718096; font-style: italic;")
        contour_layout.addWidget(self.stats_label)

        panel_layout.addWidget(contour_group)

        # Group 4: Export Vector Graphics
        export_group = QGroupBox("矢量级成果导出")
        export_layout = QHBoxLayout(export_group)
        export_layout.setSpacing(10)

        export_svg_btn = QPushButton("导出 SVG")
        export_svg_btn.clicked.connect(self._export_svg)
        export_pdf_btn = QPushButton("导出 PDF")
        export_pdf_btn.clicked.connect(self._export_pdf)
        export_layout.addWidget(export_svg_btn)
        export_layout.addWidget(export_pdf_btn)

        panel_layout.addWidget(export_group)

        panel_layout.addStretch()
        main_layout.addWidget(control_panel)

        # ------------------ Right Main Plot Canvas ------------------
        plot_container = QWidget()
        plot_container_layout = QVBoxLayout(plot_container)
        plot_container_layout.setContentsMargins(0, 0, 0, 0)
        plot_container_layout.setSpacing(0)

        self.surface_plot = SurfaceWidget(self)
        plot_container_layout.addWidget(self.surface_plot, 1)

        # Status row
        self.status_bar = QLabel("就绪")
        self.status_bar.setFixedHeight(22)
        self.status_bar.setStyleSheet("""
            font-size: 11px;
            color: #718096;
            border-top: 1px solid #e2e8f0;
            padding-left: 8px;
            background: #f7fafc;
        """)
        plot_container_layout.addWidget(self.status_bar)

        main_layout.addWidget(plot_container, 1)

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

        # Cancel active thread
        if self._worker is not None and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait()

        # Instantiate async worker
        self._worker = InterpolationWorker(
            self.points_x, self.points_y, self.points_z,
            grid_x, grid_y, method=method,
            mask_convex_hull=mask, power=power
        )
        self._worker.finished.connect(lambda grid_z, gx=grid_x, gy=grid_y: self._on_interpolation_complete(gx, gy, grid_z))
        self._worker.error.connect(self._on_interpolation_error)
        self._worker.start()

    def _on_interpolation_complete(self, grid_x, grid_y, grid_z):
        """Update the canvas plot bounds when background calculation thread finishes."""
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
            from PySide6.QtGui import QPageLayout
            
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(path)
            printer.setPageSize(QPrinter.A4)
            printer.setPageOrientation(QPrinter.Landscape)
            
            page_layout = printer.pageLayout()
            paint_rect = page_layout.paintRectPixels(300)  # 300 DPI high fidelity
            
            painter = QPainter(printer)
            painter.setRenderHint(QPainter.Antialiasing)
            self.surface_plot.render_surface(painter, paint_rect.width(), paint_rect.height())
            painter.end()
            QMessageBox.information(self, "导出成功", f"图件已成功保存为高保真出版级 PDF。\n保存路径: {path}")
