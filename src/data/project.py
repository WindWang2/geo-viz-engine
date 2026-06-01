import json
from pathlib import Path
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class ProjectMeta(BaseModel):
    name: str = "New Project"
    version: str = "0.8.0"
    created_at: str
    updated_at: str


class ProjectWell(BaseModel):
    name: str
    latitude: float
    longitude: float
    file_path: Optional[str] = None


class ProjectSeismic(BaseModel):
    file_path: Optional[str] = None
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0)
    spacing: tuple[float, float, float] = (1.0, 1.0, 1.0)


class ProjectHorizon(BaseModel):
    name: str
    file_path: str


class ProjectPick(BaseModel):
    well_name: str
    depth: float
    formation: str


class ProjectCorrelation(BaseModel):
    source_well: str
    target_well: str
    source_depth: float
    target_depth: float
    formation: str


class ProjectViewState(BaseModel):
    active_page: int = 0
    seismic_slice_positions: dict[str, int] = {"inline": 0, "crossline": 0, "time": 0}
    seismic_colormap: str = "seismic"
    seismic_render_mode: str = "planes"


class ProjectSchema(BaseModel):
    meta: ProjectMeta
    wells: list[ProjectWell] = []
    seismic: Optional[ProjectSeismic] = None
    horizons: list[ProjectHorizon] = []
    picks: list[ProjectPick] = []
    correlations: list[ProjectCorrelation] = []
    view_state: ProjectViewState = ProjectViewState()


class ProjectManager:
    """Manages serialization, deserialization, and state conversion for .gvz project files."""

    def __init__(self, project_path: str | Path):
        self.project_path = Path(project_path)

    def _relativize_path(self, path_str: str | None) -> str | None:
        """Convert an absolute path to a relative path if it is under the project folder."""
        if not path_str:
            return None
        try:
            path = Path(path_str).resolve()
            proj_dir = self.project_path.parent.resolve()
            if path.is_relative_to(proj_dir):
                # Using as_posix() to ensure forward slashes across all platforms
                return path.relative_to(proj_dir).as_posix()
        except Exception:
            pass
        return path_str

    def _expand_path(self, path_str: str | None) -> str | None:
        """Convert a relative path back to an absolute path based on the project directory."""
        if not path_str:
            return None
        try:
            path = Path(path_str)
            if path.is_absolute():
                return path_str
            proj_dir = self.project_path.parent.resolve()
            return (proj_dir / path).resolve().absolute().as_posix()
        except Exception:
            pass
        return path_str

    def save_project(self, project_data: ProjectSchema):
        """Save the project data to the .gvz JSON file, convert absolute paths to relative where possible."""
        # Dump to dict (compatible with both pydantic v1 and v2)
        if hasattr(project_data, "model_dump"):
            data_dict = project_data.model_dump()
        else:
            data_dict = json.loads(project_data.json())

        # 1. Relativize well file paths
        for well in data_dict.get("wells", []):
            if well.get("file_path"):
                well["file_path"] = self._relativize_path(well["file_path"])

        # 2. Relativize seismic file path
        seismic = data_dict.get("seismic")
        if seismic and seismic.get("file_path"):
            seismic["file_path"] = self._relativize_path(seismic["file_path"])

        # 3. Relativize horizon file paths
        for horizon in data_dict.get("horizons", []):
            if horizon.get("file_path"):
                horizon["file_path"] = self._relativize_path(horizon["file_path"])

        # Ensure parent directory exists
        self.project_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to disk
        with open(self.project_path, "w", encoding="utf-8") as f:
            json.dump(data_dict, f, indent=4, ensure_ascii=False)

    def load_project(self) -> ProjectSchema:
        """Load project data from the .gvz JSON file, expanding relative paths to absolute."""
        if not self.project_path.exists():
            raise FileNotFoundError(f"Project file not found: {self.project_path}")

        with open(self.project_path, "r", encoding="utf-8") as f:
            data_dict = json.load(f)

        # 1. Expand well file paths
        for well in data_dict.get("wells", []):
            if well.get("file_path"):
                well["file_path"] = self._expand_path(well["file_path"])

        # 2. Expand seismic file path
        seismic = data_dict.get("seismic")
        if seismic and seismic.get("file_path"):
            seismic["file_path"] = self._expand_path(seismic["file_path"])

        # 3. Expand horizon file paths
        for horizon in data_dict.get("horizons", []):
            if horizon.get("file_path"):
                horizon["file_path"] = self._expand_path(horizon["file_path"])

        # Parse dict back to schema (compatible with both pydantic v1 and v2)
        if hasattr(ProjectSchema, "model_validate"):
            return ProjectSchema.model_validate(data_dict)
        elif hasattr(ProjectSchema, "parse_obj"):
            return ProjectSchema.parse_obj(data_dict)
        else:
            return ProjectSchema(**data_dict)
