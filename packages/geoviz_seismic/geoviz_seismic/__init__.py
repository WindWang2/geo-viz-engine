"""geoviz-seismic — 3D seismic volume visualization + 2D profile display for PySide6.

Independent package providing SEGY loading, PyVista 3D rendering,
VD heatmap / Wiggle trace 2D profiles, horizon parsing, and LRU slice caching.
Works in any PySide6 project: ``pip install geoviz-seismic``.
"""

from .cache import SeismicCache
from .colormap import ColormapManager
from .horizon import HorizonParser, HorizonAxes
from .loader import SeismicLoader
from .models import SeismicVolumeMeta, SliceInfo, HorizonData
from .profile_vd import ProfileVD
from .profile_wiggle import ProfileWiggle
from .profile_widget import ProfileWidget
from .renderer_3d import Renderer3D
from .seismic_view import SeismicView

__version__ = "0.1.2"

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
    "SeismicVolumeMeta",
    "SliceInfo",
    "HorizonData",
]
