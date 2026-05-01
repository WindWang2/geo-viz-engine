import json
import os
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtCore import QObject, Slot, Signal

class Bridge(QObject):
    # 此信号由 Web 准备就绪时发出
    ready = Signal()
    # 接收导出的 SVG
    svg_received = Signal(str)

    @Slot()
    def web_ready(self):
        self.ready.emit()

    @Slot(str)
    def receive_svg(self, svg_str: str):
        self.svg_received.emit(svg_str)

class ChartEngine(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.view = QWebEngineView()
        self.layout.addWidget(self.view)
        
        # 配置 WebChannel
        self.channel = QWebChannel()
        self.bridge = Bridge()
        self.channel.registerObject("bridge", self.bridge)
        self.view.page().setWebChannel(self.channel)
        
        # 加载本地打包好的页面
        # 注意: 构建产物在 src-echarts/dist 中
        dist_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../src-echarts/dist/index.html"))
        if os.path.exists(dist_path):
            self.view.load(f"file://{dist_path}")
        else:
            print(f"Warning: ECharts dist not found at {dist_path}")
            
    def render_data(self, well_data_json: str):
        # 调用 JS 函数 render()
        self.view.page().runJavaScript(f"window.geoviz.render({well_data_json});")
        
    def export_svg(self):
        # 调用 JS，然后把返回值发给 Python
        js = """
        var svgStr = window.exportChartToSvg();
        bridge.receive_svg(svgStr);
        """
        self.view.page().runJavaScript(js)
