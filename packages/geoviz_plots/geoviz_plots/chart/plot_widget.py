"""QPainter-based high-performance 2D Line and Scatter plotting widget."""
import math
import time

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QFontMetrics, QBrush, QPolygonF
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtWidgets import QApplication, QWidget

from geoviz_plots.chart.axes import calculate_ticks, format_tick
from geoviz_plots.chart.series import LineSeries, ScatterSeries, lttb_downsample


class _KDTreeMetadata:
    """Lazy (name, local_idx, x, y) view over packed KD-tree arrays.

    Series names are stored once with offset ranges so a 1e5-point scatter
    does not allocate 1e5 Python tuples.
    """

    __slots__ = ("_names", "_offsets", "_indices", "_xy")

    def __init__(self, names, offsets, indices, xy):
        self._names = list(names)
        self._offsets = np.asarray(offsets, dtype=np.int64)
        self._indices = indices
        self._xy = xy

    def __len__(self):
        return int(self._indices.shape[0])

    def __bool__(self):
        return len(self) > 0

    def __eq__(self, other):
        if other == [] or other is None:
            return len(self) == 0
        try:
            return list(self) == list(other)
        except TypeError:
            return False

    def _name_at(self, idx: int) -> str:
        series_i = int(np.searchsorted(self._offsets, idx, side="right") - 1)
        return self._names[series_i]

    def __getitem__(self, idx):
        return (
            self._name_at(idx),
            int(self._indices[idx]),
            float(self._xy[idx, 0]),
            float(self._xy[idx, 1]),
        )

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]

    def clear(self):
        self._names = []
        self._offsets = np.zeros(1, dtype=np.int64)
        self._indices = np.empty((0,), dtype=np.int64)
        self._xy = np.empty((0, 2), dtype=np.float64)


