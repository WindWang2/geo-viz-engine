from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPolygonF, QColor, QPen
from PySide6.QtCore import QPointF, Qt

class ConnectionOverlay(QWidget):
    def __init__(self, parent, engines):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._engines = engines
        self._links = [] # List of CorrelationLink objects
        self._depth_cache = {} # Map (engine, depth) -> y_pixel

    def set_links(self, links):
        self._links = links
        self.update()

    def update_depth_cache(self, engine, depth, y_pixel):
        self._depth_cache[(engine, depth)] = y_pixel
        self.update()

    def paintEvent(self, event):
        if not self._links or len(self._engines) < 2:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        drawn_count = 0
        for link in self._links:
            try:
                src_engine = next((e for e in self._engines if getattr(e, '_well_name', '') == link.source_well), None)
                tgt_engine = next((e for e in self._engines if getattr(e, '_well_name', '') == link.target_well), None)
                
                if not src_engine or not tgt_engine:
                    continue

                parts_s = link.source_interval_id.split('_')
                parts_t = link.target_interval_id.split('_')
                if len(parts_s) < 2 or len(parts_t) < 2: continue
                
                s_top, s_bot = parts_s[0], parts_s[1]
                t_top, t_bot = parts_t[0], parts_t[1]

                # Get coordinates relative to the overlay parent (the container)
                src_rect = src_engine.geometry()
                tgt_rect = tgt_engine.geometry()
                
                y_s_top = self._depth_cache.get((src_engine, s_top))
                y_s_bot = self._depth_cache.get((src_engine, s_bot))
                y_t_top = self._depth_cache.get((tgt_engine, t_top))
                y_t_bot = self._depth_cache.get((tgt_engine, t_bot))

                if None in (y_s_top, y_s_bot, y_t_top, y_t_bot):
                    continue

                # Polygon points
                # Source well right edge to Target well left edge
                x_s = src_rect.right()
                x_t = tgt_rect.left()
                
                poly = QPolygonF([
                    QPointF(x_s, src_rect.y() + y_s_top),
                    QPointF(x_t, tgt_rect.y() + y_t_top),
                    QPointF(x_t, tgt_rect.y() + y_t_bot),
                    QPointF(x_s, src_rect.y() + y_s_bot)
                ])

                color = QColor(link.color)
                color.setAlpha(120) 
                painter.setBrush(color)
                painter.setPen(QPen(QColor(link.color).darker(110), 1, Qt.PenStyle.SolidLine))
                painter.drawPolygon(poly)
                drawn_count += 1

            except Exception as e:
                print(f"[Overlay] Draw error: {e}")
        
        # print(f"[Overlay] Painted {drawn_count} correlation polygons out of {len(self._links)} links")
