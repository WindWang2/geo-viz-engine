"""PyInstaller build script for GeoViz Engine."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def build():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "GeoVizEngine",
        "--windowed",
        "--noconfirm",
        "--add-data", f"{ROOT / 'src' / 'patterns'}:src/patterns",
        "--add-data", f"{ROOT / 'data' / 'well_coordinates.json'}:data",
        "--hidden-import", "PySide6.QtWebEngineWidgets",
        "--hidden-import", "PySide6.QtWebChannel",
        "--hidden-import", "pyvistaqt",
        "--hidden-import", "vtkmodules",
        str(ROOT / "src" / "main.py"),
    ]
    subprocess.run(cmd, check=True)
    print(f"Build complete: dist/GeoVizEngine/")


if __name__ == "__main__":
    build()
