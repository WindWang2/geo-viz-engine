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
# Critical: OpenGL + QWebEngineView coexistence on Windows
# ---------------------------------------------------------------------------
# Problem: pyqtgraph.opengl (GLViewWidget) requires an OpenGL context, while
#   QWebEngineView (Chromium) uses Qt Quick internally (QQuickWidget).  On
#   Windows, three things must be configured BEFORE QApplication is created:
#
#   1. AA_ShareOpenGLContexts — allows OpenGL contexts to be shared between
#      QOpenGLWidget (pyqtgraph) and QQuickWidget (Chromium).  Without this,
#      QWebEngineView gets a fatal "Failed to create shared context" error.
#
#   2. QQuickWindow.setGraphicsApi(OpenGL) — forces Qt Quick's RHI backend to
#      OpenGL (instead of Direct3D/Vulkan default on Windows).  Without this,
#      the RHI mismatch causes "OpenGL is not compatible with this QQuickWidget".
#
#   3. CompatibilityProfile instead of CoreProfile — CoreProfile strips legacy
#      GL functions that Chromium's GLES emulation layer depends on, causing
#      "Failed to create GLES3 context".  CompatibilityProfile includes all
#      OpenGL 3.3 features PLUS legacy functions, satisfying both pyqtgraph
#      and Chromium.
# ---------------------------------------------------------------------------

from PySide6.QtCore import Qt

# Step 1: Enable OpenGL context sharing (MUST be before QApplication)
Qt.AA_ShareOpenGLContexts  # verify attribute exists
from PySide6.QtWidgets import QApplication
QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

# Step 2: Force Qt Quick RHI to use OpenGL backend (MUST be before QApplication)
try:
    from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.OpenGL)
except ImportError:
    pass  # QtQuick not available — QWebEngineView may still work without this

from PySide6.QtGui import QFont, QSurfaceFormat
from src.app import MainWindow


def main():
    # Step 3: Set CompatibilityProfile as global default surface format
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
