"""QPainter-based vector filled contour and isoline spatial rendering widget."""
import numpy as np
import math
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPointF, Signal, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QFontMetrics, QBrush, QPainterPath
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtPrintSupport import QPrinter

from geoviz_plots.chart.axes import calculate_ticks
from geoviz_plots.surface.marching_squares import extract_contour_lines, extract_filled_contours
from geoviz_plots.surface.colormaps import COLORMAPS, sample_colormap


class SurfaceWidget(QWidget):
    """A premium, responsive spatial contouring and color filled surface mapping widget.
    
    Supports:
    - Custom stratigraphic and fluid colormaps.
    - Smooth vector isoline drawing with text-aligned cut-out labels.
    - Multi-ring odd-even fill block polygons.
    - SVG/PDF vector exports.
    """
    view_changed = Signal(float, float, float, float)  # xmin, xmax, ymin, ymax
    contour_selected = Signal(float)  # selected isoline level
    control_points_changed = Signal(list)  # updated list of control points
    grid_updated = Signal(object, object, object)  # grid_x, grid_y, grid_z

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        
        # Grid parameters
        self.grid_x = None
        self.grid_y = None
        self.grid_z = None
        self.levels = []
        self.colormap_name = "viridis"

        # Control Points & Fault Barriers
        self.control_points = []
        self.fault_polylines = []
        self.selected_cp_idx = None
        self.selected_contour_level = None
        self.is_dragging_cp = False
        
        # Viewport boundaries
        self.view_xmin = 0.0
        self.view_xmax = 1.0
        self.view_ymin = 0.0
        self.view_ymax = 1.0
        
        # Styling parameters (Dark Theme background, elegant colors)
        self.bg_color = QColor(25, 25, 25)
        self.plot_bg_color = QColor(15, 15, 15)
        self.grid_color = QColor(50, 50, 50, 200)
        self.axis_color = QColor(200, 200, 200)
        self.text_color = QColor(210, 210, 210)
        self.contour_line_color = QColor(240, 240, 240, 180)
        
        # Margins
        self.margin_left = 65
        self.margin_right = 25
        self.margin_top = 25
        self.margin_bottom = 50
        
        # Interaction states
        self.last_mouse_pos = None
        self.hover_pos = None

    def set_control_points(self, points: list):
        """Set scattered control points list: [{"id": str, "x": float, "y": float, "z": float}, ...]."""
        self.control_points = list(points)
        self.update()

    def add_control_point(self, x: float, y: float, z: float, point_id: str = None):
        """Add a single control point."""
        if point_id is None:
            point_id = f"cp_{len(self.control_points) + 1}"
        self.control_points.append({"id": point_id, "x": float(x), "y": float(y), "z": float(z)})
        self.control_points_changed.emit(self.control_points)
        self.update()

    def set_fault_polylines(self, polylines: list):
        """Set fault barrier polylines."""
        self.fault_polylines = list(polylines)
        self.update()

    def select_contour_level(self, level: float):
        """Select and highlight a specific contour level."""
        self.selected_contour_level = float(level)
        self.contour_selected.emit(self.selected_contour_level)
        self.update()

    def set_grid_data(self, grid_x, grid_y, grid_z, levels, colormap: str = "viridis"):
        """Bind spatial grid coordinates, Z matrix values, contour levels, and colormap selection."""
        self.grid_x = np.asarray(grid_x, dtype=np.float64)
        self.grid_y = np.asarray(grid_y, dtype=np.float64)
        self.grid_z = np.asarray(grid_z, dtype=np.float64)
        self.levels = sorted(levels)
        self.colormap_name = colormap if colormap in COLORMAPS else "viridis"
        self.update()

    def clear(self) -> None:
        self.grid_x = None
        self.grid_y = None
        self.grid_z = None
        self.levels = []
        self.control_points = []
        self.fault_polylines = []
        self.selected_contour_level = None
        self.view_xmin, self.view_xmax = 0.0, 1.0
        self.view_ymin, self.view_ymax = 0.0, 1.0
        self.update()


    def autofit(self):
        """Auto-scale the viewport to fit the grid data boundary dimensions exactly."""
        if self.grid_x is None or self.grid_y is None:
            self.view_xmin, self.view_xmax = 0.0, 1.0
            self.view_ymin, self.view_ymax = 0.0, 1.0
            self.update()
            return
            
        self.view_xmin = float(np.min(self.grid_x))
        self.view_xmax = float(np.max(self.grid_x))
        self.view_ymin = float(np.min(self.grid_y))
        self.view_ymax = float(np.max(self.grid_y))
        
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
            
        # Hover coordinate tracing
        if left <= curr_pos.x() <= right and top <= curr_pos.y() <= bottom:
            self.hover_pos = curr_pos
        else:
            self.hover_pos = None
            
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

    # Color interpolation manager
    def get_color(self, val: float) -> QColor:
        """Linearly interpolate color from the active colormap according to the Z value range."""
        if not self.levels:
            return QColor(100, 100, 100)
        return sample_colormap(self.colormap_name, val, self.levels[0], self.levels[-1])

    # Vector Exports
    def export_svg(self, filepath: str):
        """Export the surface to an SVG vector file."""
        generator = QSvgGenerator()
        generator.setFileName(filepath)
        generator.setSize(self.size())
        generator.setViewBox(self.rect())
        generator.setTitle(f"GeoViz Surface Map - {self.windowTitle()}")
        generator.setDescription("Generated by GeoViz Engine QPainter Surface core.")
        
        painter = QPainter(generator)
        painter.setRenderHint(QPainter.Antialiasing)
        self.render_surface(painter, self.width(), self.height())
        painter.end()

    def export_pdf(self, filepath: str):
        """Export the surface map to a PDF vector file."""
        from PySide6.QtGui import QPageSize
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(filepath)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))

        page_rect = printer.pageRect(QPrinter.DevicePixel)
        
        painter = QPainter(printer)
        painter.setRenderHint(QPainter.Antialiasing)
        self.render_surface(painter, page_rect.width(), page_rect.height())
        painter.end()

    # Core Paint Events
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self.render_surface(painter, self.width(), self.height())
        painter.end()

    def render_surface(self, painter: QPainter, width: int, height: int):
        """Draw the filled contours, isolines, axes, and text labels on the painter."""
        # 1. Fill entire widget background
        painter.fillRect(0, 0, width, height, self.bg_color)
        
        left, right, top, bottom = self.get_plot_rect(width, height)
        plot_w = right - left
        plot_h = bottom - top
        
        if plot_w <= 0 or plot_h <= 0:
            return
            
        # 2. Draw interior background
        painter.fillRect(left, top, plot_w, plot_h, self.plot_bg_color)
        
        if self.grid_x is None or self.grid_y is None or self.grid_z is None or not self.levels:
            return
            
        # Coordinates mapping lambda inside render boundary
        def to_p(x_val, y_val):
            x_r = self.view_xmax - self.view_xmin
            y_r = self.view_ymax - self.view_ymin
            if x_r == 0: x_r = 1.0
            if y_r == 0: y_r = 1.0
            px = left + (x_val - self.view_xmin) / x_r * plot_w
            py = bottom - (y_val - self.view_ymin) / y_r * plot_h
            return px, py
            
        # Clip painter to plotting rectangle boundary so rendering does not spill over margins
        painter.save()
        painter.setClipRect(QRectF(left, top, plot_w, plot_h))
        
        # 3. Draw Filled Contours (Color blocks)
        try:
            bands = extract_filled_contours(self.grid_x, self.grid_y, self.grid_z, self.levels)
            for band in bands:
                color = QColor(band.color)
                color.setAlpha(180)  # Standard clean alpha transparency

                painter.setBrush(QBrush(color))
                painter.setPen(Qt.NoPen)

                for poly_coords, offset_arr in zip(band.polygons, band.offsets):
                    path = QPainterPath()
                    path.setFillRule(Qt.OddEvenFill)

                    for j in range(len(offset_arr) - 1):
                        start_idx = offset_arr[j]
                        end_idx = offset_arr[j+1]
                        ring_pts = poly_coords[start_idx:end_idx]
                        if len(ring_pts) < 3:
                            continue

                        px, py = to_p(ring_pts[0][0], ring_pts[0][1])
                        path.moveTo(px, py)
                        for pt in ring_pts[1:]:
                            px, py = to_p(pt[0], pt[1])
                            path.lineTo(px, py)
                        path.closeSubpath()

                    painter.drawPath(path)
        except Exception:
            pass  # Fail-safe protection
            
        # 4. Draw Vector Contour Isolines & Labels (with advanced text cut-outs)
        try:
            lines_dict = extract_contour_lines(self.grid_x, self.grid_y, self.grid_z, self.levels)
            
            painter.setFont(QFont("Arial", 8, QFont.Bold))
            font_metrics = QFontMetrics(painter.font())
            
            sorted_levels = sorted(lines_dict.keys())
            major_every = 5  # every 5th contour level is major
            for level_index, lv in enumerate(sorted_levels):
                lines = lines_dict[lv]
                is_major = level_index % major_every == 0
                line_pen = QPen(self.contour_line_color, 1.2 if is_major else 0.6, Qt.SolidLine)
                painter.setPen(line_pen)
                painter.setBrush(Qt.NoBrush)
                
                label_txt = f"{lv:.1f}"
                txt_w = font_metrics.horizontalAdvance(label_txt)
                txt_h = font_metrics.height()
                
                for line in lines:
                    if len(line) < 2:
                        continue
                        
                    # Calculate total path length in pixels to determine if we should draw a label
                    pixels = [to_p(pt[0], pt[1]) for pt in line]
                    total_len = 0.0
                    for k in range(len(pixels) - 1):
                        total_len += math.hypot(pixels[k+1][0] - pixels[k][0], pixels[k+1][1] - pixels[k][1])
                        
                    # Draw text cut-out label if line path is long enough (> 130 pixels)
                    if total_len > 130.0:
                        # Find midpoint by pixel length
                        half_len = total_len / 2.0
                        cum_len = 0.0
                        mid_idx = 0
                        for k in range(len(pixels) - 1):
                            d = math.hypot(pixels[k+1][0] - pixels[k][0], pixels[k+1][1] - pixels[k][1])
                            if cum_len + d >= half_len:
                                mid_idx = k
                                break
                            cum_len += d
                            
                        # Mid segment points
                        pt_mid = pixels[mid_idx]
                        pt_next = pixels[mid_idx+1]
                        
                        # Direction angle of path segment
                        dx = pt_next[0] - pt_mid[0]
                        dy = pt_next[1] - pt_mid[1]
                        angle = math.atan2(dy, dx)
                        # Keep text facing upright
                        if dx < 0:
                            angle += math.pi
                            
                        # Determine indices for cut-out gap
                        # Gap of text_width + 10 pixels padding
                        gap_pixels = txt_w + 10.0
                        half_gap = gap_pixels / 2.0
                        
                        # Loop through and split drawing at gap entrance/exit
                        path_start = QPainterPath()
                        path_end = QPainterPath()
                        
                        in_start = True
                        in_gap = False
                        
                        cum_draw = 0.0
                        for k in range(len(pixels)):
                            if k == 0:
                                path_start.moveTo(pixels[0][0], pixels[0][1])
                                continue
                                
                            seg_d = math.hypot(pixels[k][0] - pixels[k-1][0], pixels[k][1] - pixels[k-1][1])
                            cum_draw += seg_d
                            
                            # Entering gap
                            if in_start and cum_draw >= half_len - half_gap:
                                in_start = False
                                in_gap = True
                                # Add line up to gap boundary
                                w_ratio = (half_len - half_gap - (cum_draw - seg_d)) / seg_d
                                gap_entry_x = pixels[k-1][0] + w_ratio * (pixels[k][0] - pixels[k-1][0])
                                gap_entry_y = pixels[k-1][1] + w_ratio * (pixels[k][1] - pixels[k-1][1])
                                path_start.lineTo(gap_entry_x, gap_entry_y)
                                continue
                                
                            # Exiting gap
                            if in_gap and cum_draw >= half_len + half_gap:
                                in_gap = False
                                # Resume drawing after gap boundary
                                w_ratio = (half_len + half_gap - (cum_draw - seg_d)) / seg_d
                                gap_exit_x = pixels[k-1][0] + w_ratio * (pixels[k][0] - pixels[k-1][0])
                                gap_exit_y = pixels[k-1][1] + w_ratio * (pixels[k][1] - pixels[k-1][1])
                                path_end.moveTo(gap_exit_x, gap_exit_y)
                                path_end.lineTo(pixels[k][0], pixels[k][1])
                                continue
                                
                            if in_start:
                                path_start.lineTo(pixels[k][0], pixels[k][1])
                            elif not in_gap:
                                path_end.lineTo(pixels[k][0], pixels[k][1])
                                
                        painter.drawPath(path_start)
                        painter.drawPath(path_end)
                        
                        # Render rotated text cleanly in the gap
                        painter.save()
                        painter.translate(pt_mid[0], pt_mid[1])
                        painter.rotate(math.degrees(angle))
                        
                        # Text color
                        painter.setPen(self.text_color)
                        # Draw centered text
                        painter.drawText(-txt_w / 2, txt_h / 4, label_txt)
                        painter.restore()
                        
                        # Restore active isoline pen
                        painter.setPen(line_pen)
                    else:
                        # Draw entire line without label cut-out for short isolines
                        path = QPainterPath()
                        path.moveTo(pixels[0][0], pixels[0][1])
                        for pt in pixels[1:]:
                            path.lineTo(pt[0], pt[1])
                        painter.drawPath(path)
        except Exception:
            pass  # Fail-safe protection
            
        painter.restore()  # End clip rect
        
        # 5. Draw Interactive Coordinates Hover
        if self.hover_pos is not None:
            painter.save()
            cross_pen = QPen(QColor(255, 165, 0, 150), 1, Qt.DashLine)
            painter.setPen(cross_pen)
            painter.drawLine(self.hover_pos.x(), top, self.hover_pos.x(), bottom)
            painter.drawLine(left, self.hover_pos.y(), right, self.hover_pos.y())
            
            # Text coordinates bubble
            dx, dy = self.pixel_to_data(self.hover_pos.x(), self.hover_pos.y())
            lbl_txt = f"X: {dx:.2f}\nY: {dy:.2f}"
            
            painter.setFont(QFont("Monospace", 8))
            painter.setPen(self.text_color)
            painter.drawText(self.hover_pos.x() + 10, self.hover_pos.y() - 10, lbl_txt)
            painter.restore()
            
        # 6. Draw axis borders & tick labels (above plot data overlay)
        painter.save()
        axis_pen = QPen(self.axis_color, 1.5, Qt.SolidLine)
        painter.setPen(axis_pen)
        painter.setFont(QFont("Arial", 9))
        
        # Border box
        painter.drawRect(left, top, plot_w, plot_h)
        
        font_metrics = QFontMetrics(painter.font())
        x_ticks, x_step = calculate_ticks(self.view_xmin, self.view_xmax, 6)
        y_ticks, y_step = calculate_ticks(self.view_ymin, self.view_ymax, 6)
        
        # X Ticks
        for xt in x_ticks:
            if self.view_xmin <= xt <= self.view_xmax:
                px, _ = to_p(xt, self.view_ymin)
                painter.drawLine(px, bottom, px, bottom + 5)
                
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
                
                label = f"{yt:.2f}"
                lbl_w = font_metrics.horizontalAdvance(label)
                painter.setPen(self.text_color)
                painter.drawText(left - lbl_w - 10, py + font_metrics.height() / 4, label)
                painter.setPen(axis_pen)
                
        painter.restore()
