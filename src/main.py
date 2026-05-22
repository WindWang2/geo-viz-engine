import sys
import os

# Ensure the project root is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# ---------------------------------------------------------------------------
# DLL Directory Registration for PySide6 inside PyInstaller frozen environment
# ---------------------------------------------------------------------------
if getattr(sys, 'frozen', False) and sys.platform == 'win32' and hasattr(os, 'add_dll_directory'):
    from pathlib import Path

    base_dirs = []
    if hasattr(sys, '_MEIPASS'):
        base_dirs.append(Path(sys._MEIPASS))
    else:
        print("DEBUG: sys._MEIPASS is NOT set!", file=sys.stderr)

    exe_dir = Path(sys.executable).parent
    base_dirs.append(exe_dir)
    base_dirs.append(exe_dir / "_internal")

    print(f"DEBUG: base_dirs to search: {base_dirs}", file=sys.stderr)

    for base_dir in base_dirs:
        if base_dir.exists():
            try:
                os.add_dll_directory(str(base_dir))
                print(f"DEBUG: Added DLL directory: {base_dir}", file=sys.stderr)
            except Exception as e:
                print(f"DEBUG: Failed to add DLL directory {base_dir}: {e}", file=sys.stderr)
            for sub in ["PySide6", "shiboken6"]:
                sub_dir = base_dir / sub
                if sub_dir.exists():
                    try:
                        os.add_dll_directory(str(sub_dir))
                        print(f"DEBUG: Added DLL directory: {sub_dir}", file=sys.stderr)
                    except Exception as e:
                        print(f"DEBUG: Failed to add DLL directory {sub_dir}: {e}", file=sys.stderr)

    # Also add them to PATH as a fallback
    os.environ["PATH"] = str(exe_dir / "_internal" / "PySide6") + os.pathsep + os.environ["PATH"]
    os.environ["PATH"] = str(exe_dir / "_internal" / "shiboken6") + os.pathsep + os.environ["PATH"]
    os.environ["PATH"] = str(exe_dir / "_internal") + os.pathsep + os.environ["PATH"]
    print(f"DEBUG: Final PATH starts with: {os.environ['PATH'][:200]}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Windows: Chromium GPU compositing flags (MUST be before any Qt import)
# ---------------------------------------------------------------------------
# On Windows, QWebEngineView (Chromium) and pyqtgraph.opengl (QOpenGLWidget)
# compete for the GPU context.  Setting --disable-gpu-compositing forces
# Chromium to use software compositing, avoiding the conflict while keeping
# WebGL functional for map rendering.
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    _flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    if "--disable-gpu-compositing" not in _flags:
        _flags += " --disable-gpu-compositing"
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = _flags.strip()

    # Lightweight GPU diagnostics (stderr only)
    try:
        import subprocess
        gpu_info = subprocess.run(
            ["wmic", "path", "win32_VideoController", "get", "name"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        print(f"[GeoViz] GPU: {gpu_info}", file=sys.stderr)
        print(f"[GeoViz] Chromium flags: {os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', '(none)')}", file=sys.stderr)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Critical: OpenGL + QWebEngineView coexistence on Windows
# ---------------------------------------------------------------------------
# 1. AA_ShareOpenGLContexts — allows OpenGL contexts to be shared between
#    QOpenGLWidget (pyqtgraph) and Chromium's GPU process.
# 2. QQuickWindow.setGraphicsApi(OpenGL) — forces Qt Quick RHI to OpenGL
#    (instead of Direct3D/Vulkan default on Windows).
# 3. CompatibilityProfile — includes legacy GL functions that Chromium's
#    GLES emulation layer depends on.
# ---------------------------------------------------------------------------
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

try:
    from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.OpenGL)
except ImportError:
    pass

from PySide6.QtGui import QFont, QSurfaceFormat
from src.app import MainWindow


def main():
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)
    fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)

    font = QFont()
    font.setFamilies(["Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "Segoe UI", "Arial"])
    font.setPointSize(10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferMatch)
    app.setFont(font)

    app.setStyleSheet("""
        QWidget { background: #ffffff; color: #1a202c; }
        QGroupBox { border: 1px solid #cbd5e0; border-radius: 4px; margin-top: 8px; padding-top: 16px; }
        QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
        QPushButton { background: #edf2f7; border: 1px solid #cbd5e0; border-radius: 4px; padding: 6px 16px; color: #1a202c; }
        QPushButton:hover { background: #e2e8f0; }
        QPushButton:pressed { background: #cbd5e0; }
        QTableWidget { background: #ffffff; gridline-color: #e2e8f0; border: 1px solid #e2e8f0; }
        QHeaderView::section { background: #f7fafc; border: 1px solid #e2e8f0; padding: 4px; }
        QScrollBar:vertical { background: #f7fafc; width: 10px; }
        QScrollBar::handle:vertical { background: #cbd5e0; border-radius: 5px; }
        QScrollArea { border: none; }
    """)
    app.setApplicationName("GeoViz Engine")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
