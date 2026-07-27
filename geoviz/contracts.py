from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class PreviewKind(StrEnum):
    WELL_LOG = "well_log"
    SEISMIC_2D = "seismic_2d"
    XY_SCATTER = "xy_scatter"
    FORMATION_TOPS = "formation_tops"
    SURFACE = "surface"
    TIME_DEPTH = "time_depth"


@dataclass(frozen=True)
class PreviewRequest:
    resource_id: str
    path: str
    semantic_type: str
    format: str
    label: str = ""
    source_version: str = ""
    source_crs: str = ""
    coordinate_units: str = ""
    comparison_crs: str = ""

    @property
    def normalized_format(self) -> str:
        return self.format.strip().lower().lstrip(".") or Path(self.path).suffix.lower().lstrip(".")


@dataclass(frozen=True)
class PreviewOptions:
    profile: str = "local"
    max_curves: int = 12
    max_depth_samples: int = 2_000
    max_slice_axis: int = 512
    max_points: int = 50_000
    surface_grid_size: int = 256

    @classmethod
    def local(cls) -> "PreviewOptions":
        return cls()


@dataclass(frozen=True)
class PreviewCapabilities:
    kind: PreviewKind
    interactions: tuple[str, ...] = ()
    optional_dependency: str = ""


@dataclass(frozen=True)
class PreparedPreview:
    kind: PreviewKind
    title: str
    payload: object
    summary_rows: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    warning: str = ""
    estimated_bytes: int = 0
