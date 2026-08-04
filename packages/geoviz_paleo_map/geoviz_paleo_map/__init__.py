"""geoviz_paleo_map — QPainter-based paleogeographic map visualization for PySide6."""
from geoviz_paleo_map.canvas import PaleoMapCanvas
from geoviz_paleo_map.hierarchy import FaciesHierarchy
from geoviz_paleo_map.layers.filled_contour import FilledContourLayer
from geoviz_paleo_map.floating_slider import FloatingScaleSlider
from geoviz_paleo_map.locked_panel import LockedObjectsPanel
from geoviz_paleo_map.topology import TopologyModel, TopologyBuilder
from geoviz_paleo_map.edit_engine import EditEngine
from geoviz_paleo_map.edit_commands import UndoManager
from geoviz_paleo_map.paint_scheduler import PaintScheduler, LayerPixmapCache
from geoviz_paleo_map.screen_path_cache import ScreenPathCache
from geoviz_paleo_map.save_export import export_vector_svg
from geoviz_paleo_map.export_professional import export_professional_figure

__all__ = [
    "PaleoMapCanvas", "FaciesHierarchy", "FilledContourLayer",
    "FloatingScaleSlider",
    "LockedObjectsPanel", "TopologyModel", "TopologyBuilder",
    "EditEngine", "UndoManager",
    "PaintScheduler", "LayerPixmapCache", "ScreenPathCache",
    "export_vector_svg", "export_professional_figure",
]


