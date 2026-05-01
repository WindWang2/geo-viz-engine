from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QFileDialog,
)
from src.data.loaders import load_well_log_from_excel, load_well_log_laolong1
from src.renderers.well_log.chart_engine import ChartEngine
from src.renderers.well_log.configs.laolong1 import laolong1_config

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_LAOLONG1_XLS = Path("/home/kevin/DEVON/老龙1井-野外剖面数据整理 .xls")

# Mapping: well_name → (loader_fn, path, config)
_WELL_DATA: dict[str, tuple] = {
    "HZ25-10-1": (load_well_log_from_excel, _DATA_DIR / "HZ25-10-1-laolong.xls", laolong1_config),
    "老龙1": (load_well_log_laolong1, _LAOLONG1_XLS, laolong1_config),
}


class WellLogPage(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Toolbar (hidden until a chart is loaded)
        self._toolbar = QWidget()
        self._toolbar.setStyleSheet("background: #f7fafc; border-bottom: 1px solid #e2e8f0;")
        toolbar_layout = QHBoxLayout(self._toolbar)
        toolbar_layout.setContentsMargins(12, 6, 12, 6)

        self._well_name_label = QLabel()
        self._well_name_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #1a202c;")
        toolbar_layout.addWidget(self._well_name_label)
        toolbar_layout.addStretch()

        self._export_btn = QPushButton("导出 PNG")
        self._export_btn.setFixedHeight(28)
        self._export_btn.setStyleSheet("""
            QPushButton {
                background: #3182ce; color: white;
                border: none; border-radius: 4px;
                padding: 0 12px; font-size: 13px;
            }
            QPushButton:hover { background: #2b6cb0; }
            QPushButton:pressed { background: #2c5282; }
        """)
        self._export_btn.clicked.connect(self._on_export)
        toolbar_layout.addWidget(self._export_btn)

        self._toolbar.setVisible(False)
        outer.addWidget(self._toolbar)

        # Page stack (fills remaining space)
        self._stack = QStackedWidget()

        self._placeholder = QLabel("点击地图上的井位查看测井图")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("font-size: 16px; color: #a0aec0;")
        self._stack.addWidget(self._placeholder)

        outer.addWidget(self._stack, 1)

        self._chart_widget: ChartEngine | None = None
        self._current_well: str | None = None

    def load_well(self, well_name: str) -> bool:
        """Load and display well log data for the given well name.

        Returns True if data was found, False otherwise.
        """
        if well_name == self._current_well and self._chart_widget:
            return True

        entry = _WELL_DATA.get(well_name)
        if entry is None:
            return False

        loader_fn, xls_path, config = entry

        # Remove previous chart
        if self._chart_widget:
            self._stack.removeWidget(self._chart_widget)
            self._chart_widget.deleteLater()
            self._chart_widget = None

        try:
            data = loader_fn(xls_path)
        except Exception as e:
            print(f"[WellLog] Failed to load {well_name}: {e}")
            return False

        data.well_name = well_name
        self._chart_widget = ChartEngine(data, config)
        self._stack.addWidget(self._chart_widget)
        self._stack.setCurrentWidget(self._chart_widget)
        self._current_well = well_name

        self._well_name_label.setText(well_name + " 测井图")
        self._toolbar.setVisible(True)
        return True

    def _on_export(self):
        if not self._chart_widget or not self._current_well:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出测井图",
            f"{self._current_well}_well_log.png",
            "PNG 图像 (*.png)",
        )
        if path:
            self._chart_widget.export(path)
