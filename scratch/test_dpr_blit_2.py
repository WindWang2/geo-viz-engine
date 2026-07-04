import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap, QPainter, QColor
from PySide6.QtCore import Qt

app = QApplication(sys.argv)

# Create a source pixmap of physical 200x200, DPR = 2.0 (logical 100x100).
# The top-left quadrant (physical 100x100, logical 50x50) is BLUE.
# The bottom-right quadrant (physical 100x100, logical 50x50) is RED.
pixmap = QPixmap(200, 200)
pixmap.setDevicePixelRatio(2.0)
pixmap.fill(Qt.transparent)

p = QPainter(pixmap)
p.fillRect(0, 0, 50, 50, Qt.blue)     # top-left
p.fillRect(50, 50, 50, 50, Qt.red)   # bottom-right
p.end()

print("Src physical width:", pixmap.width(), "height:", pixmap.height())

# We want to blit the top-left quadrant (logical 50x50, physical 100x100)
# to a target of logical 50x50, DPR = 1.0 (physical 50x50).
# We want the target to be completely blue.

# Let's try Case A: Passing logical coordinates (0, 0, 50, 50)
target_A = QPixmap(50, 50)
target_A.fill(Qt.green)
p_A = QPainter(target_A)
p_A.drawPixmap(0, 0, pixmap, 0, 0, 50, 50)
p_A.end()

# Let's try Case B: Passing physical coordinates (0, 0, 100, 100)
target_B = QPixmap(50, 50)
target_B.fill(Qt.green)
p_B = QPainter(target_B)
p_B.drawPixmap(0, 0, pixmap, 0, 0, 100, 100)
p_B.end()

img_A = target_A.toImage()
img_B = target_B.toImage()

print("Case A (Logical coordinates 50x50) pixel at (25, 25):", img_A.pixelColor(25, 25).name())
print("Case B (Physical coordinates 100x100) pixel at (25, 25):", img_B.pixelColor(25, 25).name())

# Let's also test when target has DPR = 2.0 (physical 100x100, logical 50x50)
# and painter target has DPR = 2.0.
target_C = QPixmap(100, 100)
target_C.setDevicePixelRatio(2.0)
target_C.fill(Qt.green)
p_C = QPainter(target_C)
p_C.drawPixmap(0, 0, pixmap, 0, 0, 50, 50)
p_C.end()

target_D = QPixmap(100, 100)
target_D.setDevicePixelRatio(2.0)
target_D.fill(Qt.green)
p_D = QPainter(target_D)
p_D.drawPixmap(0, 0, pixmap, 0, 0, 100, 100)
p_D.end()

img_C = target_C.toImage()
img_D = target_D.toImage()

print("Case C (Target DPR=2.0, Src Logical 50x50) pixel at (25, 25):", img_C.pixelColor(25, 25).name())
print("Case D (Target DPR=2.0, Src Physical 100x100) pixel at (25, 25):", img_D.pixelColor(25, 25).name())

sys.exit(0)
