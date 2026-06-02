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

from PySide6.QtGui import QFont, QSurfaceFormat, QPixmap
from PySide6.QtWidgets import QSplashScreen, QFrame, QVBoxLayout, QLabel
from PySide6.QtCore import QPropertyAnimation
from src.app import MainWindow


class BrandSplashScreen(QSplashScreen):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(450, 280)
        
        pixmap = QPixmap(450, 280)
        pixmap.fill(Qt.GlobalColor.transparent)
        self.setPixmap(pixmap)
        
        bg = QFrame(self)
        bg.setGeometry(0, 0, 450, 280)
        bg.setStyleSheet(
            "QFrame { background: #faf9f5; border: 1px solid #d3dbe6; border-radius: 12px; }"
        )
        
        layout = QVBoxLayout(bg)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        layout.addStretch()
        
        self.logo_lbl = QLabel()
        self.logo_lbl.setText('<span style="font-size: 32px; font-weight: bold; color: #1f66d4;">GeoViz</span> '
                              '<span style="font-size: 32px; font-weight: 300; color: #586878;">Engine</span>')
        self.logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_lbl.setStyleSheet("border: none; background: transparent;")
        layout.addWidget(self.logo_lbl)
        
        sub_lbl = QLabel("Azurite Design System · Desktop地质可视化引擎")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_lbl.setStyleSheet("color: #92a0b0; font-size: 12px; border: none; background: transparent;")
        layout.addWidget(sub_lbl)
        
        layout.addStretch()
        
        self.status_lbl = QLabel("正在加载地质数据模块...")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet("color: #586878; font-size: 11px; border: none; background: transparent;")
        layout.addWidget(self.status_lbl)


def main():
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)
    fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)

    from PySide6.QtGui import QIcon
    from src.utils.paths import get_resources_dir
    logo_path = str(get_resources_dir() / "icons" / "brand" / "geoviz-mark.svg")
    app.setWindowIcon(QIcon(logo_path))

    font = QFont()
    font.setFamilies(["Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "Segoe UI", "Arial"])
    font.setPointSize(10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferMatch)
    app.setFont(font)

    app.setStyleSheet("""
        QWidget { background: #faf9f5; color: #1a2433; font-family: "Microsoft YaHei", "Segoe UI", sans-serif; }
        
        QGroupBox { 
            border: 1px solid #e5eaf1; 
            border-radius: 12px; 
            margin-top: 12px; 
            padding-top: 16px; 
            font-weight: bold;
            background: #ffffff;
        }
        QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #1f66d4; }
        
        QPushButton { 
            background: #ffffff; 
            border: 1px solid #d3dbe6; 
            border-radius: 8px; 
            padding: 6px 12px; 
            color: #1a2433; 
            font-weight: 500;
        }
        QPushButton:hover { background: #f1f4f9; border-color: #1f66d4; color: #1f66d4; }
        QPushButton:pressed { background: #e9effa; }
        QPushButton:checked { background: #1f66d4; color: #ffffff; border-color: #1f66d4; }
        
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
            background: #ffffff;
            border: 1px solid #d3dbe6;
            border-radius: 6px;
            padding: 4px 8px;
            min-height: 24px;
            color: #1a2433;
        }
        QLineEdit:focus, QComboBox:focus { border-color: #1f66d4; }
        
        QTableWidget { 
            background: #ffffff; 
            gridline-color: #f1f4f9; 
            border: 1px solid #d3dbe6; 
            border-radius: 12px;
        }
        QHeaderView::section { 
            background: #fafbfd; 
            border: none;
            border-right: 1px solid #e5eaf1;
            border-bottom: 1px solid #e5eaf1;
            padding: 6px; 
            font-weight: bold;
            color: #586878;
        }
        
        QScrollBar:vertical { background: #faf9f5; width: 8px; margin: 0px; }
        QScrollBar::handle:vertical { background: #cbd5e1; border-radius: 4px; min-height: 20px; }
        QScrollBar::handle:vertical:hover { background: #94a3b8; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        
        QScrollBar:horizontal { background: #faf9f5; height: 8px; margin: 0px; }
        QScrollBar::handle:horizontal { background: #cbd5e1; border-radius: 4px; min-width: 20px; }
        QScrollBar::handle:horizontal:hover { background: #94a3b8; }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
        
        QScrollArea { border: none; background: transparent; }
    """)
    app.setApplicationName("GeoViz Engine")

    # 1. Show Splash Screen with fade-in animation
    splash = BrandSplashScreen()
    splash.setWindowOpacity(0.0)
    splash.show()
    
    anim = QPropertyAnimation(splash, b"windowOpacity")
    anim.setDuration(400)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.start()
    app.processEvents()
    
    # Simulate loading latency
    import time
    time.sleep(1.0)

    window = MainWindow()
    
    # Fade out splash and show main window
    anim_out = QPropertyAnimation(splash, b"windowOpacity")
    anim_out.setDuration(400)
    anim_out.setStartValue(1.0)
    anim_out.setEndValue(0.0)
    anim_out.finished.connect(splash.close)
    anim_out.start()
    
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
