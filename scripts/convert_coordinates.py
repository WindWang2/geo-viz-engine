#!/usr/bin/env python3
"""Convert well coordinates from EPSG:2436 to WGS84 (EPSG:4326).

Reads the source CSV, transforms projected coordinates to geographic,
and writes a JSON file for the backend to serve.
"""
import csv
import json
import sys
from pathlib import Path

try:
    from pyproj import Transformer
except ImportError:
    print("pyproj is required. Install with: pip install pyproj")
    sys.exit(1)

SRC_CSV = Path("/mnt/c/Users/wangj.KEVIN/Downloads/可视化引擎-示例数据/工区内井名与随机坐标.csv")
OUT_JSON = Path(__file__).resolve().parent.parent / "data" / "well_coordinates.json"


def convert(csv_path: Path, out_path: Path) -> int:
    # EPSG:2436 = Beijing 1954 / 3-degree Gauss-Kruger CM 117E
    # CSV X = easting with zone prefix (20), Y = northing
    transformer = Transformer.from_crs("EPSG:2436", "EPSG:4326", always_xy=False)
    wells = []

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["WellName"].strip()
            easting = float(row["X"]) - 20000000  # strip zone prefix
            northing = float(row["Y"])
            lat, lon = transformer.transform(northing, easting)
            wells.append({
                "well_name": name,
                "longitude": round(lon, 6),
                "latitude": round(lat, 6),
            })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"wells": wells}, f, ensure_ascii=False, indent=2)

    print(f"Converted {len(wells)} wells -> {out_path}")
    return len(wells)


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else SRC_CSV
    convert(src, OUT_JSON)
