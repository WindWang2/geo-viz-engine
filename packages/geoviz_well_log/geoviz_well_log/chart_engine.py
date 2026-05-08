import json
import os
import base64
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtCore import QObject, Slot, Signal

class Bridge(QObject):
    # 此信号由 Web 准备就绪时发出
    ready = Signal()
    # 接收导出的 SVG
    svg_received = Signal(str)
    # 接收深度缩放变化
    zoom_changed = Signal(float, float)
    # 接收点击区间事件
    interval_clicked = Signal(float, float)

    @Slot()
    def web_ready(self):
        self.ready.emit()

    @Slot(float, float)
    def on_zoom(self, start, end):
        self.zoom_changed.emit(start, end)

    @Slot(float, float)
    def on_click(self, top, bottom):
        self.interval_clicked.emit(top, bottom)

    @Slot(str)
    def receive_svg(self, svg_str: str):
        self.svg_received.emit(svg_str)

    @Slot(str)
    def log(self, message: str):
        print(message)

class ChartEngine(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._well_name = ""
        self._flatten_offset = 0.0
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.view = QWebEngineView()
        self.layout.addWidget(self.view)
        
        # 配置 WebChannel
        self.channel = QWebChannel()
        self.bridge = Bridge()
        self.channel.registerObject("bridge", self.bridge)
        self.view.page().setWebChannel(self.channel)
        
        self._is_web_ready = False
        self._js_queue = []
        self._last_data_json = None
        self.bridge.ready.connect(self._on_web_ready)

        # Restrict context menu to prevent manual reloading resets
        from PySide6.QtCore import Qt
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        
        # 加载本地打包好的页面
        # 路径现在指向包内部的 web_dist 目录
        base_dir = os.path.dirname(__file__)
        dist_path = os.path.abspath(os.path.join(base_dir, "web_dist", "index.html"))
        
        if os.path.exists(dist_path):
            self.view.load(f"file://{dist_path}")
        else:
            print(f"Warning: ECharts dist not found at {dist_path}")

    def _build_patterns_json(self) -> str:
        """Build a JSON object mapping pattern IDs to data URLs."""
        base_dir = os.path.dirname(__file__)
        patterns_dir = os.path.abspath(os.path.join(base_dir, "assets", "patterns"))
        patterns = {}
        if not os.path.exists(patterns_dir):
            return "{}"
        
        for filename in os.listdir(patterns_dir):
            if filename.endswith(".svg"):
                # e.g. "sand_flat.svg" → "sand-flat"
                pattern_id = filename[:-4].replace("_", "-")
                path = os.path.join(patterns_dir, filename)
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                patterns[pattern_id] = f"data:image/svg+xml;base64,{b64}"
        
        return json.dumps(patterns)

    @Slot()
    def _on_web_ready(self):
        self._is_web_ready = True
        # Step 1: Register all patterns — JS will pre-load Image objects
        # and call onPatternsReady() when done.
        patterns_json = self._build_patterns_json()
        self.view.page().runJavaScript(f"window.registerPatterns({patterns_json});")
        # Step 2: Run any queued JS commands (including render_data calls)
        for js in self._js_queue:
            self.view.page().runJavaScript(js)
        self._js_queue.clear()

        # Step 3: If we had loaded data before, re-render it upon reload
        if self._last_data_json:
            self.view.page().runJavaScript(f"window.geoviz.render({self._last_data_json});")

    def _safe_run_js(self, js: str):
        if self._is_web_ready:
            self.view.page().runJavaScript(js)
        else:
            self._js_queue.append(js)
            
    def render_data(self, well_data_json: str):
        self._last_data_json = well_data_json
        # 调用 JS 函数 render()
        self._safe_run_js(f"window.geoviz.render({well_data_json});")

    def render_well_log_data(self, data, offset: float = 0.0):
        """
        Convenience method to render from a WellLogData model directly.
        """
        from .utils import build_default_payload
        payload = build_default_payload(data, offset)
        self.render_data(json.dumps(payload))
        
    def export_svg(self):
        # 调用 JS，然后把返回值发给 Python
        js = """
        var svgStr = window.exportChartToSvg();
        bridge.receive_svg(svgStr);
        """
        self._safe_run_js(js)
