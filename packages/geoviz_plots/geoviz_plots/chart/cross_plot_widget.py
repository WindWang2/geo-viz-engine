"""QPainter-based interactive 2D scatter cross-plot widget with polygon lasso and SciPy convex hull."""
from __future__ import annotations
from typing import Optional, List, Tuple
import numpy as np

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QImage, QPainter, QPen, QColor, QFont, QBrush, QPolygonF

from geoviz_plots.chart.convex_hull import point_in_polygon_mask, compute_convex_hull

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

    @staticmethod
    def _blit_scatter_points(painter: QPainter, px, py, width: int, height: int) -> None:
        """Stamp in-view samples into one QImage (3×3 neighbourhood)."""
        arr = np.zeros((height, width, 4), dtype=np.uint8)
        ix = np.rint(px).astype(np.int32)
        iy = np.rint(py).astype(np.int32)
        color = np.asarray(_SCATTER_RGBA, dtype=np.uint8)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                xx = ix + dx
                yy = iy + dy
                ok = (xx >= 0) & (xx < width) & (yy >= 0) & (yy < height)
                arr[yy[ok], xx[ok]] = color
        image = QImage(arr.data, width, height, 4 * width, QImage.Format.Format_RGBA8888)
        painter.drawImage(0, 0, image.copy())

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
            return

        x_span = max(1e-6, self.view_xmax - self.view_xmin)
        y_span = max(1e-6, self.view_ymax - self.view_ymin)

        # Map scatter points to pixels
        px = plot_rect.left() + (self.x_data - self.view_xmin) / x_span * plot_rect.width()
        py = plot_rect.bottom() - (self.y_data - self.view_ymin) / y_span * plot_rect.height()

        finite = np.isfinite(px) & np.isfinite(py)
        px = px[finite]
        py = py[finite]
        inside = (
            (px >= plot_rect.left())
            & (px <= plot_rect.right())
            & (py >= plot_rect.top())
            & (py <= plot_rect.bottom())
        )
        px = px[inside]
        py = py[inside]
        if len(px) <= _SCATTER_ELLIPSE_LIMIT:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(90, 175, 255)))
            for x_i, y_i in zip(px, py):
                painter.drawEllipse(QPointF(float(x_i), float(y_i)), 3.0, 3.0)
        else:
            self._blit_scatter_points(painter, px, py, W, H)

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
