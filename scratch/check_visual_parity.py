import json
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage
from geoviz_map import MapCanvas, ReferenceLabel, WellMarker

DATA_DIR = Path("data")
GOLDEN = Path("tests/golden/map_canvas_default.png")

def _build_canvas() -> MapCanvas:
    world = json.loads((DATA_DIR / "world.json").read_text(encoding="utf-8"))
    china = json.loads((DATA_DIR / "china_provinces.json").read_text(encoding="utf-8"))
    coords = json.loads((DATA_DIR / "well_coordinates.json").read_text(encoding="utf-8"))
    wells = [
        WellMarker(
            name=w.get("well_name", w.get("name", "")),
            lng=w["longitude"],
            lat=w["latitude"],
            color="#ef4444",
            has_data=True,
        )
        for w in coords["wells"]
    ]
    labels = [
        ReferenceLabel(name="香港", lng=114.17, lat=22.32, kind="city"),
        ReferenceLabel(name="南海", lng=115.5, lat=20.2, kind="sea"),
    ]
    return MapCanvas(
        wells=wells,
        world_geojson=world,
        china_geojson=china,
        reference_labels=labels,
        initial_center=(115.14, 21.31),
        initial_zoom=8.0,
    )

def main():
    app = QApplication.instance() or QApplication([])
    widget = _build_canvas()
    widget.resize(1200, 800)
    widget.show()
    QApplication.processEvents()
    
    # Grab
    img = widget.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32)
    img.save("scratch/current_map.png")
    print("Saved current map image to scratch/current_map.png")
    
    golden = QImage(str(GOLDEN))
    print(f"Current image size: {img.size()}, DPR: {img.devicePixelRatio()}")
    print(f"Golden image size: {golden.size()}, DPR: {golden.devicePixelRatio()}")

if __name__ == "__main__":
    main()
