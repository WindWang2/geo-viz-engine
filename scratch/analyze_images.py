from PySide6.QtGui import QImage, QColor

def main():
    a = QImage("scratch/current_map.png")
    b = QImage("tests/golden/map_canvas_default.png")
    
    print(f"Image A: {a.width()}x{a.height()}, format={a.format()}")
    print(f"Image B: {b.width()}x{b.height()}, format={b.format()}")
    
    # Sample a few pixels from the center of the image to see what colors are present
    print("\nCenter 5x5 pixels color comparison (x, y) -> Color A vs Color B:")
    cx, cy = a.width() // 2, a.height() // 2
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            x, y = cx + dx, cy + dy
            ca = a.pixelColor(x, y)
            cb = b.pixelColor(x, y)
            print(f"({x}, {y}) -> A: {ca.name()} | B: {cb.name()}")
            
    # Check what unique colors are present in both images
    colors_a = set()
    colors_b = set()
    for y in range(0, a.height(), 10):
        for x in range(0, a.width(), 10):
            colors_a.add(a.pixelColor(x, y).name())
            colors_b.add(b.pixelColor(x, y).name())
            
    print(f"\nUnique colors sampled in A (first 10): {sorted(list(colors_a))[:10]}")
    print(f"Unique colors sampled in B (first 10): {sorted(list(colors_b))[:10]}")

if __name__ == "__main__":
    main()
