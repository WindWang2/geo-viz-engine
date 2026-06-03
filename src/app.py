from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QLabel,
    QFrame,
)

from src.data.cache import DataCache
from src.utils.paths import get_resources_dir


def _get_icon_path(name: str) -> str:
    """Resolve icon path that works in both dev and frozen (PyInstaller) modes."""
    return str(get_resources_dir() / "icons" / name)


PAGES = [
    ("map",       _get_icon_path("map.svg"),       "地图总览"),
    ("paleo_map", _get_icon_path("paleo.svg"),     "古地理图"),
    ("well_log",  _get_icon_path("well.svg"),      "井剖面"),
    ("cross_well",_get_icon_path("cross.svg"),     "连井对比"),
    ("seismic",   _get_icon_path("seismic.svg"),   "地震3D"),
    ("plots",     _get_icon_path("plots.svg"),     "平面图件"),
    ("data",      _get_icon_path("data.svg"),       "数据管理"),
    ("tools",     _get_icon_path("tools.svg"),      "工具箱"),
]

PAGE_CONFIGS = {
    0: {
        "title": "地图总览",
        "sub": "46 口井 · EPSG:4326",
        "status": "地图就绪 · 中心 106.1°E 30.3°N · zoom 7",
        "tools": ["layers", "ruler", "settings"]
    },
    1: {
        "title": "古地理图",
        "sub": "沧浪铺组 · Plate Carrée",
        "status": "古地理图 · 6 相带 · 8 井投影",
        "tools": ["layers", "palette", "export"]
    },
    2: {
        "title": "老龙1",
        "sub": "DEPTH 2515–2610m",
        "status": "老龙1 · 11 轨道 · 1:500",
        "tools": ["seg:测井图,数据", "layers"]
    },
    3: {
        "title": "连井对比",
        "sub": "4 wells · PCA",
        "status": "连井剖面 · 16 拾取点 · DTW 就绪",
        "tools": ["undo", "redo", "export"]
    },
    4: {
        "title": "地震 3D",
        "sub": "synthetic.sgy",
        "status": "体渲染 · 512×384×600 · LRU 50",
        "tools": ["grid3d", "palette", "settings"]
    },
    5: {
        "title": "平面图件",
        "sub": "砂体厚度 · IDW",
        "status": "等值图 · 网格 200×200 · 22 控制点",
        "tools": ["contour", "palette", "export"]
    },
    6: {
        "title": "数据管理",
        "sub": "46 datasets",
        "status": "缓存 231 MB · Calamine 引擎",
        "tools": ["filter", "upload"]
    },
    7: {
        "title": "工具箱",
        "sub": "6 工具",
        "status": "工具箱 · 6 个可用工具",
        "tools": ["settings"]
    },
    8: {
        "title": "设置",
        "sub": "主题 / 坐标 / 缓存",
        "status": "设置 · 偏好配置",
        "tools": []
    }
}


class SidebarButton(QPushButton):
    def __init__(self, icon_path: str, tooltip: str, nav_key: str):
        super().__init__()
        self.setText(" " + tooltip)  # Space for visual padding between icon and text
        self.nav_key = nav_key
        self.setProperty("nav_key", nav_key)
        self.setFixedHeight(40)
        self.setToolTip(tooltip)
        self.setCheckable(True)
        self.setIcon(QIcon(icon_path))
        self.setIconSize(QSize(19, 19))
        self.setStyleSheet("""
            SidebarButton {
                border: none;
                border-radius: 8px;
                background: transparent;
                text-align: left;
                padding-left: 11px;
                font-size: 13px;
                font-weight: 500;
                color: #586878;
                border-left: 3.5px solid transparent;
            }
            SidebarButton:checked {
                background: #e9effa;
                color: #1f66d4;
                font-weight: bold;
                border-left: 3.5px solid #1f66d4;
            }
            SidebarButton:hover {
                background: #f1f4f9;
                color: #1a2433;
            }
        """)


class HeaderToolButton(QPushButton):
    def __init__(self, icon_name: str, parent=None):
        super().__init__(parent)
        self.tool_key = icon_name
        self.setFixedSize(32, 32)
        icon_path = _get_icon_path(f"ui/{icon_name}.svg")
        self.setIcon(QIcon(icon_path))
        self.setIconSize(QSize(17, 17))
        self.setStyleSheet("""
            HeaderToolButton {
                border: none;
                border-radius: 8px;
                background: transparent;
            }
            HeaderToolButton:hover {
                background: #f1f4f9;
            }
        """)


