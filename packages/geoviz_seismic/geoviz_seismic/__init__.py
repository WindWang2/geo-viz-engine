"""geoviz-seismic — 3D seismic volume visualization + 2D profile display for PySide6.

Independent package providing SEGY loading, pyqtgraph OpenGL 3D rendering,
VD heatmap / Wiggle trace 2D profiles, horizon parsing, and LRU slice caching.
Optional CuPy GPU acceleration for volume slicing and colormapping.
Works in any PySide6 project: ``pip install geoviz-seismic``.
"""

from .cache import SeismicCache
from .colormap import ColormapManager
from .crossplot import analyze_lithology_crossplot
from .horizon import HorizonParser, HorizonAxes, extract_along_horizon
from .loader import SeismicLoader
from .models import SeismicVolumeMeta, SliceInfo, HorizonData, BinGridGeometry
from .profile_vd import ProfileVD
from .profile_wiggle import ProfileWiggle
from .profile_widget import ProfileWidget
from .preview_widget import (
    SeismicAxisSpec,
    SeismicPreviewPayload,
    SeismicPreviewWidget,
    SeismicSlice,
)
from . import attributes
from . import attribute_pipeline
from .attributes import blend_rgba, fuse_rgb
from . import stratal
from .stratal import (
    build_proportional_surfaces,
    extract_stratal_slice,
    stratal_slice_volume,
    validate_horizon_pair,
)

__version__ = "0.4.0"

__all__ = [
    "ColormapManager",
    "HorizonAxes",
    "HorizonParser",
    "ProfileVD",
    "ProfileWiggle",
    "ProfileWidget",
    "SeismicAxisSpec",
    "SeismicPreviewPayload",
    "SeismicPreviewWidget",
    "SeismicSlice",
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
    "analyze_lithology_crossplot",
    "blend_rgba",
    "fuse_rgb",
    # Stratal / proportional slicing (pure-numpy engine core)
    "stratal",
    "build_proportional_surfaces",
    "extract_stratal_slice",
    "stratal_slice_volume",
    "validate_horizon_pair",
    # Qt/OpenGL — lazily imported so headless consumers can skip the GL stack.
    "ClippedGLMeshItem",
    "ClippedGLVolumeItem",
]


_LAZY_GL: dict[str, tuple[str, str]] = {
    "Renderer3D": (".renderer_3d", "Renderer3D"),
    "SeismicView": (".seismic_view", "SeismicView"),
    "ClippedGLMeshItem": (".gl_clipping", "ClippedGLMeshItem"),
    "ClippedGLVolumeItem": (".gl_clipping", "ClippedGLVolumeItem"),
}


def __getattr__(name: str):
    if name in _LAZY_GL:
        import importlib

        module_name, attr = _LAZY_GL[name]
        return getattr(importlib.import_module(module_name, __name__), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

