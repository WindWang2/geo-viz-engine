"""MapPage — native QPainter-based geographic map for well coordinates with high-fidelity visual design."""
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QFrame, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QLabel, QCheckBox, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QIcon, QColor

from src.utils.paths import get_resources_dir as _get_res_dir

from geoviz_map import MapCanvas, ReferenceLabel, WellMarker

from src.data.cache import DataCache
from src.data.well_registry import available_wells
from src.utils.paths import get_data_dir

DATA_DIR = get_data_dir()
WELL_COORDS_FILE = DATA_DIR / "well_coordinates.json"
WORLD_GEOJSON_FILE = DATA_DIR / "world.json"
CHINA_GEOJSON_FILE = DATA_DIR / "china_provinces.json"


REFERENCE_LABELS: list[ReferenceLabel] = [
    ReferenceLabel(name="北京 (Beijing)", lng=116.4074, lat=39.9042, kind="capital"),
    ReferenceLabel(name="上海 (Shanghai)", lng=121.4737, lat=31.2304, kind="city"),
    ReferenceLabel(name="广州 (Guangzhou)", lng=113.2644, lat=23.1292, kind="city"),
    ReferenceLabel(name="深圳 (Shenzhen)", lng=114.0579, lat=22.5431, kind="city"),
    ReferenceLabel(name="香港 (Hong Kong)", lng=114.1694, lat=22.3193, kind="city"),
    ReferenceLabel(name="澳门 (Macau)", lng=113.5439, lat=22.1987, kind="city"),
    ReferenceLabel(name="惠州 (Huizhou)", lng=114.4158, lat=23.1109, kind="city"),
    ReferenceLabel(name="珠海 (Zhuhai)", lng=113.5767, lat=22.2707, kind="city"),
    ReferenceLabel(name="汕头 (Shantou)", lng=116.7084, lat=23.3718, kind="city"),
    ReferenceLabel(name="湛江 (Zhanjiang)", lng=110.3649, lat=21.2749, kind="city"),
    ReferenceLabel(name="海口 (Haikou)", lng=110.3308, lat=20.0221, kind="city"),
    ReferenceLabel(name="福州 (Fuzhou)", lng=119.3063, lat=26.0753, kind="city"),
    ReferenceLabel(name="台北 (Taipei)", lng=121.5654, lat=25.0330, kind="city"),
    ReferenceLabel(name="南宁 (Nanning)", lng=108.3200, lat=22.8240, kind="city"),
    ReferenceLabel(name="南海 (South China Sea)", lng=115.5, lat=20.2, kind="sea"),
]


def _l1_shadow(widget):
    """Add L1 (subtle) drop-shadow effect to a widget."""
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(8)
    shadow.setOffset(0, 1)
    shadow.setColor(QColor(0, 0, 0, 20))
    widget.setGraphicsEffect(shadow)


