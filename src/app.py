from PySide6.QtCore import Qt, QSize
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
    ("map", "src/resources/icons/map.svg", "地图总览"),
    ("paleo_map", "src/resources/icons/map.svg", "古地理图"),
    ("well_log", "src/resources/icons/well_log.svg", "井剖面"),
    ("cross_well", "src/resources/icons/cross_well.svg", "连井对比"),
    ("seismic", "src/resources/icons/seismic.svg", "地震3D"),
    ("data", "src/resources/icons/data.svg", "数据管理"),
    ("tools", "src/resources/icons/tools.svg", "工具箱"),
]


class SidebarButton(QPushButton):
    def __init__(self, icon_path: str, tooltip: str, nav_key: str):
        super().__init__()
        self.setText(" " + tooltip)  # Space for visual padding between icon and text
        self.nav_key = nav_key
        self.setProperty("nav_key", nav_key)
        self.setFixedHeight(48)
        self.setToolTip(tooltip)
        self.setCheckable(True)
        self.setIcon(QIcon(icon_path))
        self.setIconSize(QSize(20, 20))
        self.setStyleSheet("""
            SidebarButton {
                border: none;
                border-radius: 8px;
                background: transparent;
                text-align: left;
                padding-left: 12px;
                font-size: 14px;
                font-weight: 500;
                color: #4a5568;
            }
            SidebarButton:checked {
                background: #edf2f7;
                color: #2b6cb0;
                font-weight: bold;
            }
            SidebarButton:hover {
                background: #e2e8f0;
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
        self.sidebar.setFixedWidth(140)
        self.sidebar.setStyleSheet("background: #f7fafc; border-right: 1px solid #e2e8f0;")
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(8, 12, 8, 12)
        sidebar_layout.setSpacing(6)

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

        from src.pages.cross_well_page import CrossWellPage
        self.cross_well_page = CrossWellPage()

        try:
            from src.pages.map_page import MapPage
            self.map_page = MapPage(self.cache, well_click_callback=self._on_well_clicked)
        except ImportError:
            self.map_page = None
        except Exception:
            self.map_page = None

        map_widget = self.map_page if self.map_page else QLabel("地图总览 (WebEngine unavailable)")

        try:
            from src.pages.paleo_map_page import PaleoMapPage
            self.paleo_map_page = PaleoMapPage()
            paleo_map_widget = self.paleo_map_page
        except Exception as e:
            paleo_map_widget = QLabel(f"古地理图 (unavailable: {e})")
            paleo_map_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            paleo_map_widget.setStyleSheet("font-size: 24px; color: #a0aec0;")

        try:
            from src.pages.seismic_page import SeismicPage
            self.seismic_page = SeismicPage()
            seismic_widget = self.seismic_page
        except Exception:
            seismic_widget = QLabel("地震3D (placeholder)")
            seismic_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            seismic_widget.setStyleSheet("font-size: 24px; color: #a0aec0;")

        from src.pages.data_page import DataPage
        self.data_page = DataPage(self.cache)

        from src.pages.tools_page import ToolsPage
        self.tools_page = ToolsPage()

        page_widgets = [
            map_widget,                            # map
            paleo_map_widget,                      # paleo map
            self.well_log_page,                   # well log
            self.cross_well_page,                # cross well
            seismic_widget,                       # seismic
            self.data_page,                      # data
            self.tools_page,                     # tools
        ]
        for pw in page_widgets:
            if isinstance(pw, QLabel):
                pw.setAlignment(Qt.AlignmentFlag.AlignCenter)
                pw.setStyleSheet("font-size: 24px; color: #a0aec0;")
            self.stack.addWidget(pw)
        root.addWidget(self.stack, 1)

    def _switch_page(self, index: int):
        for i, btn in enumerate(self.sidebar_buttons):
            btn.setChecked(i == index)
        self.stack.setCurrentIndex(index)

    def _on_well_clicked(self, well_name: str):
        self.well_log_page.load_well(well_name)
        self._switch_page(2)
