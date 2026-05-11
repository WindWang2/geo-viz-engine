from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


class PaleoDataLoader:
    """Load paleogeography data from GeoJSON or CSV/Excel files.

    Returns a dict mapping period names to lists of GeoJSON Feature dicts.
    """

    def __init__(self, path: str):
        self._path = path

    @staticmethod
    def detect_format(path: str) -> str | None:
        ext = Path(path).suffix.lower()
        if ext in (".csv",):
            return "csv"
        if ext in (".xlsx", ".xls"):
            return "csv"
        if ext in (".json", ".geojson"):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data.get("type") in (
                    "FeatureCollection",
                    "Feature",
                ):
                    return "geojson"
            except (json.JSONDecodeError, OSError):
                pass
        return None

    def load(self) -> dict[str, list[dict]]:
        fmt = self.detect_format(self._path)
        if fmt == "csv":
            return self._load_csv()
        if fmt == "geojson":
            return self._load_geojson()
        raise ValueError(
            f"Unsupported file format: {self._path}. "
            f"Expected GeoJSON (.json/.geojson) or CSV (.csv/.xlsx)."
        )

    def _load_csv(self) -> dict[str, list[dict]]:
        ext = Path(self._path).suffix.lower()
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(self._path)
        else:
            df = pd.read_csv(self._path)

        result: dict[str, list[dict]] = {}
        for _, row in df.iterrows():
            period = str(row.get("period", Path(self._path).stem))
            facies = str(row.get("facies", ""))
            boundary = row.get("boundary_type", None)
            name = str(row.get("name", facies))

            # Build geometry
            if "geometry" in row and pd.notna(row["geometry"]):
                from shapely import from_wkt

                geom = from_wkt(str(row["geometry"]))
                coordinates = json.loads(
                    json.dumps(geom.__geo_interface__["coordinates"])
                )
                geom_type = geom.geom_type
            elif all(c in row for c in ("lon_min", "lon_max", "lat_min", "lat_max")):
                lon_min = float(row["lon_min"])
                lon_max = float(row["lon_max"])
                lat_min = float(row["lat_min"])
                lat_max = float(row["lat_max"])
                coordinates = [
                    [
                        [lon_min, lat_min],
                        [lon_max, lat_min],
                        [lon_max, lat_max],
                        [lon_min, lat_max],
                        [lon_min, lat_min],
                    ]
                ]
                geom_type = "Polygon"
            else:
                raise ValueError(
                    f"Row missing geometry: need either 'geometry' (WKT) or "
                    f"'lon_min,lon_max,lat_min,lat_max' columns."
                )

            feature = {
                "type": "Feature",
                "properties": {
                    "facies": facies,
                    "name": name,
                },
                "geometry": {"type": geom_type, "coordinates": coordinates},
            }
            if pd.notna(boundary):
                feature["properties"]["boundary_type"] = str(boundary)

            result.setdefault(period, []).append(feature)

        return result

    def _load_geojson(self) -> dict[str, list[dict]]:
        with open(self._path, encoding="utf-8") as f:
            data = json.load(f)

        features = data.get("features", [])
        if data.get("type") == "Feature":
            features = [data]

        stem = Path(self._path).stem
        result: dict[str, list[dict]] = {}
        for feat in features:
            props = feat.get("properties", {}) or {}
            period = props.get("period", stem)
            result.setdefault(period, []).append(feat)

        return result
