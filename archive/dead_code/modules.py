from dataclasses import dataclass, field
from typing import Protocol


class LeafModule(Protocol):
    def sync_depth(self, top_m: float, bottom_m: float) -> None: ...
    def preferred_width(self) -> int: ...
    def set_pixel_density(self, px_per_m: float) -> None: ...


@dataclass
class CompositeModule:
    label: str
    children: list[LeafModule] = field(default_factory=list)
    width_override: int | None = None

    def sync_depth(self, top_m: float, bottom_m: float):
        for c in self.children:
            c.sync_depth(top_m, bottom_m)

    def set_pixel_density(self, px_per_m: float):
        for c in self.children:
            c.set_pixel_density(px_per_m)

    def preferred_width(self) -> int:
        if self.width_override is not None:
            return self.width_override
        return sum(c.preferred_width() for c in self.children)


@dataclass
class LayoutCoordinator:
    """
    master_vb: pg.ViewBox — the shared DEPTH-axis ViewBox used as the source of truth for y-range.
    modules: ordered list of LeafModule | CompositeModule — representing columns left-to-right.
    viewport_height: current scroll-area content height in pixels.
    """
    master_vb: object
    modules: list[LeafModule | CompositeModule] = field(default_factory=list)
    viewport_height: int = 0

    def fit_to_viewport(self):
        """
        Called on init and on resize. Computes px_per_m = viewport_height / depth_span,
        distributes to all modules via set_pixel_density(), then broadcasts full depth range via sync_depth().
        """
        import pyqtgraph as pg
        # Get full range from master ViewBox
        _, (vy_min, vy_max) = self.master_vb.viewRange()
        span = vy_max - vy_min
        if span <= 0:
            return
        px_per_m = self.viewport_height / span
        for mod in self.modules:
            mod.set_pixel_density(px_per_m)
        self._broadcast_range(vy_min, vy_max)

    def _broadcast_range(self, top_m: float, bottom_m: float):
        for mod in self.modules:
            mod.sync_depth(top_m, bottom_m)

    def on_master_range_changed(self, vb, y_range):
        """Connect to master's sigYRangeChanged signal."""
        self._broadcast_range(y_range[0], y_range[1])

    def on_resize(self, height: int):
        self.viewport_height = height
        self.fit_to_viewport()