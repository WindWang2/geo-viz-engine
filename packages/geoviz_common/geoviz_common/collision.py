"""CollisionDetector — spatial-hash rectangle collision grid for labels.

Shared verbatim by geoviz_map and geoviz_paleo_map (label placement).
"""
import math

from PySide6.QtCore import QRectF


def _rect_is_finite(rect: QRectF) -> bool:
    return (
        math.isfinite(rect.left())
        and math.isfinite(rect.right())
        and math.isfinite(rect.top())
        and math.isfinite(rect.bottom())
    )


class CollisionDetector:
    """Spatial-hash grid: ``try_add`` succeeds only when ``rect`` does not
    intersect any already-added rect (optionally expanded by ``margin``)."""

    # #146: a finite-but-huge rect (projection blow-up: ±1e9 with a 120 px
    # cell) spans ~1e14 cells and hangs the UI thread in the generator. A
    # rect covering more than this many cells is treated as "collides with
    # everything" and rejected in O(1).
    MAX_COVERED_CELLS = 4096

    def __init__(self, margin: float = 0.0, cell_size: float = 120.0):
        self._grid: dict[tuple[int, int], list[QRectF]] = {}
        self._margin = margin
        self._cell_size = max(1.0, float(cell_size))

    def _covered_cell_count(self, rect: QRectF) -> int:
        x1 = int(rect.left() // self._cell_size)
        x2 = int(rect.right() // self._cell_size)
        y1 = int(rect.top() // self._cell_size)
        y2 = int(rect.bottom() // self._cell_size)
        return (x2 - x1 + 1) * (y2 - y1 + 1)

    def _get_cells(self, rect: QRectF):
        if not _rect_is_finite(rect):
            return
        # Grid indices
        x1 = int(rect.left() // self._cell_size)
        x2 = int(rect.right() // self._cell_size)
        y1 = int(rect.top() // self._cell_size)
        y2 = int(rect.bottom() // self._cell_size)
        for x in range(x1, x2 + 1):
            for y in range(y1, y2 + 1):
                yield (x, y)

    def try_add(self, rect: QRectF) -> bool:
        if self._margin > 0:
            test_rect = rect.adjusted(-self._margin, -self._margin, self._margin, self._margin)
        else:
            test_rect = rect
        if not _rect_is_finite(test_rect):
            return False
        # #146: O(1) reject before the grid walk — a label-sized rect never
        # legitimately covers thousands of cells.
        if self._covered_cell_count(test_rect) > self.MAX_COVERED_CELLS:
            return False

        # Spatial Hash lookup
        for cell in self._get_cells(test_rect):
            if cell in self._grid:
                for existing in self._grid[cell]:
                    if existing.intersects(test_rect):
                        return False

        # Add to all covered cells
        for cell in self._get_cells(test_rect):
            self._grid.setdefault(cell, []).append(test_rect)

        return True

    def clear(self):
        self._grid.clear()
