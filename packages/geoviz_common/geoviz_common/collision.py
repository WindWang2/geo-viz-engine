"""CollisionDetector — spatial-hash rectangle collision grid for labels.

Shared verbatim by geoviz_map and geoviz_paleo_map (label placement).
"""
from PySide6.QtCore import QRectF


class CollisionDetector:
    """Spatial-hash grid: ``try_add`` succeeds only when ``rect`` does not
    intersect any already-added rect (optionally expanded by ``margin``)."""

    def __init__(self, margin: float = 0.0, cell_size: float = 120.0):
        self._grid: dict[tuple[int, int], list[QRectF]] = {}
        self._margin = margin
        self._cell_size = cell_size

    def _get_cells(self, rect: QRectF):
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
