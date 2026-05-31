"""geoviz-seismic — 3D seismic volume visualization + 2D profile display for PySide6.

Independent package providing SEGY loading, pyqtgraph OpenGL 3D rendering,
VD heatmap / Wiggle trace 2D profiles, horizon parsing, and LRU slice caching.
Optional CuPy GPU acceleration for volume slicing and colormapping.
Works in any PySide6 project: ``pip install geoviz-seismic``.
"""

from .cache import SeismicCache
from .colormap import ColormapManager
from .horizon import HorizonParser, HorizonAxes, extract_along_horizon
from .loader import SeismicLoader
from .models import SeismicVolumeMeta, SliceInfo, HorizonData, BinGridGeometry
from .profile_vd import ProfileVD
from .profile_wiggle import ProfileWiggle
from .profile_widget import ProfileWidget
from .renderer_3d import Renderer3D
from .seismic_view import SeismicView
from . import attributes
from . import attribute_pipeline

__version__ = "0.4.0"

__all__ = [
    "ColormapManager",
    "HorizonAxes",
    "HorizonParser",
    "ProfileVD",
    "ProfileWiggle",
    "ProfileWidget",
    "Renderer3D",
    "SeismicCache",
    "SeismicLoader",
    "SeismicView",
    "BinGridGeometry",
    "SeismicVolumeMeta",
    "SliceInfo",
    "HorizonData",
    "attributes",
    "attribute_pipeline",
    "extract_along_horizon",
]
