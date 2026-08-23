"""Data models for line and scatter chart series, and data downsampling utilities."""
import numpy as np
import math
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt

def lttb_downsample(x, y, threshold: int) -> tuple[np.ndarray, np.ndarray]:
    """Downsample (x, y) coordinates to `threshold` points using Largest-Triangle-Three-Buckets algorithm.
    
    Filters out NaNs prior to downsampling.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    
    # Filter out NaNs to ensure LTTB calculation is stable
    mask = ~np.isnan(x) & ~np.isnan(y)
    x = x[mask]
    y = y[mask]
    
    n_points = len(x)
    if threshold >= n_points or threshold <= 2:
        return x, y
        
    # Split data into buckets
    # Keep the first and last points as-is, so threshold - 2 buckets in between
    bucket_size = (n_points - 2) / (threshold - 2)
    
    # Pre-allocate results
    res_x = np.zeros(threshold)
    res_y = np.zeros(threshold)
    
    # First point
    res_x[0] = x[0]
    res_y[0] = y[0]
    
    # Last point
    res_x[-1] = x[-1]
    res_y[-1] = y[-1]
    
    # Index of the previously chosen point (starts at 0)
    a_idx = 0
    
    for i in range(threshold - 2):
        # Range of current bucket
        b_start = int(math.floor((i) * bucket_size)) + 1
        b_end = int(math.floor((i + 1) * bucket_size)) + 1
        b_end = min(b_end, n_points - 1)
        
        if b_start >= b_end:
            # Empty bucket, fallback
            res_x[i+1] = x[b_start]
            res_y[i+1] = y[b_start]
            a_idx = b_start
            continue
            
        # Range of next bucket
        next_b_start = int(math.floor((i + 1) * bucket_size)) + 1
        next_b_end = int(math.floor((i + 2) * bucket_size)) + 1
        next_b_end = min(next_b_end, n_points - 1)
        
        # Calculate the average of the next bucket
        if next_b_start < next_b_end:
            c_x = np.mean(x[next_b_start:next_b_end])
            c_y = np.mean(y[next_b_start:next_b_end])
        else:
            c_x = x[-1]
            c_y = y[-1]
            
        # Point A (previously chosen point)
        a_x = x[a_idx]
        a_y = y[a_idx]
        
        # Points in current bucket
        bx = x[b_start:b_end]
        by = y[b_start:b_end]
        
        # Triangle area formula (omitting constant factor 0.5)
        areas = np.abs(a_x * (by - c_y) + bx * (c_y - a_y) + c_x * (a_y - by))
        
        # Find index that maximizes area
        max_idx = np.argmax(areas)
        best_idx = b_start + max_idx
        
        res_x[i+1] = x[best_idx]
        res_y[i+1] = y[best_idx]
        a_idx = best_idx
        
    return res_x, res_y


class Series:
    """Base class for all chart series models."""
    def __init__(self, x=None, y=None, name: str = "", color=None, visible: bool = True):
        self.x = np.asarray(x, dtype=np.float64) if x is not None else np.array([], dtype=np.float64)
        self.y = np.asarray(y, dtype=np.float64) if y is not None else np.array([], dtype=np.float64)
        self.name = name
        self.visible = visible
        
        # elegant standard colors (e.g. elegant dark mode palette or standard blue)
        if color is None:
            self.color = QColor(64, 156, 255)  # Sleek blue
        elif isinstance(color, QColor):
            self.color = color
        else:
            self.color = QColor(color)

    def get_bounds(self) -> tuple[float, float, float, float]:
        """Return (xmin, xmax, ymin, ymax) ignoring non-finite samples."""
        if len(self.x) == 0 or len(self.y) == 0:
            return 0.0, 0.0, 0.0, 0.0
            
        mask = np.isfinite(self.x) & np.isfinite(self.y)
        fx = self.x[mask]
        fy = self.y[mask]
        
        if len(fx) == 0 or len(fy) == 0:
            return 0.0, 0.0, 0.0, 0.0
            
        return float(np.min(fx)), float(np.max(fx)), float(np.min(fy)), float(np.max(fy))


class LineSeries(Series):
    """Series for line plots (with optional markers)."""
    def __init__(self, x=None, y=None, name: str = "", color=None, 
                 width: float = 1.5, style: Qt.PenStyle = Qt.SolidLine, 
                 marker_size: float = 0.0, marker_style: str = "none", 
                 visible: bool = True):
        super().__init__(x, y, name, color, visible)
        self.width = width
        self.style = style
        self.marker_size = marker_size
        self.marker_style = marker_style  # "none", "circle", "square", "triangle", "cross"


class ScatterSeries(Series):
    """Series for scatter plots."""
    def __init__(self, x=None, y=None, name: str = "", color=None,
                 size: float = 6.0, marker_style: str = "circle",
                 visible: bool = True, labels=None):
        super().__init__(x, y, name, color, visible)
        self.size = size
        self.marker_style = marker_style  # "circle", "square", "triangle", "cross"
        # Optional per-point text labels aligned with x/y (e.g. well names);
        # rendered next to each marker while the series is not downsampled.
        self.labels = labels
