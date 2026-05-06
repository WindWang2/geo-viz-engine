from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtCore import Qt, QPointF, QRectF

class LocationMapWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.wells = [] # List of (lon, lat, name)
        self.setFixedSize(200, 200)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        
    def set_wells(self, wells_data):
        """
        wells_data: list of (lon, lat, name)
        """
        self.wells = wells_data
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw background frame
        painter.setBrush(QColor(255, 255, 255, 200))
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 5, 5)

        if not self.wells:
            painter.setPen(Qt.gray)
            painter.drawText(self.rect(), Qt.AlignCenter, "No Wells")
            return

        # Get bounds
        lons = [w[0] for w in self.wells]
        lats = [w[1] for w in self.wells]
        
        min_lon, max_lon = min(lons), max(lons)
        min_lat, max_lat = min(lats), max(lats)
        
        # Add padding
        padding = 0.1
        if max_lon == min_lon:
            min_lon -= 0.01
            max_lon += 0.01
        if max_lat == min_lat:
            min_lat -= 0.01
            max_lat += 0.01
            
        lon_range = max_lon - min_lon
        lat_range = max_lat - min_lat
        
        # Adjust range to maintain aspect ratio (roughly, assuming small area)
        # For simplicity, we'll just use the padding
        margin = 20
        draw_rect = self.rect().adjusted(margin, margin, -margin, -margin)
        
        def to_screen(lon, lat):
            x = draw_rect.left() + (lon - min_lon) / lon_range * draw_rect.width()
            # Y is inverted in screen coordinates
            y = draw_rect.bottom() - (lat - min_lat) / lat_range * draw_rect.height()
            return QPointF(x, y)

        points = [to_screen(lon, lat) for lon, lat, name in self.wells]

        # Draw connection lines
        if len(points) > 1:
            painter.setPen(QPen(QColor(100, 100, 100, 150), 1, Qt.DashLine))
            for i in range(len(points) - 1):
                painter.drawLine(points[i], points[i+1])

        # Draw well dots and labels
        font = QFont("Arial", 8)
        painter.setFont(font)
        
        for i, (lon, lat, name) in enumerate(self.wells):
            p = points[i]
            
            # Dot
            painter.setBrush(QColor(31, 41, 55)) # Gray-800
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(p, 3, 3)
            
            # Label
            painter.setPen(QColor(31, 41, 55))
            painter.drawText(p.x() + 5, p.y() + 5, name)
