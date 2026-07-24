"""geoviz_well_seismic_3d — joint well–seismic 3D scene and widget."""

from __future__ import annotations

from .models import (
    TimeDepthTable,
    VerticalDomain,
    WellHead,
    WellTrajectory3D,
)
from .scene import WellSeismicScene
from .survey import SurveySpec, survey_from_corners
from .volume_access import InMemoryVolumeAccess, VolumeAccess

__version__ = "0.1.0"

__all__ = [
    "InMemoryVolumeAccess",
    "SurveySpec",
    "TimeDepthTable",
    "VerticalDomain",
    "VolumeAccess",
    "WellHead",
    "WellSeismicScene",
    "WellTrajectory3D",
    "survey_from_corners",
]


def __getattr__(name: str):
    """Lazy export for optional Qt-heavy widget."""
    if name == "WellSeismicJointWidget":
        from .joint_widget import WellSeismicJointWidget

        return WellSeismicJointWidget
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
