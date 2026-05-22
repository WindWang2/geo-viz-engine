"""PyInstaller build script for GeoViz Engine."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def build():
    print("=== Starting GeoViz Engine Build ===")

    # 1. Clean previous build and release directories
    dist_dir = ROOT / "dist"
    build_dir = ROOT / "build"
    release_dir = ROOT / "release"

    for path in [dist_dir, build_dir, release_dir]:
        if path.exists():
            print(f"Cleaning existing directory: {path}")
            shutil.rmtree(path, ignore_errors=True)

    # 2. Prepare PyInstaller command
    sep = os.path.pathsep
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "GeoVizEngine",
        "--console",
        "--noconfirm",
        
        # Application core assets
        "--add-data", f"{ROOT / 'src' / 'patterns'}{sep}src/patterns",
        "--add-data", f"{ROOT / 'src' / 'resources'}{sep}src/resources",
        "--add-data", f"{ROOT / 'src' / 'assets'}{sep}src/assets",
        "--add-data", f"{ROOT / 'src' / 'pages' / 'map' / 'assets'}{sep}src/pages/map/assets",
        
        # Package-specific assets
        "--add-data", f"{ROOT / 'packages' / 'geoviz_well_log' / 'geoviz_well_log' / 'web_dist'}{sep}geoviz_well_log/web_dist",
        "--add-data", f"{ROOT / 'packages' / 'geoviz_well_log' / 'geoviz_well_log' / 'assets' / 'patterns'}{sep}geoviz_well_log/assets/patterns",
        
        # Hidden imports
        "--hidden-import", "PySide6.QtWebEngineWidgets",
        "--hidden-import", "PySide6.QtWebChannel",
        "--hidden-import", "shiboken6",
        "--hidden-import", "pydantic",
        
        str(ROOT / "src" / "main.py"),
    ]

    print(f"Running PyInstaller command: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    print("PyInstaller build completed successfully!")

    # 3. Setup standalone release folder
    print("=== Constructing Standalone Release Folder ===")
    app_release_dir = release_dir / "GeoVizEngine"
    app_release_dir.mkdir(parents=True, exist_ok=True)

    # Copy PyInstaller distribution output to release folder
    pyinstaller_output = dist_dir / "GeoVizEngine"
    if pyinstaller_output.exists():
        print(f"Copying executable distribution from {pyinstaller_output} to {app_release_dir}")
        shutil.copytree(pyinstaller_output, app_release_dir, dirs_exist_ok=True)
    else:
        raise RuntimeError("PyInstaller build finished but output directory was not found!")

    # Copy data directory directly next to the executable
    src_data_dir = ROOT / "data"
    dest_data_dir = app_release_dir / "data"
    if src_data_dir.exists():
        print(f"Copying data directory from {src_data_dir} to {dest_data_dir}")
        
        # Custom copy function to ignore temporary or cached files
        def ignore_patterns(path, names):
            return [name for name in names if name.startswith(('.', '__')) or name.endswith('.log')]
            
        shutil.copytree(src_data_dir, dest_data_dir, ignore=ignore_patterns, dirs_exist_ok=True)
    else:
        print("Warning: Source data directory was not found at root! Dynamic data folder is empty.")

    print("\n=== Release Build Success ===")
    print(f"The double-clickable program is available at: {app_release_dir / 'GeoVizEngine.exe'}")
    print(f"Full standalone package resides in: {app_release_dir.resolve()}")


if __name__ == "__main__":
    build()
