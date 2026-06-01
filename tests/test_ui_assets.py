import os
import pytest
from src.utils.paths import get_resources_dir

def test_nav_icons_exist_and_are_svg():
    """Verify that the new Azurite navigation icons exist in the resources directory."""
    icon_dir = get_resources_dir() / "icons"
    
    expected_icons = [
        "map.svg",
        "paleo.svg",
        "well.svg",
        "cross.svg",
        "seismic.svg",
        "plots.svg",
        "data.svg",
        "tools.svg"
    ]
    
    for icon_name in expected_icons:
        icon_path = icon_dir / icon_name
        assert icon_path.exists(), f"Icon {icon_name} is missing from {icon_dir}"
        assert icon_path.suffix == ".svg"
        # Check if file is not empty
        assert os.path.getsize(icon_path) > 0

def test_ui_icons_directory_exists():
    """Verify that the UI action icons subdirectory exists."""
    ui_icon_dir = get_resources_dir() / "icons" / "ui"
    assert ui_icon_dir.exists()
    assert ui_icon_dir.is_dir()
