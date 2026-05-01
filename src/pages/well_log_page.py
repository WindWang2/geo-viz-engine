import json
import math
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QFileDialog,
)
from src.data.well_registry import get_well_data
from src.renderers.well_log.chart_engine import ChartEngine


class WellLogPage(QWidget):
    # Mapping Chinese lithology names to SVG pattern IDs defined in index.html
    LITHOLOGY_MAP = {
        "砂岩": "sandstone",
        "泥岩": "mudstone",
        "灰岩": "limestone",
        "白云岩": "dolomite",
        "页岩": "shale",
        "粉砂岩": "siltstone",
    }

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

        self._export_btn = QPushButton("导出")
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

        entry = get_well_data(well_name)
        if entry is None:
            return False

        loader_fn, xls_path, config = entry

        # Remove previous chart
        if self._chart_widget:
            self._stack.removeWidget(self._chart_widget)
            self._chart_widget.deleteLater()
            self._chart_widget = None

        try:
            data = loader_fn(xls_path, well_name=well_name)
        except Exception as e:
            print(f"[WellLog] Failed to load {well_name}: {e}")
            return False

        self._chart_widget = ChartEngine(self)
        # Connect signal once during creation
        self._chart_widget.bridge.svg_received.connect(self._save_svg_to_disk)
        
        self._stack.addWidget(self._chart_widget)
        self._stack.setCurrentWidget(self._chart_widget)
        self._current_well = well_name
        
        # 构建 ECharts Payload
        payload = {
            "metadata": {
                "wellName": data.well_name,
                "topDepth": data.top_depth,
                "bottomDepth": data.bottom_depth
            },
            "tracks": []
        }
        
        # 映射曲线 (CurveTracks)
        for curve in data.curves:
            # zip depth and values into [[d, v], ...]
            curve_data = []
            for d, v in zip(curve.depth, curve.values):
                # Convert NaN to None so it becomes null in JSON
                val = v if not math.isnan(v) else None
                curve_data.append([d, val])

            payload["tracks"].append({
                "type": "CurveTrack",
                "series": [
                    {
                        "name": curve.name,
                        "color": curve.color or "#3182ce",
                        "data": curve_data
                    }
                ]
            })
            
        # 映射岩性 (LithologyTracks) - Unify sources
        lithology_data = []
        if hasattr(data, 'lithology') and data.lithology:
            lithology_data.extend(data.lithology)
        if data.intervals and data.intervals.lithology:
            lithology_data.extend(data.intervals.lithology)

        if lithology_data:
            payload["tracks"].append({
                "type": "LithologyTrack",
                "data": [
                    {
                        "top": item.top,
                        "bottom": item.bottom,
                        "lithology": self.LITHOLOGY_MAP.get(item.name, ""),
                        "description": item.name,
                        "color": getattr(item, 'color', "#cbd5e0")
                    } for item in lithology_data
                ]
            })

        self._chart_widget.render_data(json.dumps(payload))

        self._well_name_label.setText(well_name + " 测井图")
        self._toolbar.setVisible(True)
        return True

    def _on_export(self):
        if not self._chart_widget or not self._current_well:
            return
        # Trigger JS export; the signal was connected in load_well
        self._chart_widget.export_svg()
        
    def _save_svg_to_disk(self, svg_str: str):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出测井图",
            f"{self._current_well}_well_log.svg",
            "SVG 矢量 (*.svg)"
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(svg_str)
            except Exception as e:
                print(f"[WellLog] Failed to save SVG: {e}")