def _load_json(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return {"type": "FeatureCollection", "features": []}


def _coords_to_markers(coords, data_wells: set[str]) -> list[WellMarker]:
    return [
        WellMarker(
            name=w.name,
            lng=w.longitude,
            lat=w.latitude,
            color="#ef4444" if w.name in data_wells else "#6b7280",
            has_data=w.name in data_wells,
        )
        for w in coords
    ]


class MapPage(QWidget):
    open_well_log_requested = Signal(str)

    def __init__(self, cache: DataCache, well_click_callback=None):
        super().__init__()
        self.cache = cache
        self.well_click_callback = well_click_callback

        # Main Layout: horizontal split
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 1. Left Sidebar
        self.left_sidebar = QFrame()
        self.left_sidebar.setFixedWidth(260)
        self.left_sidebar.setStyleSheet(
            "QFrame { background: #ffffff; border-right: 1px solid #e5eaf1; }"
        )
        sidebar_layout = QVBoxLayout(self.left_sidebar)
        sidebar_layout.setContentsMargins(16, 16, 16, 16)
        sidebar_layout.setSpacing(12)

        # Search Bar (with linear SVG search icon, per Azurite spec)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索井位...")
        _search_icon_path = _get_res_dir() / "icons" / "ui" / "search.svg"
        if _search_icon_path.exists():
            self.search_box.addAction(QIcon(str(_search_icon_path)), QLineEdit.ActionPosition.LeadingPosition)
        self.search_box.setStyleSheet(
            "QLineEdit { background: #fafbfd; border: 1px solid #d3dbe6; border-radius: 6px; padding: 6px 10px 6px 6px; color: #1a2433; }"
            "QLineEdit:focus { border: 1px solid #1f66d4; background: #ffffff; }"
        )
        sidebar_layout.addWidget(self.search_box)

        # Chips for categorization
        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(6)
        
        self.chip_all = QPushButton("全部 46")
        self.chip_interpreted = QPushButton("已解释 31")
        self.chip_gas = QPushButton("含气 12")

        chip_style = (
            "QPushButton { border-radius: 6px; background: #fafbfd; color: #586878; border: 1px solid #d3dbe6; font-size: 11px; padding: 4px 8px; }"
            "QPushButton:hover { background: #e9effa; color: #1f66d4; border-color: #1f66d4; }"
            "QPushButton:checked { background: #e9effa; color: #1f66d4; border-color: #1f66d4; font-weight: bold; }"
        )
        for btn in [self.chip_all, self.chip_interpreted, self.chip_gas]:
            btn.setStyleSheet(chip_style)
            btn.setCheckable(True)
            chips_layout.addWidget(btn)
        
        self.chip_all.setChecked(True)
        sidebar_layout.addLayout(chips_layout)

        # Well scroll list
        self.well_list = QListWidget()
        self.well_list.setStyleSheet(
            "QListWidget { border: none; background: #ffffff; }"
            "QListWidget::item { padding: 8px; border-radius: 8px; margin: 1px 4px; color: #1a2433; }"
            "QListWidget::item:hover { background: #f1f4f9; }"
            "QListWidget::item:selected { background: #e9effa; color: #1f66d4; font-weight: bold; }"
        )
        sidebar_layout.addWidget(self.well_list)

        self.main_layout.addWidget(self.left_sidebar)

        # 2. Right Canvas Area
        self.right_container = QWidget()
        self.right_layout = QVBoxLayout(self.right_container)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(0)

        coords = cache.get_well_coordinates(WELL_COORDS_FILE)
        self.data_wells = available_wells()
        self.wells = _coords_to_markers(coords, self.data_wells)
        world = _load_json(WORLD_GEOJSON_FILE)
        china = _load_json(CHINA_GEOJSON_FILE)

        self.map_canvas = MapCanvas(
            wells=self.wells,
            world_geojson=world,
            china_geojson=china,
            reference_labels=REFERENCE_LABELS,
            initial_zoom=7.5,
        )
        self.right_layout.addWidget(self.map_canvas)
        self.main_layout.addWidget(self.right_container)

        # Populate well list
        for w in self.wells:
            item = QListWidgetItem(f"📍 {w.name}")
            item.setData(Qt.UserRole, w.name)
            self.well_list.addItem(item)

        # Wire search filtering
        self.search_box.textChanged.connect(self._filter_wells)
        self.well_list.itemClicked.connect(self._on_list_item_clicked)

        # 3. Right Area Floating Widgets
        # Layer Manager overlay (top-left)
        self.layer_manager = QFrame(self.right_container)
        self.layer_manager.setStyleSheet(
            "QFrame { background: rgba(255, 255, 255, 0.95); border: 1px solid #e5eaf1; border-radius: 8px; }"
        )
        _l1_shadow(self.layer_manager)
        lm_layout = QVBoxLayout(self.layer_manager)
        lm_layout.setContentsMargins(10, 10, 10, 10)
        lm_layout.setSpacing(6)
        lm_title = QLabel("图层管理")
        lm_title.setStyleSheet("font-weight: bold; color: #1a2433; font-size: 12px; border: none;")
        lm_layout.addWidget(lm_title)
        
        self.chk_wells = QCheckBox("井位标记")
        self.chk_wells.setChecked(True)
        self.chk_grids = QCheckBox("坐标网格")
        self.chk_grids.setChecked(True)
        for chk in [self.chk_wells, self.chk_grids]:
            chk.setStyleSheet("QCheckBox { color: #586878; font-size: 11px; border: none; }")
            lm_layout.addWidget(chk)

        # Floating Toolbar overlay (top-right)
        self.float_tb = QFrame(self.right_container)
        self.float_tb.setStyleSheet(
            "QFrame { background: rgba(255, 255, 255, 0.95); border: 1px solid #e5eaf1; border-radius: 8px; }"
        )
        _l1_shadow(self.float_tb)
        tb_layout = QVBoxLayout(self.float_tb)
        tb_layout.setContentsMargins(6, 6, 6, 6)
        tb_layout.setSpacing(6)
        
        self.btn_zoom_in = QPushButton("＋")
        self.btn_zoom_out = QPushButton("－")
        self.btn_fit = QPushButton("⛶")
        self.btn_ruler = QPushButton("📏")
        self.btn_ruler.hide()  # No backend implementation yet
        
        tb_btn_style = (
            "QPushButton { border: none; background: transparent; color: #586878; font-size: 14px; min-width: 32px; min-height: 32px; border-radius: 4px; padding: 0px; }"
            "QPushButton:hover { background: #f4f7fb; color: #1f66d4; }"
        )
        for btn in [self.btn_zoom_in, self.btn_zoom_out, self.btn_fit, self.btn_ruler]:
            btn.setStyleSheet(tb_btn_style)
            tb_layout.addWidget(btn)

        # Well Callout Panel overlay (starts hidden)
        self.well_callout = QFrame(self.right_container)
        self.well_callout.setStyleSheet(
            "QFrame { background: #ffffff; border: 1px solid #e5eaf1; border-radius: 12px; }"
        )
        co_layout = QVBoxLayout(self.well_callout)
        co_layout.setContentsMargins(16, 16, 16, 16)
        co_layout.setSpacing(8)

        self.well_callout_title = QLabel("井名: 未选择")
        self.well_callout_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #1a2433; border: none;")
        co_layout.addWidget(self.well_callout_title)

        self.well_callout_desc = QLabel("选择一口井以查看详细坐标和地质属性。")
        self.well_callout_desc.setStyleSheet("color: #586878; font-size: 12px; border: none;")
        self.well_callout_desc.setWordWrap(True)
        co_layout.addWidget(self.well_callout_desc)

        self.open_log_btn = QPushButton("打开井剖面")
        self.open_log_btn.setStyleSheet(
            "QPushButton { background: #1f66d4; color: #ffffff; font-weight: bold; border-radius: 6px; padding: 6px 12px; border: none; }"
            "QPushButton:hover { background: #1a54b2; }"
        )
        co_layout.addWidget(self.open_log_btn)
        
        self.well_callout.hide()

        # Connect canvas signals
        self.map_canvas.well_clicked.connect(self._on_well_clicked)
        self.map_canvas.well_hovered.connect(self._on_well_hovered)
        self.open_log_btn.clicked.connect(self._on_open_log_clicked)

        # Wire toolbar buttons
        self.btn_zoom_in.clicked.connect(lambda: self.map_canvas.set_zoom(self.map_canvas.zoom * 1.2))
        self.btn_zoom_out.clicked.connect(lambda: self.map_canvas.set_zoom(self.map_canvas.zoom / 1.2))
        self.btn_fit.clicked.connect(lambda: self.map_canvas.set_zoom(7.5))

        # Wire layer visibility checkboxes
        self.chk_wells.toggled.connect(self._on_layer_toggled)
        self.chk_grids.toggled.connect(self._on_layer_toggled)

        # Wire filter chips
        self.chip_all.toggled.connect(lambda checked: self._on_chip_toggled("all", checked))
        self.chip_interpreted.toggled.connect(lambda checked: self._on_chip_toggled("interpreted", checked))
        self.chip_gas.toggled.connect(lambda checked: self._on_chip_toggled("gas", checked))

    def reload_wells(self):
        """Refresh well markers and sidebar list from the catalog."""
        coords = self.cache.get_well_coordinates(WELL_COORDS_FILE)
        self.data_wells = available_wells()
        self.wells = _coords_to_markers(coords, self.data_wells)
        self.map_canvas._wells_layer.wells = self.wells
        self.map_canvas._wells_layer._build_index()
        self.map_canvas.update()
        self.well_list.clear()
        for w in self.wells:
            item = QListWidgetItem(f"📍 {w.name}")
            item.setData(Qt.UserRole, w.name)
            self.well_list.addItem(item)
        self.chip_all.setText(f"全部 {len(self.wells)}")

    def _on_layer_toggled(self):
        """Toggle map layer visibility from checkboxes."""
        from geoviz_map.layers.wells import WellsLayer
        from geoviz_map.layers.graticule import GraticuleLayer
        for layer in self.map_canvas.layers:
            if isinstance(layer, WellsLayer):
                layer.visible = self.chk_wells.isChecked()
            elif isinstance(layer, GraticuleLayer):
                layer.visible = self.chk_grids.isChecked()
        self.map_canvas.update()

    def _on_chip_toggled(self, chip: str, checked: bool):
        """Filter well list by chip category."""
        if chip == "all" and checked:
            self.chip_interpreted.setChecked(False)
            self.chip_gas.setChecked(False)
        elif chip == "interpreted" and checked:
            self.chip_all.setChecked(False)
            self.chip_gas.setChecked(False)
        elif chip == "gas" and checked:
            self.chip_all.setChecked(False)
            self.chip_interpreted.setChecked(False)
        # If unchecking without checking another, re-check "all"
        if not checked and not self.chip_all.isChecked() and not self.chip_interpreted.isChecked() and not self.chip_gas.isChecked():
            self.chip_all.setChecked(True)
        self._apply_chip_filter()

    def _apply_chip_filter(self):
        """Filter the well list based on active chip."""
        show_data_only = self.chip_interpreted.isChecked()
        show_gas_only = self.chip_gas.isChecked()
        for i in range(self.well_list.count()):
            item = self.well_list.item(i)
            well_name = item.data(Qt.UserRole)
            marker = next((w for w in self.wells if w.name == well_name), None)
            if marker is None:
                item.setHidden(False)
                continue
            if show_data_only:
                item.setHidden(not marker.has_data)
            elif show_gas_only:
                item.setHidden(not marker.has_data)
            else:
                item.setHidden(False)

    def _filter_wells(self, text):
        for i in range(self.well_list.count()):
            item = self.well_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def _on_list_item_clicked(self, item):
        well_name = item.data(Qt.UserRole)
        self._on_well_clicked(well_name)

    def _on_well_clicked(self, well_name: str):
        well_marker = None
        for w in self.wells:
            if w.name == well_name:
                well_marker = w
                break

        if well_marker:
            self.well_callout_title.setText(f"📍 {well_name}")
            status_str = "含气" if well_marker.has_data else "未测试"
            self.well_callout_desc.setText(
                f"经度: {well_marker.lng:.4f}°\n"
                f"纬度: {well_marker.lat:.4f}°\n"
                f"类型: {status_str}"
            )
            self.well_callout.show()
            self.well_callout.raise_()

    def _on_well_hovered(self, well_name: str):
        from PySide6.QtWidgets import QApplication
        if well_name:
            QApplication.setOverrideCursor(Qt.CursorShape.PointingHandCursor)
        else:
            QApplication.restoreOverrideCursor()

    def _on_open_log_clicked(self):
        title = self.well_callout_title.text().replace("📍 ", "").strip()
        self.open_well_log_requested.emit(title)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Position floating overlays relative to right container size
        rc_w = self.right_container.width()
        rc_h = self.right_container.height()

        self.layer_manager.setGeometry(16, 16, 140, 95)
        self.float_tb.setGeometry(rc_w - 44 - 16, 16, 44, 148)
        
        co_w, co_h = 240, 140
        self.well_callout.setGeometry(
            16,
            rc_h - co_h - 16,
            co_w,
            co_h
        )
