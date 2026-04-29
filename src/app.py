from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QLabel,
)

from src.data.cache import DataCache


PAGES = [
    ("map", "M", "地图总览"),
    ("well_log", "W", "井剖面"),
    ("seismic", "S", "地震3D"),
    ("data", "D", "数据管理"),
]


class SidebarButton(QPushButton):
    def __init__(self, icon_text: str, tooltip: str, nav_key: str):
        super().__init__(icon_text)
        self.nav_key = nav_key
        self.setProperty("nav_key", nav_key)
        self.setFixedSize(48, 48)
        self.setToolTip(tooltip)
        self.setCheckable(True)
        self.setStyleSheet("""
            SidebarButton {
                border: none;
                border-radius: 8px;
                font-size: 20px;
                background: transparent;
            }
            SidebarButton:checked {
                background: #2d3748;
            }
            SidebarButton:hover {
                background: #1a202c;
            }
        """)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GeoViz Engine")
        self.resize(1280, 800)
        self.cache = DataCache()
        self._build_ui()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(56)
        self.sidebar.setStyleSheet("background: #0d1117;")
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(4, 8, 4, 8)
        sidebar_layout.setSpacing(4)

        self.sidebar_buttons: list[SidebarButton] = []
        for i, (key, icon, tooltip) in enumerate(PAGES):
            btn = SidebarButton(icon, tooltip, key)
            btn.clicked.connect(lambda checked, idx=i: self._switch_page(idx))
            self.sidebar_buttons.append(btn)
            sidebar_layout.addWidget(btn)

        self.sidebar_buttons[0].setChecked(True)
        sidebar_layout.addStretch()
        root.addWidget(self.sidebar)

        # Page stack
        self.stack = QStackedWidget()

        # Lazy-import pages to avoid heavy imports at startup
        from src.pages.well_log_page import WellLogPage
        self.well_log_page = WellLogPage()

        try:
            from src.pages.map_page import MapPage
            self.map_page = MapPage(self.cache, well_click_callback=self._on_well_clicked)
        except ImportError:
            self.map_page = None
        except Exception:
            self.map_page = None

        map_widget = self.map_page if self.map_page else QLabel("地图总览 (WebEngine unavailable)")

        try:
            from src.renderers.seismic_renderer import _check_pyvista_qt_available
            if not _check_pyvista_qt_available():
                raise RuntimeError("pyvistaqt QtInteractor unavailable (no OpenGL)")
            from src.pages.seismic_page import SeismicPage
            self.seismic_page = SeismicPage()
            seismic_widget = self.seismic_page
        except Exception:
            seismic_widget = QLabel("地震3D (placeholder)")
            seismic_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            seismic_widget.setStyleSheet("font-size: 24px; color: #4a5568;")

        from src.pages.data_page import DataPage
        self.data_page = DataPage(self.cache)

        page_widgets = [
            map_widget,                            # map
            self.well_log_page,                   # well log
            seismic_widget,                       # seismic
            self.data_page,                      # data
        ]
        for pw in page_widgets:
            if isinstance(pw, QLabel):
                pw.setAlignment(Qt.AlignmentFlag.AlignCenter)
                pw.setStyleSheet("font-size: 24px; color: #4a5568;")
            self.stack.addWidget(pw)
        root.addWidget(self.stack, 1)

    def _switch_page(self, index: int):
        for i, btn in enumerate(self.sidebar_buttons):
            btn.setChecked(i == index)
        self.stack.setCurrentIndex(index)

    def _on_well_clicked(self, well_name: str):
        self._switch_page(1)  # Switch to well log page
