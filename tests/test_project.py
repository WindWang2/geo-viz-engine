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


def test_expand_path_rejects_traversal(tmp_path):
    """Malicious relative paths must not escape the project directory."""
    proj_dir = tmp_path / "my_project"
    proj_dir.mkdir()
    gvz = proj_dir / "test.gvz"
    gvz.write_text('{"meta": {"name": "x", "created_at": "t", "updated_at": "t"}, "wells": []}')

    manager = ProjectManager(gvz)
    data = {
        "meta": {"name": "x", "created_at": "t", "updated_at": "t"},
        "wells": [{"name": "W1", "latitude": 1.0, "longitude": 2.0, "file_path": "../../../etc/passwd"}],
    }
    with open(gvz, "w") as f:
        json.dump(data, f)

    loaded = manager.load_project()
    assert loaded.wells[0].file_path is None


def test_project_roundtrip_preserves_outside_absolute_paths(tmp_path):
    """#509: data files outside the project folder are stored absolute on
    save and must survive the load round-trip — load used to null them via
    the traversal containment check, silently dropping every well/seismic
    that lived outside the project dir."""
    proj_dir = tmp_path / "proj"
    proj_dir.mkdir()
    gvz = proj_dir / "expl.gvz"

    outside_well = tmp_path / "datastore" / "HZ25.xlsx"
    outside_well.parent.mkdir(parents=True, exist_ok=True)
    outside_well.touch()
    outside_segy = tmp_path / "seismic_store" / "cube.sgy"
    outside_segy.parent.mkdir(parents=True, exist_ok=True)
    outside_segy.touch()

    wells = [ProjectWell(name="HZ25", latitude=20.5, longitude=115.2, file_path=str(outside_well))]
    seismic = ProjectSeismic(
        file_path=str(outside_segy), origin=(0.0, 0.0, 0.0), spacing=(10.0, 10.0, 4.0)
    )
    schema = ProjectSchema(
        meta=ProjectMeta(name="P", version="1", created_at="t", updated_at="t"),
        wells=wells,
        seismic=seismic,
    )

    ProjectManager(gvz).save_project(schema)

    # Stored verbatim as absolute (not nulled, not relativized).
    raw = json.loads(gvz.read_text(encoding="utf-8"))
    assert Path(raw["wells"][0]["file_path"]).is_absolute()
    assert Path(raw["seismic"]["file_path"]).is_absolute()

    loaded = ProjectManager(gvz).load_project()
    assert loaded.wells[0].file_path == outside_well.resolve().as_posix()
    assert loaded.seismic is not None
    assert loaded.seismic.file_path == outside_segy.resolve().as_posix()


def test_save_project_crash_midwrite_leaves_previous_version_intact(tmp_path, monkeypatch):
    """#574: a crash mid-dump must not destroy the only project file. The
    old in-place 'w' open truncated it first; now the payload streams to a
    temp sibling and the final file is only replaced atomically."""
    import src.data.project as project_mod

    gvz = tmp_path / "proj" / "expl.gvz"
    gvz.parent.mkdir(parents=True)
    manager = ProjectManager(gvz)

    schema1 = ProjectSchema(
        meta=ProjectMeta(name="first", version="1", created_at="t", updated_at="t"),
        wells=[ProjectWell(name="W1", latitude=1.0, longitude=2.0, file_path=None)],
    )
    manager.save_project(schema1)
    first_raw = gvz.read_text(encoding="utf-8")
    assert json.loads(first_raw)["meta"]["name"] == "first"

    schema2 = ProjectSchema(
        meta=ProjectMeta(name="second", version="1", created_at="t", updated_at="t"),
        wells=[ProjectWell(name="W2", latitude=1.0, longitude=2.0, file_path=None)],
    )

    real_dump = json.dump

    def exploding_dump(obj, fh, **kwargs):
        fh.write('{"meta": {"name": "second", "created')  # partial garbage
        raise RuntimeError("disk filled / process killed mid-dump")

    monkeypatch.setattr(project_mod.json, "dump", exploding_dump)
    try:
        manager.save_project(schema2)
        raise AssertionError("expected the injected save failure")
    except RuntimeError:
        pass

    # The previous version is intact and loadable; no temp litter remains.
    assert json.loads(gvz.read_text(encoding="utf-8"))["meta"]["name"] == "first"
    assert not (gvz.parent / "expl.gvz.tmp").exists()
    monkeypatch.setattr(project_mod.json, "dump", real_dump)

    # A subsequent successful save keeps the previous version as .bak.
    manager.save_project(schema2)
    assert json.loads(gvz.read_text(encoding="utf-8"))["meta"]["name"] == "second"
    bak = gvz.parent / "expl.gvz.bak"
    assert bak.exists()
    assert json.loads(bak.read_text(encoding="utf-8"))["meta"]["name"] == "first"