def _empty_tree_metadata():
    return _KDTreeMetadata(
        [],
        np.zeros(1, dtype=np.int64),
        np.empty((0,), dtype=np.int64),
        np.empty((0, 2), dtype=np.float64),
    )


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
    point_hovered = Signal(str, int, float, float)  # series_name, index, x, y
    point_hover_cleared = Signal()
    point_clicked = Signal(str, int, float, float)  # series_name, index, x, y
    # Deprecated compatibility attribute. It no longer emits because its
    # historical hover semantics contradicted the name; use point_hovered or
    # point_clicked according to intent.
    point_selected = Signal(str, int, float, float)
    reset_requested = Signal()
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
        self._equal_aspect = False
        self._autofit_bounds = None
        self._full_view_bounds = None
        
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
        self._x_axis_label = ""
        self._y_axis_label = ""
        
        # Interaction states
        self.last_mouse_pos = None
        self._press_pos = None
        self._dragged_since_press = False
        self._last_click_pos = None
        self._last_click_hit = None
        self._last_click_time = 0.0
        self.hover_pos = None
        self.hovered_point = None  # (series_name, index)
        self.selected_point = None  # (series_name, index)
        self.selected_label = ""
        self.highlighted_points = {}  # series_name -> set(index)
        
        self._kdtree = None
        self._tree_xy = np.empty((0, 2), dtype=np.float64)
        self._tree_names = []
        self._tree_offsets = np.zeros(1, dtype=np.int64)
        self._tree_indices = np.empty((0,), dtype=np.int64)
        self._tree_metadata = _empty_tree_metadata()
        self._pixel_tree_key = None
        self._tree_pixel_xy = np.empty((0, 2), dtype=np.float64)
        self.downsample_threshold = 2000

    def _reset_kdtree(self):
        self._kdtree = None
        self._tree_xy = np.empty((0, 2), dtype=np.float64)
        self._tree_names = []
        self._tree_offsets = np.zeros(1, dtype=np.int64)
        self._tree_indices = np.empty((0,), dtype=np.int64)
        self._tree_metadata = _empty_tree_metadata()
        self._pixel_tree_key = None
        self._tree_pixel_xy = np.empty((0, 2), dtype=np.float64)

    def _rebuild_kdtree(self):
        """Build a spatial index of all points for fast snapping."""
        try:
            from scipy.spatial import cKDTree as KDTree
        except ImportError:
            self._reset_kdtree()
            return

        xs_parts = []
        ys_parts = []
        names = []
        offsets = [0]
        idx_parts = []
        for s in self.series_list:
            if not s.visible or len(s.x) == 0:
                continue
            mask = np.isfinite(s.x) & np.isfinite(s.y)
            if not np.any(mask):
                continue
            sx = np.asarray(s.x[mask], dtype=np.float64)
            sy = np.asarray(s.y[mask], dtype=np.float64)
            xs_parts.append(sx)
            ys_parts.append(sy)
            names.append(s.name)
            offsets.append(offsets[-1] + int(sx.shape[0]))
            idx_parts.append(np.flatnonzero(mask).astype(np.int64, copy=False))

        if not xs_parts:
            self._reset_kdtree()
            return

        points = np.column_stack((np.concatenate(xs_parts), np.concatenate(ys_parts)))
        self._tree_xy = points
        self._tree_names = names
        self._tree_offsets = np.asarray(offsets, dtype=np.int64)
        self._tree_indices = np.concatenate(idx_parts)
        self._kdtree = KDTree(
            points,
            copy_data=False,
            compact_nodes=False,
            balanced_tree=False,
        )
        self._pixel_tree_key = None
        self._tree_metadata = _KDTreeMetadata(
            self._tree_names,
            self._tree_offsets,
            self._tree_indices,
            self._tree_xy,
        )

    def _pixel_points(self) -> np.ndarray:
        """Map packed data-space tree points to the current plot pixels."""
        left, right, top, bottom = self.get_plot_rect(self.width(), self.height())
        plot_w = max(right - left, 1.0)
        plot_h = max(bottom - top, 1.0)
        x_range = self.view_xmax - self.view_xmin or 1.0
        y_range = self.view_ymax - self.view_ymin or 1.0
        px = left + (self._tree_xy[:, 0] - self.view_xmin) / x_range * plot_w
        py = bottom - (self._tree_xy[:, 1] - self.view_ymin) / y_range * plot_h
        return np.column_stack((px, py))

    def _ensure_pixel_kdtree(self) -> None:
        """Rebuild the snap index in pixel space when the view or size changes."""
        if self._tree_xy.size == 0:
            return
        key = (
            self.view_xmin,
            self.view_xmax,
            self.view_ymin,
            self.view_ymax,
            int(self.width()),
            int(self.height()),
        )
        if self._kdtree is not None and self._pixel_tree_key == key:
            return
        try:
            from scipy.spatial import cKDTree as KDTree
        except ImportError:
            return
        self._tree_pixel_xy = np.ascontiguousarray(self._pixel_points())
        self._kdtree = KDTree(
            self._tree_pixel_xy,
            copy_data=False,
            compact_nodes=False,
            balanced_tree=False,
        )
        self._pixel_tree_key = key

    def add_series(self, series):
        """Add a data series (LineSeries or ScatterSeries) to the plot."""
        self.series_list.append(series)
        self._rebuild_kdtree()
        self.update()

    def clear(self):
        """Clear all series from the plot."""
        self._invalidate_hover()
        self._clear_last_click()
        self.last_mouse_pos = None
        self._press_pos = None
        self._dragged_since_press = False
        self.series_list.clear()
        self.highlighted_points.clear()
        self.selected_point = None
        self.selected_label = ""
        self._tree_metadata.clear()
        self._rebuild_kdtree()
        self._autofit_bounds = None
        self._full_view_bounds = None
        self.update()

    def set_equal_aspect(self, enabled: bool) -> None:
        """Keep one data unit the same physical size on both axes."""
        self._equal_aspect = bool(enabled)
        if not self._equal_aspect:
            return
        if self._autofit_bounds is not None:
            self._full_view_bounds = self._equalized_bounds(self._autofit_bounds)
        self._apply_view(self._equalized_bounds(self._current_view()))

    def autofit(self):
        """Auto-scale the viewport to fit all visible data with a 5% margin buffer."""
        if not self.series_list:
            self._autofit_bounds = (0.0, 1.0, 0.0, 1.0)
            self._full_view_bounds = self._view_for_current_aspect(
                self._autofit_bounds
            )
            self._apply_view(self._full_view_bounds)
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
            self._autofit_bounds = (0.0, 1.0, 0.0, 1.0)
            self._full_view_bounds = self._view_for_current_aspect(
                self._autofit_bounds
            )
            self._apply_view(self._full_view_bounds)
            return
            
        # Add 5% padding
        dx = g_xmax - g_xmin
        dy = g_ymax - g_ymin
        if dx == 0.0:
            dx = abs(g_xmin) * 0.1 if g_xmin != 0.0 else 1.0
        if dy == 0.0:
            dy = abs(g_ymin) * 0.1 if g_ymin != 0.0 else 1.0
            
        self._autofit_bounds = (
            g_xmin - 0.05 * dx,
            g_xmax + 0.05 * dx,
            g_ymin - 0.05 * dy,
            g_ymax + 0.05 * dy,
        )
        self._full_view_bounds = self._view_for_current_aspect(
            self._autofit_bounds
        )
        self._apply_view(self._full_view_bounds)

    def focus_point(
        self,
        x: float,
        y: float,
        *,
        zoom_factor: float = 4.0,
    ) -> None:
        """Center a fixed zoom derived from the last autofit view."""
        if zoom_factor <= 0.0:
            raise ValueError("zoom_factor must be positive")
        if self._full_view_bounds is None:
            self.autofit()
        assert self._full_view_bounds is not None
        full_xmin, full_xmax, full_ymin, full_ymax = self._full_view_bounds
        half_width = (full_xmax - full_xmin) / (2.0 * zoom_factor)
        half_height = (full_ymax - full_ymin) / (2.0 * zoom_factor)
        self._apply_view(
            (
                float(x) - half_width,
                float(x) + half_width,
                float(y) - half_height,
                float(y) + half_height,
            )
        )

    def reset_view(self) -> None:
        """Restore the full data view recorded by the last autofit."""
        if self._full_view_bounds is None:
            self.autofit()
            return
        self._apply_view(self._full_view_bounds)

    def view_bounds(self) -> tuple[float, float, float, float]:
        """Return the exact current data viewport."""
        return self._current_view()

    def set_view_bounds(
        self,
        bounds: tuple[float, float, float, float],
    ) -> None:
        """Restore an exact data viewport previously returned by view_bounds."""
        values = tuple(float(value) for value in bounds)
        if (
            len(values) != 4
            or not all(math.isfinite(value) for value in values)
            or values[0] >= values[1]
            or values[2] >= values[3]
        ):
            raise ValueError("view bounds must be finite increasing ranges")
        self._apply_view(values)

    def set_axis_labels(self, x_label: str, y_label: str) -> None:
        """Set caller-owned, domain-neutral X/Y axis titles."""
        self._x_axis_label = str(x_label)
        self._y_axis_label = str(y_label)
        self.update()

    def axis_labels(self) -> tuple[str, str]:
        """Return the current X/Y axis titles."""
        return self._x_axis_label, self._y_axis_label

    def _current_view(self) -> tuple[float, float, float, float]:
        return (
            self.view_xmin,
            self.view_xmax,
            self.view_ymin,
            self.view_ymax,
        )

    def _view_for_current_aspect(
        self,
        bounds: tuple[float, float, float, float],
    ) -> tuple[float, float, float, float]:
        if not self._equal_aspect:
            return bounds
        return self._equalized_bounds(bounds)

    def _equalized_bounds(
        self,
        bounds: tuple[float, float, float, float],
    ) -> tuple[float, float, float, float]:
        xmin, xmax, ymin, ymax = bounds
        left, right, top, bottom = self.get_plot_rect(self.width(), self.height())
        plot_width = max(1.0, right - left)
        plot_height = max(1.0, bottom - top)
        units_per_pixel = max(
            (xmax - xmin) / plot_width,
            (ymax - ymin) / plot_height,
        )
        center_x = (xmin + xmax) / 2.0
        center_y = (ymin + ymax) / 2.0
        half_width = units_per_pixel * plot_width / 2.0
        half_height = units_per_pixel * plot_height / 2.0
        return (
            center_x - half_width,
            center_x + half_width,
            center_y - half_height,
            center_y + half_height,
        )

    def _apply_view(
        self,
        bounds: tuple[float, float, float, float],
    ) -> None:
        self._invalidate_hover()
        (
            self.view_xmin,
            self.view_xmax,
            self.view_ymin,
            self.view_ymax,
        ) = bounds
        self.view_changed.emit(
            self.view_xmin,
            self.view_xmax,
            self.view_ymin,
            self.view_ymax,
        )
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
        
        if x_range == 0:
            x_range = 1.0
        if y_range == 0:
            y_range = 1.0
        
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
        
        if plot_w == 0:
            plot_w = 1.0
        if plot_h == 0:
            plot_h = 1.0
        
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

        self._invalidate_hover()
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

        self._invalidate_hover()
        self.view_xmin = cx - (cx - self.view_xmin) / factor
        self.view_xmax = cx + (self.view_xmax - cx) / factor
        self.view_ymin = cy - (cy - self.view_ymin) / factor
        self.view_ymax = cy + (self.view_ymax - cy) / factor
        
        self.view_changed.emit(self.view_xmin, self.view_xmax, self.view_ymin, self.view_ymax)
        self.update()

    # Inter-page data linking highlight methods
    def set_selected_point(
        self,
        series_name: str,
        index: int,
        *,
        label: str = "",
    ) -> None:
        """Select one plotted point and optionally render its caller label."""
        series = next(
            (item for item in self.series_list if item.name == series_name),
            None,
        )
        if series is None:
            raise ValueError(f"unknown series: {series_name}")
        if index < 0 or index >= len(series.x):
            raise IndexError(f"point index out of range: {index}")
        self.selected_point = (series_name, int(index))
        self.selected_label = str(label)
        self.update()

    def clear_selected_point(self) -> None:
        """Clear the caller-owned selected point."""
        self.selected_point = None
        self.selected_label = ""
        self.update()

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
            self._press_pos = event.position()
            self._dragged_since_press = False
            
    def mouseMoveEvent(self, event):
        curr_pos = event.position()
        left, right, top, bottom = self.get_plot_rect(self.width(), self.height())
        
        # Panning
        if event.buttons() in (Qt.LeftButton, Qt.MiddleButton) and self.last_mouse_pos is not None:
            if self._press_pos is not None:
                drag_distance = (
                    abs(curr_pos.x() - self._press_pos.x())
                    + abs(curr_pos.y() - self._press_pos.y())
                )
                if drag_distance >= 4.0:
                    self._dragged_since_press = True
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
            self._clear_hovered_point()
            
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not self._dragged_since_press:
                hit = self.check_nearest_point(event.position())
                self._last_click_pos = event.position()
                self._last_click_hit = hit
                self._last_click_time = time.monotonic()
                if hit is not None:
                    series_name, index, x_value, y_value = hit
                    self.point_clicked.emit(
                        series_name,
                        int(index),
                        float(x_value),
                        float(y_value),
                    )
            else:
                self._clear_last_click()
        self.last_mouse_pos = None
        self._press_pos = None
        self._dragged_since_press = False

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
        if event.button() != Qt.LeftButton:
            return
        hit = self.check_nearest_point(event.position())
        previous_point_hit = self._double_click_started_on_point(event.position())
        self._clear_last_click()
        if hit is None and not previous_point_hit:
            self.reset_view()
            self.reset_requested.emit()

    def _double_click_started_on_point(self, position: QPointF) -> bool:
        if self._last_click_hit is None or self._last_click_pos is None:
            return False
        application = QApplication.instance()
        interval_seconds = (
            application.doubleClickInterval() / 1_000.0
            if application is not None
            else 0.5
        )
        elapsed = time.monotonic() - self._last_click_time
        distance = math.hypot(
            position.x() - self._last_click_pos.x(),
            position.y() - self._last_click_pos.y(),
        )
        return elapsed <= interval_seconds and distance < 4.0

    def _clear_last_click(self) -> None:
        self._last_click_pos = None
        self._last_click_hit = None
        self._last_click_time = 0.0

    def leaveEvent(self, event):
        self._invalidate_hover()
        super().leaveEvent(event)

    def resizeEvent(self, event):
        if self._equal_aspect and self._autofit_bounds is not None:
            current_view = self._current_view()
            previous_full_view = self._full_view_bounds
            self._full_view_bounds = self._equalized_bounds(
                self._autofit_bounds
            )
            if previous_full_view is None:
                self._apply_view(self._full_view_bounds)
            else:
                current_width = current_view[1] - current_view[0]
                current_height = current_view[3] - current_view[2]
                zoom_factor = max(
                    (previous_full_view[1] - previous_full_view[0])
                    / max(current_width, np.finfo(float).eps),
                    (previous_full_view[3] - previous_full_view[2])
                    / max(current_height, np.finfo(float).eps),
                )
                center_x = (current_view[0] + current_view[1]) / 2.0
                center_y = (current_view[2] + current_view[3]) / 2.0
                half_width = (
                    self._full_view_bounds[1] - self._full_view_bounds[0]
                ) / (2.0 * zoom_factor)
                half_height = (
                    self._full_view_bounds[3] - self._full_view_bounds[2]
                ) / (2.0 * zoom_factor)
                self._apply_view(
                    (
                        center_x - half_width,
                        center_x + half_width,
                        center_y - half_height,
                        center_y + half_height,
                    )
                )
        super().resizeEvent(event)

    def check_nearest_point(self, mouse_pos):
        """Return and emit the nearest hover point within the activation radius."""
        closest_dist = 15.0  # Activation radius in pixels
        closest_pt = None  # (series, index, x, y)
        
        if self._kdtree is not None and len(self._tree_indices):
            self._ensure_pixel_kdtree()
            _dists, idx = self._kdtree.query(
                [float(mouse_pos.x()), float(mouse_pos.y())],
                k=1,
                distance_upper_bound=closest_dist,
            )
            if np.isfinite(_dists) and int(idx) < len(self._tree_indices):
                idx = int(idx)
                series_i = int(
                    np.searchsorted(self._tree_offsets, idx, side="right") - 1
                )
                s_name = self._tree_names[series_i]
                local_idx = int(self._tree_indices[idx])
                x_val = float(self._tree_xy[idx, 0])
                y_val = float(self._tree_xy[idx, 1])
                closest_dist = float(_dists)
                closest_pt = (s_name, local_idx, x_val, y_val)
        else:
            left, right, top, bottom = self.get_plot_rect(self.width(), self.height())
            plot_w = max(right - left, 1.0)
            plot_h = max(bottom - top, 1.0)
            x_range = self.view_xmax - self.view_xmin or 1.0
            y_range = self.view_ymax - self.view_ymin or 1.0
            mx, my = float(mouse_pos.x()), float(mouse_pos.y())
            for s in self.series_list:
                if not s.visible or len(s.x) == 0:
                    continue
                mask = ~np.isnan(s.x) & ~np.isnan(s.y)
                if not np.any(mask):
                    continue
                sx = np.asarray(s.x[mask], dtype=np.float64)
                sy = np.asarray(s.y[mask], dtype=np.float64)
                indices = np.nonzero(mask)[0]
                px = left + (sx - self.view_xmin) / x_range * plot_w
                py = bottom - (sy - self.view_ymin) / y_range * plot_h
                dist = np.hypot(mx - px, my - py)
                j = int(np.argmin(dist))
                if dist[j] < closest_dist:
                    closest_dist = float(dist[j])
                    closest_pt = (
                        s.name,
                        int(indices[j]),
                        float(sx[j]),
                        float(sy[j]),
                    )
                    
        if closest_pt:
            s_name, idx, x_val, y_val = closest_pt
            if self.hovered_point != (s_name, idx):
                self.hovered_point = (s_name, idx)
                self.point_hovered.emit(
                    s_name,
                    int(idx),
                    float(x_val),
                    float(y_val),
                )
        else:
            self._clear_hovered_point()
        return closest_pt

    def _clear_hovered_point(self) -> None:
        if self.hovered_point is None:
            return
        self.hovered_point = None
        self.point_hover_cleared.emit()

    def _invalidate_hover(self) -> None:
        self.hover_pos = None
        self._clear_hovered_point()

    def _resolve_point(self, reference):
        if reference is None:
            return None
        series_name, index = reference
        series = next(
            (
                candidate
                for candidate in self.series_list
                if candidate.name == series_name
            ),
            None,
        )
        if series is None or not 0 <= index < len(series.x):
            return None
        return float(series.x[index]), float(series.y[index])

    def _draw_point_indicator(
        self,
        painter,
        to_pixel,
        reference,
        *,
        pen,
        brush,
        radii,
        label="",
    ):
        point = self._resolve_point(reference)
        if point is None:
            return
        px, py = to_pixel(*point)
        painter.save()
        painter.setPen(pen)
        painter.setBrush(brush)
        for radius in radii:
            painter.drawEllipse(QPointF(px, py), radius, radius)
        if label:
            painter.setFont(QFont("Arial", 9, QFont.Bold))
            painter.setPen(self.highlight_color)
            painter.drawText(QPointF(px + 16.0, py - 12.0), label)
        painter.restore()

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
        from PySide6.QtGui import QPageSize
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(filepath)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))

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
            if x_r == 0:
                x_r = 1.0
            if y_r == 0:
                y_r = 1.0
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
                
        # 4. Render Series Data (clipped so off-view strokes stay in the frame)
        painter.save()
        painter.setClipRect(QRectF(left, top, plot_w, plot_h))
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
                
                poly = QPolygonF()
                
                for x_val, y_val in zip(sx, sy):
                    if np.isnan(x_val) or np.isnan(y_val):
                        if len(poly) > 1:
                            painter.drawPolyline(poly)
                        poly.clear()
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

        painter.restore()

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
            lbl_txt = f"X: {format_tick(dx, x_step)}\nY: {format_tick(dy, y_step)}"
            
            painter.setFont(QFont("Monospace", 8))
            painter.setPen(self.text_color)
            painter.drawText(self.hover_pos.x() + 10, self.hover_pos.y() - 10, lbl_txt)
            painter.restore()
            
        # Draw nearest hover point highlight ring
        self._draw_point_indicator(
            painter,
            to_p,
            self.hovered_point,
            pen=QPen(self.highlight_color, 2, Qt.SolidLine),
            brush=Qt.NoBrush,
            radii=(9.0,),
        )

        # Draw caller-owned selected point and its label independently of hover.
        self._draw_point_indicator(
            painter,
            to_p,
            self.selected_point,
            pen=QPen(self.axis_color, 3, Qt.SolidLine),
            brush=QBrush(self.highlight_color),
            radii=(12.0,),
            label=self.selected_label,
        )

        # Draw external highlighted/linked points (from bidirectional Map/Well selection)
        for s_name, indices in self.highlighted_points.items():
            for idx in indices:
                self._draw_point_indicator(
                    painter,
                    to_p,
                    (s_name, idx),
                    pen=QPen(
                        self.highlight_color,
                        1.5,
                        Qt.SolidLine,
                    ),
                    brush=Qt.NoBrush,
                    radii=(6.0, 10.0),
                )

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
                label = format_tick(xt, x_step)
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
                label = format_tick(yt, y_step)
                lbl_w = font_metrics.horizontalAdvance(label)
                painter.setPen(self.text_color)
                painter.drawText(left - lbl_w - 10, py + font_metrics.height() / 4, label)
                painter.setPen(axis_pen)

        if self._x_axis_label:
            painter.setPen(self.text_color)
            label_width = font_metrics.horizontalAdvance(
                self._x_axis_label
            )
            painter.drawText(
                left + (plot_w - label_width) / 2.0,
                bottom + 42.0,
                self._x_axis_label,
            )
        if self._y_axis_label:
            painter.save()
            painter.setPen(self.text_color)
            label_width = font_metrics.horizontalAdvance(
                self._y_axis_label
            )
            painter.translate(16.0, top + (plot_h + label_width) / 2.0)
            painter.rotate(-90.0)
            painter.drawText(0.0, 0.0, self._y_axis_label)
            painter.restore()
                
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
