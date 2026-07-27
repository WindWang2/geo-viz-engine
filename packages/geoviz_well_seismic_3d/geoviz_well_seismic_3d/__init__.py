"""geoviz_well_seismic_3d — joint well–seismic 3D scene and widget."""

from __future__ import annotations

from .depth_transform import (
    ConstantVelocityDepth,
    DepthTransformKind,
    DepthTransformState,
    select_depth_transform,
)
from .fence import FenceExtraction, FenceSection, extract_fence_strip, well_to_well_path
from .models import (
    JointWellId,
    TimeDepthTable,
    VerticalDomain,
    WellHead,
    WellTrajectory3D,
)
from .probe import ProbeState, probe_from_fence_s
from .registration import VolumeRegistration
from .scene import JointWellPresentation, ProfileWellHit, WellSeismicScene
from .segy_survey import (
    align_horizon_corners_to_loader_axes,
    horizon_corners_from_dat,
    survey_corners_from_segy,
)
from .survey import SurveySpec, survey_from_corners
from .volume_access import InMemoryVolumeAccess, VolumeAccess

__version__ = "0.1.0"

__all__ = [
    "ConstantVelocityDepth",
    "DepthTransformKind",
    "DepthTransformState",
    "FenceExtraction",
    "FenceSection",
    "InMemoryVolumeAccess",
    "JointWellPresentation",
    "JointWellId",
    "ProbeState",
    "ProfileWellHit",
    "SurveySpec",
    "TimeDepthTable",
    "VerticalDomain",
    "VolumeAccess",
    "VolumeRegistration",
    "WellHead",
    "WellSeismicScene",
    "WellTrajectory3D",
    "extract_fence_strip",
    "align_horizon_corners_to_loader_axes",
    "horizon_corners_from_dat",
    "probe_from_fence_s",
    "select_depth_transform",
    "survey_corners_from_segy",
    "survey_from_corners",
    "well_to_well_path",
]


def __getattr__(name: str):
    """Lazy export for optional Qt-heavy widget."""
    if name == "WellSeismicJointWidget":
        from .joint_widget import WellSeismicJointWidget

        return WellSeismicJointWidget
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
