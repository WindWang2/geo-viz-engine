import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtCore import Qt

app = QApplication(sys.argv)

# Create a pixmap of physical size 200x200, with DPR = 2.0 (logical size 100x100)
pixmap = QPixmap(200, 200)
pixmap.setDevicePixelRatio(2.0)
pixmap.fill(Qt.red)

# Draw on it to make sure it's colored
p = QPainter(pixmap)
p.fillRect(0, 0, 100, 100, Qt.blue)  # Draw logical 100x100
p.end()

print("Pixmap physical size:", pixmap.width(), "x", pixmap.height())
print("Pixmap logical size:", pixmap.width() / pixmap.devicePixelRatio(), "x", pixmap.height() / pixmap.devicePixelRatio())

# Let's create a target pixmap of physical size 100x100, DPR = 1.0 (logical size 100x100)
target = QPixmap(100, 100)
target.fill(Qt.green)

# Draw on target using QPainter
p2 = QPainter(target)

# Try drawing using physical coordinates as src rect
try:
    p2.drawPixmap(0, 0, pixmap, 0, 0, 200, 200)
    print("Drew with physical coordinates (0, 0, 200, 200) successfully")
except Exception as e:
    print("Error drawing with physical coordinates:", e)

p2.end()

# Let's inspect the target pixels.
# If we drew with physical coordinates (200x200) and drawPixmap treats them as logical,
# it would only draw the top-left portion or clip it.
# Let's see: if it treats it as logical, the logical width is 100.
# So if we copy (0, 0, 100, 100), it should copy the entire blue area.
target2 = QPixmap(100, 100)
target2.fill(Qt.green)
p3 = QPainter(target2)
p3.drawPixmap(0, 0, pixmap, 0, 0, 100, 100)
p3.end()

# Let's compare target (physical src) vs target2 (logical src)
img1 = target.toImage()
img2 = target2.toImage()

print("Pixel at (50, 50) using physical src:", img1.pixelColor(50, 50).name())
print("Pixel at (50, 50) using logical src:", img2.pixelColor(50, 50).name())
sys.exit(0)
