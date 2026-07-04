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
    exe_dir = Path(sys.executable).parent
    base_dirs.append(exe_dir)
    base_dirs.append(exe_dir / "_internal")

    for base_dir in base_dirs:
        if base_dir.exists():
            try:
                os.add_dll_directory(str(base_dir))
            except OSError:
                pass
            for sub in ["PySide6", "shiboken6"]:
                sub_dir = base_dir / sub
                if sub_dir.exists():
                    try:
                        os.add_dll_directory(str(sub_dir))
                    except OSError:
                        pass

    os.environ["PATH"] = str(exe_dir / "_internal" / "PySide6") + os.pathsep + os.environ["PATH"]
    os.environ["PATH"] = str(exe_dir / "_internal" / "shiboken6") + os.pathsep + os.environ["PATH"]
    os.environ["PATH"] = str(exe_dir / "_internal") + os.pathsep + os.environ["PATH"]


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
from src.utils.global_style import GLOBAL_STYLESHEET


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

    app.setStyleSheet(GLOBAL_STYLESHEET)
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
