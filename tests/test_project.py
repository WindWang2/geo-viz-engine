import os
import tempfile
import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from src.data.project import (
    ProjectSchema, ProjectMeta, ProjectWell, ProjectSeismic,
    ProjectHorizon, ProjectPick, ProjectCorrelation, ProjectViewState,
    ProjectManager
)


def test_project_schema_validation():
    """Verify that ProjectSchema correctly validates field types and defaults."""
    # Test valid minimal project
    meta = ProjectMeta(created_at="2026-06-01T12:00:00", updated_at="2026-06-01T12:00:00")
    proj = ProjectSchema(meta=meta)
    assert proj.meta.name == "New Project"
    assert proj.meta.version == "0.8.0"
    assert len(proj.wells) == 0
    assert proj.seismic is None
    assert proj.view_state.active_page == 0

    # Test invalid field types raise ValidationError
    with pytest.raises(ValidationError):
        # name must be string, but latitude/longitude must be float
        ProjectWell(name="Well A", latitude="invalid", longitude=115.0)


def test_project_manager_save_and_load():
    """Verify that ProjectManager successfully serializes and deserializes a full project structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        proj_dir = Path(tmpdir)
        gvz_path = proj_dir / "test_project.gvz"

        # Define data files within project directory to test relative path conversion
        well_file = proj_dir / "data" / "HZ25.xlsx"
        well_file.parent.mkdir(parents=True, exist_ok=True)
        well_file.touch()

        seismic_file = proj_dir / "seismic" / "data.sgy"
        seismic_file.parent.mkdir(parents=True, exist_ok=True)
        seismic_file.touch()

        # Build full project state
        meta = ProjectMeta(
            name="Test Exploration",
            version="0.8.0",
            created_at="2026-06-01T12:00:00",
            updated_at="2026-06-01T12:30:00"
        )
        wells = [
            ProjectWell(name="HZ25", latitude=20.5, longitude=115.2, file_path=str(well_file))
        ]
        seismic = ProjectSeismic(
            file_path=str(seismic_file),
            origin=(100.0, 200.0, 0.0),
            spacing=(10.0, 10.0, 4.0)
        )
        horizons = [
            ProjectHorizon(name="H1", file_path="horizons/h1.txt")
        ]
        picks = [
            ProjectPick(well_name="HZ25", depth=1250.5, formation="Laolong")
        ]
        correlations = [
            ProjectCorrelation(
                source_well="HZ25",
                target_well="HZ26",
                source_depth=1250.5,
                target_depth=1270.0,
                formation="Laolong"
            )
        ]
        view_state = ProjectViewState(
            active_page=2,
            seismic_slice_positions={"inline": 15, "crossline": 20, "time": 120},
            seismic_colormap="jet",
            seismic_render_mode="volume"
        )

        project_data = ProjectSchema(
            meta=meta,
            wells=wells,
            seismic=seismic,
            horizons=horizons,
            picks=picks,
            correlations=correlations,
            view_state=view_state
        )

        manager = ProjectManager(gvz_path)

        # 1. Save project
        manager.save_project(project_data)
        assert gvz_path.exists()

        # Verify on-disk JSON uses relative paths
        with open(gvz_path, "r", encoding="utf-8") as f:
            disk_json = json.load(f)
            # The absolute path should be converted to relative path
            assert disk_json["wells"][0]["file_path"] == "data/HZ25.xlsx"
            assert disk_json["seismic"]["file_path"] == "seismic/data.sgy"

        # 2. Load project
        loaded_proj = manager.load_project()
        
        # Verify round-trip content matching
        assert loaded_proj.meta.name == "Test Exploration"
        assert loaded_proj.meta.version == "0.8.0"
        
        # Paths should be automatically expanded back to absolute paths on load
        assert loaded_proj.wells[0].file_path == str(well_file)
        assert loaded_proj.seismic.file_path == str(seismic_file)
        
        # Check other fields
        assert loaded_proj.horizons[0].name == "H1"
        assert loaded_proj.picks[0].depth == 1250.5
        assert loaded_proj.correlations[0].formation == "Laolong"
        assert loaded_proj.view_state.active_page == 2
        assert loaded_proj.view_state.seismic_slice_positions["inline"] == 15
        assert loaded_proj.view_state.seismic_colormap == "jet"
        assert loaded_proj.view_state.seismic_render_mode == "volume"
