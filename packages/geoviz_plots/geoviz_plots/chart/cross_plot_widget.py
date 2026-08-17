"""QPainter-based interactive 2D scatter cross-plot widget with polygon lasso and SciPy convex hull."""
from __future__ import annotations
from typing import Optional, List, Tuple
import numpy as np

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QImage, QPainter, QPen, QColor, QFont, QBrush, QPolygonF

from geoviz_plots.chart.axes import calculate_ticks, format_tick
from geoviz_plots.chart.convex_hull import point_in_polygon_mask, compute_convex_hull
from geoviz_plots.surface.colormaps import COLORMAPS, sample_colormap

# Per-point QPainter ellipses stay readable for small clouds; larger sets
# are stamped into a QImage so paint stays O(N) numpy rather than N Python
# drawEllipse calls.
_SCATTER_ELLIPSE_LIMIT = 4000
_SCATTER_RGBA = (90, 175, 255, 255)


class CrossPlotWidget(QWidget):
    """Interactive 2D scatter cross-plot widget.

    Signals:
        points_selected: Emitted when points are selected via polygon lasso.
            Payload: (selected_indices_array, (xmin, xmax, ymin, ymax))
    """

    points_selected = Signal(object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self.x_data: Optional[np.ndarray] = None
        self.y_data: Optional[np.ndarray] = None
        self.z_data: Optional[np.ndarray] = None

        self.x_label = "X Axis"
        self.y_label = "Y Axis"
        self.z_label = "Z Axis"

        self.margin_left = 65
        self.margin_right = 75
        self.margin_top = 25
        self.margin_bottom = 50

        # Viewport boundaries
        self.view_xmin = 0.0
        self.view_xmax = 1.0
        self.view_ymin = 0.0
        self.view_ymax = 1.0

        # Lasso & Clusters
        self.lasso_active = False
        self.current_lasso_pts: List[QPointF] = []
        self.clusters: List[dict] = []  # List of {"hull": np.ndarray, "indices": np.ndarray, "color": QColor}

    def set_scatter_data(
        self,
        x: np.ndarray,
        y: np.ndarray,
        z: Optional[np.ndarray] = None,
        x_label: str = "X Axis",
        y_label: str = "Y Axis",
        z_label: str = "Z Axis",
    ):
        self.x_data = np.asarray(x, dtype=np.float64)
        self.y_data = np.asarray(y, dtype=np.float64)
        self.z_data = np.asarray(z, dtype=np.float64) if z is not None else None

        self.x_label = x_label
        self.y_label = y_label
        self.z_label = z_label

        if len(self.x_data) > 0:
            # A single NaN sample must not poison the whole view bounds
            # (np.min/np.max return NaN, mapping every point off-canvas) —
            # mask non-finite samples like Series.get_bounds does (#553).
            finite = np.isfinite(self.x_data) & np.isfinite(self.y_data)
            if np.any(finite):
                self.view_xmin = float(np.min(self.x_data[finite]))
                self.view_xmax = float(np.max(self.x_data[finite]))
                self.view_ymin = float(np.min(self.y_data[finite]))
                self.view_ymax = float(np.max(self.y_data[finite]))

        self.clusters.clear()
        self.update()

    def apply_lasso_polygon(self, lasso_data_pts: List[QPointF]):
        if self.x_data is None or self.y_data is None or len(self.x_data) == 0:
            return

        poly_verts = [(p.x(), p.y()) for p in lasso_data_pts]
        mask = point_in_polygon_mask(self.x_data, self.y_data, poly_verts)
        indices = np.where(mask)[0]

        if len(indices) > 0:
            sel_x = self.x_data[indices]
            sel_y = self.y_data[indices]
            hull_pts = compute_convex_hull(sel_x, sel_y)

            cluster = {
                "name": f"Cluster_{len(self.clusters) + 1}",
                "hull": hull_pts,
                "indices": indices,
                "color": QColor(31, 102, 212, 50),
            }
            self.clusters.append(cluster)

            xmin, xmax = float(np.min(sel_x)), float(np.max(sel_x))
            ymin, ymax = float(np.min(sel_y)), float(np.max(sel_y))
            self.points_selected.emit(indices, (xmin, xmax, ymin, ymax))

        self.update()

    def _axis_captions(self) -> dict[str, str]:
        return {"x": self.x_label, "y": self.y_label, "z": self.z_label}

    def _z_range(self, z: np.ndarray) -> tuple[float, float]:
        finite = z[np.isfinite(z)]
        if finite.size == 0:
            return 0.0, 1.0
        return float(np.min(finite)), float(np.max(finite))

    def _z_qcolors(self, z: np.ndarray, colormap: str = "viridis") -> list[QColor]:
        vmin, vmax = self._z_range(np.asarray(z, dtype=np.float64))
        return [sample_colormap(colormap, float(v), vmin, vmax) for v in z]

    @staticmethod
    def _z_rgba_lut(z: np.ndarray, vmin: float, vmax: float, colormap: str = "viridis") -> np.ndarray:
        lut = np.zeros((256, 4), dtype=np.uint8)
        for i in range(256):
            c = sample_colormap(colormap, vmin + (vmax - vmin) * (i / 255.0), vmin, vmax)
            lut[i] = (c.red(), c.green(), c.blue(), 255)
        span = max(vmax - vmin, 1e-12)
        t = np.clip((z - vmin) / span, 0.0, 1.0)
        t = np.where(np.isfinite(z), t, 0.0)
        idx = np.rint(t * 255.0).astype(np.int32)
        return lut[idx]

    @staticmethod
    def _blit_scatter_points(painter: QPainter, px, py, width: int, height: int, rgba=None) -> None:
        """Stamp in-view samples into one QImage (3×3 neighbourhood)."""
        arr = np.zeros((height, width, 4), dtype=np.uint8)
        ix = np.rint(px).astype(np.int32)
        iy = np.rint(py).astype(np.int32)
        if rgba is None:
            color = np.asarray(_SCATTER_RGBA, dtype=np.uint8)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    xx = ix + dx
                    yy = iy + dy
                    ok = (xx >= 0) & (xx < width) & (yy >= 0) & (yy < height)
                    arr[yy[ok], xx[ok]] = color
        else:
            colors = np.asarray(rgba, dtype=np.uint8)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    xx = ix + dx
                    yy = iy + dy
                    ok = (xx >= 0) & (xx < width) & (yy >= 0) & (yy < height)
                    arr[yy[ok], xx[ok]] = colors[ok]
        image = QImage(arr.data, width, height, 4 * width, QImage.Format.Format_RGBA8888)
        painter.drawImage(0, 0, image.copy())

    def _draw_axes(self, painter: QPainter, plot_rect: QRectF) -> None:
        x_ticks, x_step = calculate_ticks(self.view_xmin, self.view_xmax, 6)
        y_ticks, y_step = calculate_ticks(self.view_ymin, self.view_ymax, 6)
        x_span = max(1e-6, self.view_xmax - self.view_xmin)
        y_span = max(1e-6, self.view_ymax - self.view_ymin)

        def to_p(x_val: float, y_val: float) -> tuple[float, float]:
            px = plot_rect.left() + (x_val - self.view_xmin) / x_span * plot_rect.width()
            py = plot_rect.bottom() - (y_val - self.view_ymin) / y_span * plot_rect.height()
            return px, py

        axis_pen = QPen(QColor(180, 180, 180), 1)
        grid_pen = QPen(QColor(50, 50, 50), 1, Qt.PenStyle.DashLine)
        painter.setFont(QFont("SansSerif", 8))
        metrics = painter.fontMetrics()
        text_color = QColor(210, 210, 210)

        painter.setPen(grid_pen)
        for xt in x_ticks:
            if self.view_xmin <= xt <= self.view_xmax:
                px, _ = to_p(xt, self.view_ymin)
                painter.drawLine(px, plot_rect.top(), px, plot_rect.bottom())
        for yt in y_ticks:
            if self.view_ymin <= yt <= self.view_ymax:
                _, py = to_p(self.view_xmin, yt)
                painter.drawLine(plot_rect.left(), py, plot_rect.right(), py)

        painter.setPen(axis_pen)
        for xt in x_ticks:
            if self.view_xmin <= xt <= self.view_xmax:
                px, _ = to_p(xt, self.view_ymin)
                painter.drawLine(px, plot_rect.bottom(), px, plot_rect.bottom() + 4)
                label = format_tick(xt, x_step)
                painter.setPen(text_color)
                painter.drawText(px - metrics.horizontalAdvance(label) / 2, plot_rect.bottom() + 16, label)
                painter.setPen(axis_pen)
        for yt in y_ticks:
            if self.view_ymin <= yt <= self.view_ymax:
                _, py = to_p(self.view_xmin, yt)
                painter.drawLine(plot_rect.left() - 4, py, plot_rect.left(), py)
                label = format_tick(yt, y_step)
                painter.setPen(text_color)
                painter.drawText(plot_rect.left() - metrics.horizontalAdvance(label) - 8, py + 4, label)
                painter.setPen(axis_pen)

        painter.setPen(text_color)
        if self.x_label:
            lw = metrics.horizontalAdvance(self.x_label)
            painter.drawText(plot_rect.center().x() - lw / 2, plot_rect.bottom() + 34, self.x_label)
        if self.y_label:
            painter.save()
            painter.translate(14, plot_rect.center().y() + metrics.horizontalAdvance(self.y_label) / 2)
            painter.rotate(-90)
            painter.drawText(0, 0, self.y_label)
            painter.restore()

    def _draw_z_colorbar(self, painter: QPainter, plot_rect: QRectF, vmin: float, vmax: float) -> None:
        from PySide6.QtGui import QLinearGradient

        bar = QRectF(plot_rect.right() + 10, plot_rect.top(), 12, plot_rect.height())
        grad = QLinearGradient(bar.left(), bar.bottom(), bar.left(), bar.top())
        for pos, col in COLORMAPS["viridis"]:
            grad.setColorAt(pos, col)
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(QColor(88, 104, 120), 1))
        painter.drawRect(bar)
        painter.setPen(QColor(210, 210, 210))
        painter.setFont(QFont("SansSerif", 8))
        metrics = painter.fontMetrics()
        for frac, val in ((0.0, vmin), (1.0, vmax)):
            py = bar.bottom() - frac * bar.height()
            label = f"{val:.1f}"
            painter.drawText(bar.right() + 4, py + metrics.height() / 4, label)
        if self.z_label:
            painter.save()
            painter.translate(bar.right() + 28, plot_rect.center().y() + metrics.horizontalAdvance(self.z_label) / 2)
            painter.rotate(-90)
            painter.drawText(0, 0, self.z_label)
            painter.restore()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        W, H = self.width(), self.height()
        painter.fillRect(0, 0, W, H, QColor(25, 25, 25))

        # Canvas bounds
        plot_rect = QRectF(self.margin_left, self.margin_top, W - self.margin_left - self.margin_right, H - self.margin_top - self.margin_bottom)
        painter.fillRect(plot_rect, QColor(15, 15, 15))
        painter.setPen(QPen(QColor(88, 104, 120), 1))
        painter.drawRect(plot_rect)

        if self.x_data is None or len(self.x_data) == 0:
            self._draw_axes(painter, plot_rect)
            return

        x_span = max(1e-6, self.view_xmax - self.view_xmin)
        y_span = max(1e-6, self.view_ymax - self.view_ymin)

        # Map scatter points to pixels
        px = plot_rect.left() + (self.x_data - self.view_xmin) / x_span * plot_rect.width()
        py = plot_rect.bottom() - (self.y_data - self.view_ymin) / y_span * plot_rect.height()

        finite = np.isfinite(px) & np.isfinite(py)
        px = px[finite]
        py = py[finite]
        z_view = None
        if self.z_data is not None and len(self.z_data) == len(finite):
            z_view = self.z_data[finite]
        inside = (
            (px >= plot_rect.left())
            & (px <= plot_rect.right())
            & (py >= plot_rect.top())
            & (py <= plot_rect.bottom())
        )
        px = px[inside]
        py = py[inside]
        if z_view is not None:
            z_view = z_view[inside]
        zmin = zmax = None
        rgba = None
        if z_view is not None and len(z_view) > 0:
            zmin, zmax = self._z_range(z_view)
            rgba = self._z_rgba_lut(z_view, zmin, zmax)
        if len(px) <= _SCATTER_ELLIPSE_LIMIT:
            painter.setPen(Qt.PenStyle.NoPen)
            if rgba is None:
                painter.setBrush(QBrush(QColor(90, 175, 255)))
                for x_i, y_i in zip(px, py):
                    painter.drawEllipse(QPointF(float(x_i), float(y_i)), 3.0, 3.0)
            else:
                for x_i, y_i, color in zip(px, py, rgba):
                    painter.setBrush(QBrush(QColor(int(color[0]), int(color[1]), int(color[2]))))
                    painter.drawEllipse(QPointF(float(x_i), float(y_i)), 3.0, 3.0)
        else:
            self._blit_scatter_points(painter, px, py, W, H, rgba)

        # Draw cluster convex hulls
        for c in self.clusters:
            hull = c["hull"]
            if len(hull) >= 3:
                h_px = plot_rect.left() + (hull[:, 0] - self.view_xmin) / x_span * plot_rect.width()
                h_py = plot_rect.bottom() - (hull[:, 1] - self.view_ymin) / y_span * plot_rect.height()

                poly = QPolygonF([QPointF(h_px[k], h_py[k]) for k in range(len(hull))])
                painter.setPen(QPen(QColor(31, 102, 212), 2))
                painter.setBrush(QBrush(c["color"]))
                painter.drawPolygon(poly)

        self._draw_axes(painter, plot_rect)
        if zmin is not None and zmax is not None:
            self._draw_z_colorbar(painter, plot_rect, zmin, zmax)
