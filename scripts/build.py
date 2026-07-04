"""PyInstaller build script for GeoViz Engine."""
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def build():
    print("=== Starting GeoViz Engine Build ===")

    dist_dir = ROOT / "dist"
    build_dir = ROOT / "build"
    release_dir = ROOT / "release"

    for path in [dist_dir, build_dir, release_dir]:
        if path.exists():
            print(f"Cleaning existing directory: {path}")
            shutil.rmtree(path, ignore_errors=True)

    sep = os.path.pathsep
    windowed = [] if os.environ.get("GEOVIZ_CONSOLE") else ["--windowed"]

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "GeoVizEngine",
        *windowed,
        "--noconfirm",
        "--add-data", f"{ROOT / 'src' / 'patterns'}{sep}src/patterns",
        "--add-data", f"{ROOT / 'src' / 'resources'}{sep}src/resources",
        "--add-data", f"{ROOT / 'src' / 'assets'}{sep}src/assets",
        "--add-data", f"{ROOT / 'src' / 'pages' / 'map' / 'assets'}{sep}src/pages/map/assets",
        "--add-data", f"{ROOT / 'packages' / 'geoviz_well_log' / 'geoviz_well_log' / 'web_dist'}{sep}geoviz_well_log/web_dist",
        "--add-data", f"{ROOT / 'packages' / 'geoviz_well_log' / 'geoviz_well_log' / 'assets' / 'patterns'}{sep}geoviz_well_log/assets/patterns",
        "--add-data", f"{ROOT / 'data'}{sep}data",
        "--add-data", f"{ROOT / 'samples'}{sep}samples",
        "--hidden-import", "PySide6.QtWebEngineWidgets",
        "--hidden-import", "PySide6.QtWebChannel",
        "--hidden-import", "shiboken6",
        "--hidden-import", "pydantic",
        "--hidden-import", "geoviz_common",
        "--hidden-import", "geoviz_map",
        "--hidden-import", "geoviz_paleo_map",
        "--hidden-import", "geoviz_well_log",
        "--hidden-import", "geoviz_seismic",
        "--hidden-import", "geoviz_cross_well",
        "--hidden-import", "geoviz_well_tie",
        "--hidden-import", "geoviz_plots",
        str(ROOT / "src" / "main.py"),
    ]

    print(f"Running PyInstaller command: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    print("PyInstaller build completed successfully!")

    print("=== Constructing Standalone Release Folder ===")
    app_release_dir = release_dir / "GeoVizEngine"
    app_release_dir.mkdir(parents=True, exist_ok=True)

    pyinstaller_output = dist_dir / "GeoVizEngine"
    if pyinstaller_output.exists():
        shutil.copytree(pyinstaller_output, app_release_dir, dirs_exist_ok=True)
    else:
        raise RuntimeError("PyInstaller build finished but output directory was not found!")

    src_data_dir = ROOT / "data"
    dest_data_dir = app_release_dir / "data"
    if src_data_dir.exists():
        def ignore_patterns(path, names):
            return [name for name in names if name.startswith(('.', '__')) or name.endswith('.log')]
        shutil.copytree(src_data_dir, dest_data_dir, ignore=ignore_patterns, dirs_exist_ok=True)

    exe_name = "GeoVizEngine.exe" if platform.system() == "Windows" else "GeoVizEngine"
    print("\n=== Release Build Success ===")
    print(f"Executable: {app_release_dir / exe_name}")
    print(f"Package: {app_release_dir.resolve()}")


if __name__ == "__main__":
    build()