class SegmentedControl(QFrame):
    def __init__(self, items: list[str], parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            SegmentedControl {
                background: #f1f4f9;
                border-radius: 8px;
                padding: 3px;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.buttons = []
        for it in items:
            btn = QPushButton(it)
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    border: none;
                    background: transparent;
                    color: #586878;
                    padding: 4px 11px;
                    font-size: 12px;
                    font-weight: 500;
                    border-radius: 6px;
                }
                QPushButton:checked {
                    background: #ffffff;
                    color: #1f66d4;
                    font-weight: bold;
                }
            """)
            layout.addWidget(btn)
            self.buttons.append(btn)
        self.buttons[0].setChecked(True)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GeoViz Engine")
        self.setWindowIcon(QIcon(_get_icon_path("brand/geoviz-mark.svg")))
        self.resize(1280, 820)
        self.cache = DataCache()
        self.current_project = None
        self.current_project_path = None
        self._build_ui()

    def _build_ui(self):
        self._sidebar_collapsed = False
        self._sidebar_width_expanded = 200
        self._sidebar_width_collapsed = 56

        # Base outer layout is Vertical to place Header, Body (Sidebar+Stack), and Footer
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # 1. Top Header Frame
        self.header_frame = QFrame()
        self.header_frame.setObjectName("header_frame")
        self.header_frame.setFixedHeight(48)
        self.header_frame.setStyleSheet("""
            #header_frame {
                background: #ffffff;
                border-bottom: 1px solid #e5eaf1;
            }
        """)
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(16, 0, 16, 0)
        header_layout.setSpacing(14)

        # Brand Section
        self.brand_logo = QLabel()
        logo_path = _get_icon_path("brand/geoviz-mark.svg")
        self.brand_logo.setPixmap(QIcon(logo_path).pixmap(26, 26))
        self.brand_logo.setFixedSize(26, 26)
        self.brand_logo.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1f66d4, stop:1 #133a76);
            border-radius: 7px;
        """)
        self.brand_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.brand_name_label = QLabel()
        self.brand_name_label.setTextFormat(Qt.TextFormat.RichText)
        self.brand_name_label.setText('GeoViz <span style="color: #92a0b0; font-weight: 500;">Engine</span>')
        self.brand_name_label.setStyleSheet("font-weight: 700; font-size: 14.5px; color: #1f66d4; padding: 0px; margin: 0px;")
        self.brand_name_label.setMinimumWidth(115)

        header_layout.addWidget(self.brand_logo)
        header_layout.addWidget(self.brand_name_label)

        # Sidebar toggle button
        self.sidebar_toggle_btn = QPushButton("☰")
        self.sidebar_toggle_btn.setFixedSize(32, 32)
        self.sidebar_toggle_btn.setStyleSheet("""
            QPushButton {
                border: none; border-radius: 8px;
                background: transparent; font-size: 16px; color: #586878;
            }
            QPushButton:hover { background: #f1f4f9; }
        """)
        self.sidebar_toggle_btn.clicked.connect(self._toggle_sidebar)
        header_layout.addWidget(self.sidebar_toggle_btn)

        # Divider
        divider1 = QFrame()
        divider1.setFrameShape(QFrame.Shape.VLine)
        divider1.setFrameShadow(QFrame.Shadow.Plain)
        divider1.setStyleSheet("color: #e5eaf1; max-width: 1px; min-height: 20px;")
        header_layout.addWidget(divider1)

        # Dynamic Header Context (Title & Subtitle)
        self.header_title = QLabel("地图总览")
        self.header_title.setStyleSheet("font-weight: 600; font-size: 13.5px; color: #1a2433;")
        self.header_sub = QLabel("46 口井 · EPSG:4326")
        self.header_sub.setStyleSheet("color: #92a0b0; font-size: 11.5px; font-family: monospace;")
        
        header_layout.addWidget(self.header_title)
        header_layout.addWidget(self.header_sub)

        # Search bar
        from PySide6.QtWidgets import QLineEdit
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("搜索功能、井名...")
        self.search_bar.setFixedHeight(30)
        self.search_bar.setMinimumWidth(200)
        self.search_bar.setStyleSheet("""
            QLineEdit {
                background: #f1f4f9;
                border: none;
                border-radius: 8px;
                padding: 5px 12px 5px 28px;
                font-size: 12px;
                color: #92a0b0;
            }
            QLineEdit:focus {
                background: #ffffff;
                border: 1px solid #1f66d4;
            }
        """)
        search_icon_path = _get_icon_path("ui/search.svg")
        self.search_bar.addAction(QIcon(search_icon_path), QLineEdit.ActionPosition.LeadingPosition)
        header_layout.addWidget(self.search_bar)

        # Notification bell
        self.notification_bell_btn = HeaderToolButton("bell")
        self.notification_bell_btn.setToolTip("通知")
        header_layout.addWidget(self.notification_bell_btn)

        header_layout.addStretch()

        # Dynamic Tools Container
        self.header_tools_container = QWidget()
        self.header_tools_layout = QHBoxLayout(self.header_tools_container)
        self.header_tools_layout.setContentsMargins(0, 0, 0, 0)
        self.header_tools_layout.setSpacing(7)
        header_layout.addWidget(self.header_tools_container)

        # Divider
        divider2 = QFrame()
        divider2.setFrameShape(QFrame.Shape.VLine)
        divider2.setFrameShadow(QFrame.Shadow.Plain)
        divider2.setStyleSheet("color: #e5eaf1; max-width: 1px; min-height: 20px;")
        header_layout.addWidget(divider2)

        # Language dropdown / label
        self.lang_label = QLabel()
        self.lang_label.setTextFormat(Qt.TextFormat.RichText)
        globe_icon_path = _get_icon_path("ui/globe.svg")
        self.lang_label.setText(f'<img src="{globe_icon_path}" width="16" height="16"> 中文')
        self.lang_label.setStyleSheet("font-size: 12px; color: #586878;")
        header_layout.addWidget(self.lang_label)

        outer_layout.addWidget(self.header_frame)

        # 2. Main Body Layout (Sidebar + Stack)
        body_widget = QWidget()
        body_layout = QHBoxLayout(body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Sidebar
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(200)
        self.sidebar.setStyleSheet("background: #ffffff; border-right: 1px solid #e5eaf1;")
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(4)

        # Group "可视化"
        lbl_viz = QLabel("可视化")
        lbl_viz.setStyleSheet("font-size: 10.5px; font-weight: 600; letter-spacing: 0.8px; text-transform: uppercase; color: #92a0b0; padding: 12px 10px 6px;")
        sidebar_layout.addWidget(lbl_viz)

        self.sidebar_buttons: list[SidebarButton] = []
        for i, (key, icon, tooltip) in enumerate(PAGES):
            if i == 6:
                # Group "工作区"
                lbl_work = QLabel("工作区")
                lbl_work.setStyleSheet("font-size: 10.5px; font-weight: 600; letter-spacing: 0.8px; text-transform: uppercase; color: #92a0b0; padding: 12px 10px 6px;")
                sidebar_layout.addWidget(lbl_work)
            
            btn = SidebarButton(icon, tooltip, key)
            btn.clicked.connect(lambda _checked=False, idx=i: self._switch_page(idx))
            self.sidebar_buttons.append(btn)
            sidebar_layout.addWidget(btn)

        self.sidebar_buttons[0].setChecked(True)
        sidebar_layout.addStretch()

        # Separator line before settings
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e5eaf1; max-height: 1px;")
        sidebar_layout.addWidget(sep)

        # Footer Settings button
        self.settings_btn = SidebarButton(_get_icon_path("ui/settings.svg"), "设置", "settings")
        self.settings_btn.clicked.connect(lambda: self._switch_page(8))
        sidebar_layout.addWidget(self.settings_btn)

        body_layout.addWidget(self.sidebar)

        # Page stack
        self.stack = QStackedWidget()

        # Lazy-import pages
        try:
            from src.pages.seismic import SeismicPage
            self.seismic_page = SeismicPage()
            seismic_widget = self.seismic_page
        except Exception:
            seismic_widget = QLabel("地震3D (placeholder)")
            seismic_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            seismic_widget.setStyleSheet("font-size: 24px; color: #a0aec0;")

        try:
            from src.pages.map import MapPage
            self.map_page = MapPage(self.cache, well_click_callback=self._on_well_clicked)
        except ImportError:
            self.map_page = None
        except Exception:
            self.map_page = None

        map_widget = self.map_page if self.map_page else QLabel("地图总览 (WebEngine unavailable)")

        try:
            from src.pages.paleo_map import PaleoMapPage
            self.paleo_map_page = PaleoMapPage()
            paleo_map_widget = self.paleo_map_page
        except Exception as e:
            paleo_map_widget = QLabel(f"古地理图 (unavailable: {e})")
            paleo_map_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            paleo_map_widget.setStyleSheet("font-size: 24px; color: #a0aec0;")

        from src.pages.well_log import WellLogPage
        self.well_log_page = WellLogPage()

        from src.pages.cross_well import CrossWellPage
        self.cross_well_page = CrossWellPage()

        # Connect map box-selection to cross-well planned section loader
        if self.map_page and hasattr(self.map_page, "map_canvas"):
            self.map_page.map_canvas.section_selected.connect(self._on_section_selected)

        # Connect map well-callout "open well log" linkage
        if self.map_page and hasattr(self.map_page, "open_well_log_requested"):
            self.map_page.open_well_log_requested.connect(self._on_open_well_log_requested)

        from src.pages.data import DataPage
        self.data_page = DataPage(self.cache)

        from src.pages.tools import ToolsPage
        self.tools_page = ToolsPage()

        from src.pages.plots import PlotsPage
        self.plots_page = PlotsPage()

        from src.pages.settings import SettingsPage
        self.settings_page = SettingsPage()

        page_widgets = [
            map_widget,                            # map (0)
            paleo_map_widget,                      # paleo map (1)
            self.well_log_page,                    # well log (2)
            self.cross_well_page,                  # cross well (3)
            seismic_widget,                        # seismic (4)
            self.plots_page,                       # plots (5)
            self.data_page,                        # data (6)
            self.tools_page,                       # tools (7)
            self.settings_page,                    # settings (8)
        ]
        for pw in page_widgets:
            if isinstance(pw, QLabel):
                pw.setAlignment(Qt.AlignmentFlag.AlignCenter)
                pw.setStyleSheet("font-size: 24px; color: #a0aec0;")
            self.stack.addWidget(pw)
        body_layout.addWidget(self.stack, 1)

        outer_layout.addWidget(body_widget, 1)

        # 3. Bottom Status Bar Frame
        self.footer_frame = QFrame()
        self.footer_frame.setObjectName("footer_frame")
        self.footer_frame.setFixedHeight(26)
        self.footer_frame.setStyleSheet("""
            #footer_frame {
                background: #ffffff;
                border-top: 1px solid #e5eaf1;
            }
        """)
        footer_layout = QHBoxLayout(self.footer_frame)
        footer_layout.setContentsMargins(14, 0, 14, 0)
        footer_layout.setSpacing(14)

        # Green Indicator Dot
        self.status_dot = QLabel()
        self.status_dot.setFixedSize(6, 6)
        self.status_dot.setStyleSheet("""
            background: #2ca36b;
            border-radius: 3px;
        """)

        # Status text
        self.status_text = QLabel("就绪")
        self.status_text.setStyleSheet("color: #92a0b0; font-size: 11px; font-family: monospace;")

        footer_layout.addWidget(self.status_dot)
        self.status_dot.setVisible(False)  # No health signal to drive this yet
        footer_layout.addWidget(self.status_text)
        footer_layout.addStretch()

        # Version label
        from pathlib import Path as _P
        _version_file = _P(__file__).resolve().parent.parent / "VERSION"
        _ver = _version_file.read_text().strip() if _version_file.exists() else "?.?.?"
        self.version_label = QLabel(f"GeoViz Engine v{_ver}")
        self.version_label.setStyleSheet("color: #92a0b0; font-size: 11px; font-family: monospace;")
        footer_layout.addWidget(self.version_label)

        outer_layout.addWidget(self.footer_frame)

        # Initialize Header context & Tools for Map Page (default index 0)
        self._update_header_and_footer(0)

        # Connect preference bus signals
        from src.utils.preferences import get_preference_bus
        bus = get_preference_bus()
        bus.theme_changed.connect(self._on_theme_preference)
        bus.cache_cleared.connect(self._on_cache_cleared)

        # Restore sidebar collapsed state
        from PySide6.QtCore import QSettings
        settings = QSettings("GeoViz", "Engine")
        if settings.value("sidebar/collapsed", False, type=bool):
            self._sidebar_collapsed = False
            self._toggle_sidebar()

    def _switch_page(self, index: int):
        # 1. Cleanup current page if needed (stop threads, free GPU)
        current = self.stack.currentWidget()
        if current is not None and hasattr(current, "cleanup"):
            try:
                current.cleanup()
            except Exception as e:
                print(f"Error during page cleanup: {e}")

        # 2. Perform switch
        for i, btn in enumerate(self.sidebar_buttons):
            btn.setChecked(i == index)
        self.stack.setCurrentIndex(index)
        self._update_header_and_footer(index)

    def _toggle_sidebar(self):
        from PySide6.QtCore import QSettings

        self._sidebar_collapsed = not self._sidebar_collapsed
        w = self._sidebar_width_collapsed if self._sidebar_collapsed else self._sidebar_width_expanded
        self.sidebar.setFixedWidth(w)

        for btn in self.sidebar_buttons:
            if self._sidebar_collapsed:
                btn.setText("")
                btn.setFixedWidth(44)
            else:
                # Restore text from tooltip (nav_key label)
                tooltip = btn.toolTip()
                btn.setText(" " + tooltip)
                btn.setFixedWidth(160)

        # Also handle settings button
        if hasattr(self, 'settings_btn'):
            if self._sidebar_collapsed:
                self.settings_btn.setText("")
                self.settings_btn.setFixedWidth(44)
            else:
                self.settings_btn.setText(" " + self.settings_btn.toolTip())
                self.settings_btn.setFixedWidth(160)

        # Persist state
        settings = QSettings("GeoViz", "Engine")
        settings.setValue("sidebar/collapsed", self._sidebar_collapsed)

    def _update_header_and_footer(self, index: int):
        cfg = PAGE_CONFIGS.get(index, {})
        if not cfg:
            return

        # Update Title & Subtitle
        self.header_title.setText(cfg["title"])
        self.header_sub.setText(cfg["sub"])

        # Update Status Bar text
        self.status_text.setText(cfg["status"])

        # Clear existing tool widgets
        while self.header_tools_layout.count():
            item = self.header_tools_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        # Populate Tools
        for t in cfg["tools"]:
            if t.startswith("seg:"):
                items = t[4:].split(",")
                seg = SegmentedControl(items)
                self.header_tools_layout.addWidget(seg)
            else:
                btn = HeaderToolButton(t)
                btn.clicked.connect(lambda checked=False, key=t: self._on_header_tool(key))
                self.header_tools_layout.addWidget(btn)

    def _on_header_tool(self, tool_key: str):
        """Dispatch header tool button clicks to the active page."""
        page = self.stack.currentWidget()
        if page is None:
            return
        handler_name = f"_on_tool_{tool_key}"
        handler = getattr(page, handler_name, None)
        if handler is not None:
            handler()
        elif tool_key == "settings":
            self._switch_page(8)

    def _on_well_clicked(self, well_name: str):
        self.well_log_page.load_well(well_name)
        self._switch_page(2)

    def _on_open_well_log_requested(self, well_name: str):
        """Map Well Callout 'Open well log' button → load and switch to WellLogPage."""
        self.well_log_page.load_well(well_name)
        self._switch_page(2)

    def _on_section_selected(self, well_names: list[str]):
        self.cross_well_page.load_planned_section(well_names)
        self._switch_page(3)

    def sync_from_project(self, project_data):
        """Apply project state to the main window and all pages."""
        self.current_project = project_data
        
        # Restore active page
        if project_data.view_state:
            active_page = project_data.view_state.active_page
            self._switch_page(active_page)

        # Sync DataPage display if instantiated
        if hasattr(self, "data_page") and self.data_page is not None:
            self.data_page.update_project_display()

    def sync_to_project(self):
        """Gather current application state from all pages and return a ProjectSchema."""
        from src.data.project import ProjectSchema, ProjectMeta, ProjectViewState
        from datetime import datetime

        # Create defaults if no project is active
        if self.current_project is None:
            now_str = datetime.now().isoformat()
            meta = ProjectMeta(
                name="New Project",
                version="0.8.0",
                created_at=now_str,
                updated_at=now_str
            )
            self.current_project = ProjectSchema(meta=meta)

        # Update metadata timestamp
        self.current_project.meta.updated_at = datetime.now().isoformat()

        # Gather view state
        self.current_project.view_state.active_page = self.stack.currentIndex()

        return self.current_project

    def closeEvent(self, event):
        # Stop any background QThreads owned by pages to prevent
        # "QThread: Destroyed while thread is still running" on shutdown.
        for attr in ("_worker", "_load_thread", "_pred_thread"):
            for page in (
                getattr(self, "plots_page", None),
                getattr(self, "well_log_page", None),
                getattr(self, "cross_well_page", None),
            ):
                if page is None:
                    continue
                t = getattr(page, attr, None)
                if t is not None and hasattr(t, "isRunning"):
                    try:
                        if t.isRunning():
                            if hasattr(t, "quit"):
                                t.quit()
                            if not t.wait(1500):
                                t.terminate()
                                t.wait(500)
                    except RuntimeError:
                        pass
        super().closeEvent(event)

    def _on_theme_preference(self, theme_label: str):
        """Apply theme change from settings page."""
        # Theme application is handled by qApp stylesheet reload.
        # This is the hook point for future theme switching logic.

    def _on_cache_cleared(self, mb_released: float):
        """Update status bar after cache clear."""
        self.status_text.setText(f"缓存已清理 · 释放 {mb_released:.1f} MB")
