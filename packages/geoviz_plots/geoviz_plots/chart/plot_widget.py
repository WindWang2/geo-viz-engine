"""QPainter-based high-performance 2D Line and Scatter plotting widget."""
import numpy as np
import math
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPointF, Signal, Slot, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QFontMetrics, QBrush, QPolygonF
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtPrintSupport import QPrinter

from geoviz_plots.chart.axes import calculate_ticks
from geoviz_plots.chart.series import LineSeries, ScatterSeries, lttb_downsample

class PlotWidget(QWidget):
    """A premium, responsive, QPainter-based 2D plotting widget for lines and scatter series.
    
    Supports:
    - Custom margin & axis ticking via Heckbert's algorithm.
    - Interactive panning, zooming (mouse wheel at cursor), and autofit.
    - LTTB downsampling for maintaining high rendering performance (> 60 FPS) with large datasets.
    - Interactive linking: emits signal on point hover/selection, and allows highlighted coordinates.
    - SVG/PDF vector exports.
    """
    # Signals for interactive linking
    point_selected = Signal(str, int, float, float)  # series_name, index, x, y
    view_changed = Signal(float, float, float, float)  # xmin, xmax, ymin, ymax

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        
        self.series_list = []
        
        # Viewport boundaries in data coordinates
        self.view_xmin = 0.0
        self.view_xmax = 1.0
        self.view_ymin = 0.0
        self.view_ymax = 1.0
        
        # Styling parameters (Premium Elegant Dark Theme by default)
        self.bg_color = QColor(25, 25, 25)
        self.plot_bg_color = QColor(15, 15, 15)
        self.grid_color = QColor(45, 45, 45, 200)
        self.axis_color = QColor(200, 200, 200)
        self.text_color = QColor(210, 210, 210)
        self.crosshair_color = QColor(255, 165, 0, 120)  # Subtle orange
        self.highlight_color = QColor(255, 69, 0)
        
        # Margins around the plotting canvas
        self.margin_left = 65
        self.margin_right = 25
        self.margin_top = 25
        self.margin_bottom = 50
        
        # Interaction states
        self.last_mouse_pos = None
        self.hover_pos = None
        self.selected_point = None  # (series_name, index)
        self.highlighted_points = {}  # series_name -> set(index)
        
        # Downsampling threshold
        self.downsample_threshold = 2000

    def add_series(self, series):
        """Add a data series (LineSeries or ScatterSeries) to the plot."""
        self.series_list.append(series)
        self.update()

    def clear(self):
        """Clear all series from the plot."""
        self.series_list.clear()
        self.highlighted_points.clear()
        self.selected_point = None
        self.update()

    def autofit(self):
        """Auto-scale the viewport to fit all visible data with a 5% margin buffer."""
        if not self.series_list:
            self.view_xmin, self.view_xmax = 0.0, 1.0
            self.view_ymin, self.view_ymax = 0.0, 1.0
            self.update()
            return
            
        g_xmin, g_xmax = float('inf'), float('-inf')
        g_ymin, g_ymax = float('inf'), float('-inf')
        
        has_data = False
        for s in self.series_list:
            if not s.visible:
                continue
            xmin, xmax, ymin, ymax = s.get_bounds()
            if xmin == xmax == ymin == ymax == 0.0 and len(s.x) == 0:
                continue
            has_data = True
            g_xmin = min(g_xmin, xmin)
            g_xmax = max(g_xmax, xmax)
            g_ymin = min(g_ymin, ymin)
            g_ymax = max(g_ymax, ymax)
            
        if not has_data:
            self.view_xmin, self.view_xmax = 0.0, 1.0
            self.view_ymin, self.view_ymax = 0.0, 1.0
            self.update()
            return
            
        # Add 5% padding
        dx = g_xmax - g_xmin
        dy = g_ymax - g_ymin
        if dx == 0.0:
            dx = abs(g_xmin) * 0.1 if g_xmin != 0.0 else 1.0
        if dy == 0.0:
            dy = abs(g_ymin) * 0.1 if g_ymin != 0.0 else 1.0
            
        self.view_xmin = g_xmin - 0.05 * dx
        self.view_xmax = g_xmax + 0.05 * dx
        self.view_ymin = g_ymin - 0.05 * dy
        self.view_ymax = g_ymax + 0.05 * dy
        
        self.view_changed.emit(self.view_xmin, self.view_xmax, self.view_ymin, self.view_ymax)
        self.update()

    def get_plot_rect(self, width, height) -> tuple[float, float, float, float]:
        """Return the plotting area canvas rectangle bounds: (left, right, top, bottom)."""
        return (
            self.margin_left, 
            width - self.margin_right, 
            self.margin_top, 
            height - self.margin_bottom
        )

    def data_to_pixel(self, x: float, y: float) -> tuple[float, float]:
        """Map data coordinates to pixel coordinates."""
        left, right, top, bottom = self.get_plot_rect(self.width(), self.height())
        plot_w = right - left
        plot_h = bottom - top
        
        x_range = self.view_xmax - self.view_xmin
        y_range = self.view_ymax - self.view_ymin
        
        if x_range == 0: x_range = 1.0
        if y_range == 0: y_range = 1.0
        
        px = left + (x - self.view_xmin) / x_range * plot_w
        py = bottom - (y - self.view_ymin) / y_range * plot_h
        return px, py

    def pixel_to_data(self, px: float, py: float) -> tuple[float, float]:
        """Map pixel coordinates back to data coordinates."""
        left, right, top, bottom = self.get_plot_rect(self.width(), self.height())
        plot_w = right - left
        plot_h = bottom - top
        
        x_range = self.view_xmax - self.view_xmin
        y_range = self.view_ymax - self.view_ymin
        
        if plot_w == 0: plot_w = 1.0
        if plot_h == 0: plot_h = 1.0
        
        x = self.view_xmin + (px - left) / plot_w * x_range
        y = self.view_ymin + (bottom - py) / plot_h * y_range
        return x, y

    def pan(self, dpx: float, dpy: float):
        """Pan the viewport by pixel coordinates shift delta (dpx, dpy)."""
        left, right, top, bottom = self.get_plot_rect(self.width(), self.height())
        plot_w = right - left
        plot_h = bottom - top
        
        if plot_w <= 0 or plot_h <= 0:
            return
            
        x_range = self.view_xmax - self.view_xmin
        y_range = self.view_ymax - self.view_ymin
        
        dx = (dpx / plot_w) * x_range
        dy = -(dpy / plot_h) * y_range
        
        self.view_xmin -= dx
        self.view_xmax -= dx
        self.view_ymin -= dy
        self.view_ymax -= dy
        
        self.view_changed.emit(self.view_xmin, self.view_xmax, self.view_ymin, self.view_ymax)
        self.update()

    def zoom(self, factor: float, cx: float, cy: float):
        """Zoom the viewport by a factor relative to a center point in data coordinates (cx, cy)."""
        if factor <= 0.0:
            return
            
        self.view_xmin = cx - (cx - self.view_xmin) / factor
        self.view_xmax = cx + (self.view_xmax - cx) / factor
        self.view_ymin = cy - (cy - self.view_ymin) / factor
        self.view_ymax = cy + (self.view_ymax - cy) / factor
        
        self.view_changed.emit(self.view_xmin, self.view_xmax, self.view_ymin, self.view_ymax)
        self.update()

    # Inter-page data linking highlight methods
    def highlight_point(self, series_name: str, index: int):
        """Highlight a specific point from external widgets/pages."""
        if series_name not in self.highlighted_points:
            self.highlighted_points[series_name] = set()
        self.highlighted_points[series_name].add(index)
        self.update()

    def clear_highlights(self):
        """Clear all highlighted points."""
        self.highlighted_points.clear()
        self.update()

    # Interaction Events
    def mousePressEvent(self, event):
        if event.button() in (Qt.LeftButton, Qt.MiddleButton):
            self.last_mouse_pos = event.position()
            
    def mouseMoveEvent(self, event):
        curr_pos = event.position()
        left, right, top, bottom = self.get_plot_rect(self.width(), self.height())
        
        # Panning
        if event.buttons() in (Qt.LeftButton, Qt.MiddleButton) and self.last_mouse_pos is not None:
            dpx = curr_pos.x() - self.last_mouse_pos.x()
            dpy = curr_pos.y() - self.last_mouse_pos.y()
            self.pan(dpx, dpy)
            self.last_mouse_pos = curr_pos
            return
            
        # Hover / tracking
        if left <= curr_pos.x() <= right and top <= curr_pos.y() <= bottom:
            self.hover_pos = curr_pos
            # Find closest point
            self.check_nearest_point(curr_pos)
        else:
            self.hover_pos = None
            self.selected_point = None
            
        self.update()

    def mouseReleaseEvent(self, event):
        self.last_mouse_pos = None

    def wheelEvent(self, event):
        curr_pos = event.position()
        left, right, top, bottom = self.get_plot_rect(self.width(), self.height())
        if not (left <= curr_pos.x() <= right and top <= curr_pos.y() <= bottom):
            return
            
        cx, cy = self.pixel_to_data(curr_pos.x(), curr_pos.y())
        angle = event.angleDelta().y()
        factor = 1.15 if angle > 0 else (1.0 / 1.15)
        self.zoom(factor, cx, cy)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.autofit()

    def check_nearest_point(self, mouse_pos):
        """Identify if a point is close to the mouse cursor, and emit interactive linking signal."""
        closest_dist = 15.0  # Activation radius in pixels
        closest_pt = None  # (series, index, x, y)
        
        for s in self.series_list:
            if not s.visible or len(s.x) == 0:
                continue
                
            # Efficient spatial bounds check
            mask = ~np.isnan(s.x) & ~np.isnan(s.y)
            sx = s.x[mask]
            sy = s.y[mask]
            indices = np.where(mask)[0]
            
            for idx, x_val, y_val in zip(indices, sx, sy):
                px, py = self.data_to_pixel(x_val, y_val)
                dist = math.hypot(mouse_pos.x() - px, mouse_pos.y() - py)
                if dist < closest_dist:
                    closest_dist = dist
                    closest_pt = (s.name, idx, x_val, y_val)
                    
        if closest_pt:
            s_name, idx, x_val, y_val = closest_pt
            if self.selected_point != (s_name, idx):
                self.selected_point = (s_name, idx)
                self.point_selected.emit(s_name, int(idx), float(x_val), float(y_val))
        else:
            self.selected_point = None

    # Vector Export implementation
    def export_svg(self, filepath: str):
        """Export the plot to a vector SVG file."""
        generator = QSvgGenerator()
        generator.setFileName(filepath)
        generator.setSize(self.size())
        generator.setViewBox(self.rect())
        generator.setTitle(f"GeoViz Plot - {self.windowTitle()}")
        generator.setDescription("Generated by GeoViz Engine QPainter plotting core.")
        
        painter = QPainter(generator)
        painter.setRenderHint(QPainter.Antialiasing)
        self.render_plot(painter, self.width(), self.height())
        painter.end()

    def export_pdf(self, filepath: str):
        """Export the plot to a clean vector PDF file."""
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFile(filepath)
        printer.setPageSize(QPrinter.A4)
        
        # Use full page dimensions
        page_rect = printer.pageRect(QPrinter.DevicePixel)
        
        painter = QPainter(printer)
        painter.setRenderHint(QPainter.Antialiasing)
        self.render_plot(painter, page_rect.width(), page_rect.height())
        painter.end()

    # Core Paint & Rendering Core
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self.render_plot(painter, self.width(), self.height())
        painter.end()

    def render_plot(self, painter: QPainter, width: int, height: int):
        """Draw the entire plot canvas onto the provided painter."""
        # 1. Fill entire widget background
        painter.fillRect(0, 0, width, height, self.bg_color)
        
        left, right, top, bottom = self.get_plot_rect(width, height)
        plot_w = right - left
        plot_h = bottom - top
        
        if plot_w <= 0 or plot_h <= 0:
            return
            
        # 2. Draw interior plot background
        painter.fillRect(left, top, plot_w, plot_h, self.plot_bg_color)
        
        # Calculate Nice Ticks for X and Y
        x_ticks, x_step = calculate_ticks(self.view_xmin, self.view_xmax, 6)
        y_ticks, y_step = calculate_ticks(self.view_ymin, self.view_ymax, 6)
        
        # Helper to convert layout coordinates within rendering engine size
        def to_p(x_val, y_val):
            x_r = self.view_xmax - self.view_xmin
            y_r = self.view_ymax - self.view_ymin
            if x_r == 0: x_r = 1.0
            if y_r == 0: y_r = 1.0
            px = left + (x_val - self.view_xmin) / x_r * plot_w
            py = bottom - (y_val - self.view_ymin) / y_r * plot_h
            return px, py
            
        # 3. Draw Grid Lines
        grid_pen = QPen(self.grid_color, 1, Qt.DashLine)
        painter.setPen(grid_pen)
        
        for xt in x_ticks:
            if self.view_xmin <= xt <= self.view_xmax:
                px, _ = to_p(xt, self.view_ymin)
                painter.drawLine(px, top, px, bottom)
                
        for yt in y_ticks:
            if self.view_ymin <= yt <= self.view_ymax:
                _, py = to_p(self.view_xmin, yt)
                painter.drawLine(left, py, right, py)
                
        # 4. Render Series Data
        for s in self.series_list:
            if not s.visible or len(s.x) == 0:
                continue
                
            # Perform LTTB downsampling for huge series to protect UI from rendering lockups
            if len(s.x) > self.downsample_threshold:
                sx, sy = lttb_downsample(s.x, s.y, self.downsample_threshold)
            else:
                sx, sy = s.x, s.y
                
            # Break paths nicely when encountering NaN values
            if isinstance(s, LineSeries):
                line_pen = QPen(s.color, s.width, s.style)
                painter.setPen(line_pen)
                
                in_line = False
                poly = QPolygonF()
                
                for x_val, y_val in zip(sx, sy):
                    if np.isnan(x_val) or np.isnan(y_val):
                        if len(poly) > 1:
                            painter.drawPolyline(poly)
                        poly.clear()
                        in_line = False
                        continue
                        
                    px, py = to_p(x_val, y_val)
                    poly.append(QPointF(px, py))
                    
                if len(poly) > 1:
                    painter.drawPolyline(poly)
                    
                # Draw markers for LineSeries if specified
                if s.marker_size > 0.0 and s.marker_style != "none":
                    self.draw_markers(painter, sx, sy, s.marker_style, s.marker_size, s.color, to_p)
                    
            elif isinstance(s, ScatterSeries):
                self.draw_markers(painter, sx, sy, s.marker_style, s.size, s.color, to_p)

        # 5. Draw interactive hover crosshair & highlight selection
        if self.hover_pos is not None:
            painter.save()
            cross_pen = QPen(self.crosshair_color, 1, Qt.DashLine)
            painter.setPen(cross_pen)
            
            # Vertical & horizontal crosshair lines
            painter.drawLine(self.hover_pos.x(), top, self.hover_pos.x(), bottom)
            painter.drawLine(left, self.hover_pos.y(), right, self.hover_pos.y())
            
            # Hover Coordinate text label near the mouse
            dx, dy = self.pixel_to_data(self.hover_pos.x(), self.hover_pos.y())
            lbl_txt = f"X: {dx:.2f}\nY: {dy:.2f}"
            
            painter.setFont(QFont("Monospace", 8))
            painter.setPen(self.text_color)
            painter.drawText(self.hover_pos.x() + 10, self.hover_pos.y() - 10, lbl_txt)
            painter.restore()
            
        # Draw selected/linked hover point highlight ring
        if self.selected_point is not None:
            s_name, idx = self.selected_point
            series = next((s for s in self.series_list if s.name == s_name), None)
            if series is not None and 0 <= idx < len(series.x):
                px, py = to_p(series.x[idx], series.y[idx])
                painter.save()
                painter.setPen(QPen(self.highlight_color, 2, Qt.SolidLine))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(QPointF(px, py), 9.0, 9.0)
                painter.restore()

        # Draw external highlighted/linked points (from bidirectional Map/Well selection)
        for s_name, indices in self.highlighted_points.items():
            series = next((s for s in self.series_list if s.name == s_name), None)
            if series is None:
                continue
            for idx in indices:
                if 0 <= idx < len(series.x):
                    px, py = to_p(series.x[idx], series.y[idx])
                    painter.save()
                    painter.setPen(QPen(self.highlight_color, 1.5, Qt.SolidLine))
                    # Draw a nice pulse indicator (concentric rings)
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(QPointF(px, py), 6.0, 6.0)
                    painter.drawEllipse(QPointF(px, py), 10.0, 10.0)
                    painter.restore()

        # 6. Draw axis borders & tick labels (above plot data overlay)
        painter.save()
        axis_pen = QPen(self.axis_color, 1.5, Qt.SolidLine)
        painter.setPen(axis_pen)
        painter.setFont(QFont("Arial", 9))
        
        # Border
        painter.drawRect(left, top, plot_w, plot_h)
        
        # Draw tick labels
        font_metrics = QFontMetrics(painter.font())
        
        # X Ticks
        for xt in x_ticks:
            if self.view_xmin <= xt <= self.view_xmax:
                px, _ = to_p(xt, self.view_ymin)
                painter.drawLine(px, bottom, px, bottom + 5)
                
                # Center label horizontally
                label = f"{xt:.2f}"
                lbl_w = font_metrics.horizontalAdvance(label)
                painter.setPen(self.text_color)
                painter.drawText(px - lbl_w / 2, bottom + 20, label)
                painter.setPen(axis_pen)
                
        # Y Ticks
        for yt in y_ticks:
            if self.view_ymin <= yt <= self.view_ymax:
                _, py = to_p(self.view_xmin, yt)
                painter.drawLine(left - 5, py, left, py)
                
                # Right align label on Y axis
                label = f"{yt:.2f}"
                lbl_w = font_metrics.horizontalAdvance(label)
                painter.setPen(self.text_color)
                painter.drawText(left - lbl_w - 10, py + font_metrics.height() / 4, label)
                painter.setPen(axis_pen)
                
        painter.restore()

    def draw_markers(self, painter: QPainter, sx, sy, style: str, size: float, color: QColor, to_p):
        """Render point markers using QPainter."""
        painter.save()
        painter.setPen(QPen(color, 1.0, Qt.SolidLine))
        painter.setBrush(QBrush(color))
        
        half = size / 2.0
        
        for x_val, y_val in zip(sx, sy):
            if np.isnan(x_val) or np.isnan(y_val):
                continue
                
            px, py = to_p(x_val, y_val)
            
            if style == "circle":
                painter.drawEllipse(QPointF(px, py), half, half)
            elif style == "square":
                painter.drawRect(QRectF(px - half, py - half, size, size))
            elif style == "triangle":
                poly = QPolygonF([
                    QPointF(px, py - half),
                    QPointF(px - half, py + half),
                    QPointF(px + half, py + half)
                ])
                painter.drawPolygon(poly)
            elif style == "cross":
                painter.drawLine(px - half, py, px + half, py)
                painter.drawLine(px, py - half, px, py + half)
                
        painter.restore()
