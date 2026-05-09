import os
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFileDialog, QStackedWidget, QMessageBox
)

from src.renderers.paleo_map_renderer import PaleoMapRenderer


class PaleoMapPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Use a QStackedWidget to toggle between Empty State and Map
        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)

        # 1. Empty State
        self.empty_widget = QWidget()
        self.empty_widget.setStyleSheet("background: #f7fafc;")
        empty_layout = QVBoxLayout(self.empty_widget)
        
        drop_area = QLabel("拖拽 Paleogeography GeoJSON 文件到此处\n或点击加载")
        drop_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_area.setStyleSheet("""
            QLabel {
                border: 2px dashed #cbd5e1;
                border-radius: 8px;
                background: #ffffff;
                color: #64748b;
                font-size: 16px;
                padding: 40px;
            }
            QLabel:hover {
                border-color: #3182ce;
                color: #3182ce;
                background: #ebf8ff;
            }
        """)
        # Make the drop area clickable
        drop_area.mousePressEvent = lambda e: self._on_load_clicked()
        
        empty_layout.addStretch()
        empty_layout.addWidget(drop_area, 0, Qt.AlignmentFlag.AlignCenter)
        empty_layout.addStretch()
        
        self.stack.addWidget(self.empty_widget)

        # 2. Map State (Full-Bleed with Floating Controls)
        self.map_container = QWidget()
        map_layout = QVBoxLayout(self.map_container)
        map_layout.setContentsMargins(0, 0, 0, 0)
        map_layout.setSpacing(0)

        self.map_view = PaleoMapRenderer(self)
        map_layout.addWidget(self.map_view)

        # Floating Toolbar (Overlay)
        # In PySide6, floating overlays can be achieved by parenting to the container and positioning manually, 
        # or using a layout on top. For simplicity, we use an absolute positioned widget over map_container.
        self.floating_toolbar = QWidget(self.map_container)
        self.floating_toolbar.setStyleSheet("""
            QWidget {
                background: rgba(255, 255, 255, 0.9);
                border: 1px solid #e2e8f0;
                border-radius: 6px;
            }
        """)
        float_layout = QHBoxLayout(self.floating_toolbar)
        float_layout.setContentsMargins(8, 8, 8, 8)
        
        self.load_btn = QPushButton("重新加载")
        self.load_btn.setStyleSheet("""
            QPushButton {
                background: #edf2f7; color: #1e293b;
                border: 1px solid #cbd5e1; border-radius: 4px;
                padding: 6px 12px; font-size: 13px; font-weight: bold;
            }
            QPushButton:hover { background: #e2e8f0; }
        """)
        self.load_btn.clicked.connect(self._on_load_clicked)

        self.export_btn = QPushButton("导出图片")
        self.export_btn.setStyleSheet("""
            QPushButton {
                background: #3182ce; color: white;
                border: none; border-radius: 4px;
                padding: 6px 12px; font-size: 13px; font-weight: bold;
            }
            QPushButton:hover { background: #2b6cb0; }
            QPushButton:pressed { background: #2c5282; }
        """)
        self.export_btn.clicked.connect(self._on_export_clicked)

        float_layout.addWidget(self.load_btn)
        float_layout.addWidget(self.export_btn)
        
        self.floating_toolbar.move(20, 20)
        self.floating_toolbar.show()

        self.stack.addWidget(self.map_container)
        self.stack.setCurrentWidget(self.empty_widget)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Keep floating toolbar in top-left
        if hasattr(self, 'floating_toolbar'):
            self.floating_toolbar.move(20, 20)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith(('.json', '.geojson')):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            self._load_file(file_path)

    def _on_load_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择古地理 GeoJSON 文件", "", "GeoJSON 文件 (*.json *.geojson)"
        )
        if file_path:
            self._load_file(file_path)

    def _load_file(self, file_path: str):
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "错误", "文件不存在！")
            return
            
        try:
            self.map_view.load_geojson(file_path)
            self.stack.setCurrentWidget(self.map_container)
        except Exception as e:
            QMessageBox.critical(self, "加载失败", f"无法加载地图数据:\n{e}")

    def _on_export_clicked(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出地图", "paleomap.png", "PNG 图片 (*.png)"
        )
        if not path:
            return

        if not path.lower().endswith(".png"):
            path += ".png"
            
        pixmap = self.map_view.grab()
        pixmap.save(path, "PNG")
