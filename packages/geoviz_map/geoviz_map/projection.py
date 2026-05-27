"""Web Mercator projection (matches MapLibre GL internal projection)."""
import math

R_EARTH = 6378137.0  # WGS84 / Web Mercator earth radius (meters)
MAX_LAT = 85.05112878  # Web Mercator latitude clamp


def lnglat_to_world(lng: float, lat: float) -> tuple[float, float]:
    """Convert lng/lat (degrees) to Web Mercator world coordinates (meters)."""
    if not -MAX_LAT <= lat <= MAX_LAT:
        raise ValueError(f"latitude {lat} outside Web Mercator range ±{MAX_LAT}")
    x = math.radians(lng) * R_EARTH
    y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * R_EARTH
    return x, y


def world_to_lnglat(x: float, y: float) -> tuple[float, float]:
    """Inverse of lnglat_to_world."""
    lng = math.degrees(x / R_EARTH)
    lat = math.degrees(2 * math.atan(math.exp(y / R_EARTH)) - math.pi / 2)
    return lng, lat
