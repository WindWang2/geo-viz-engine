"""CRS helpers for the geoviz facade (Phase-2, T2 / #246).

The Workstation holds its own ``CoordinateReference`` (project / target /
display CRS + transform history) and calls ``coerce_to_project_crs`` at
draw-time to reproject well coordinates to the project CRS before feeding
the paleo_map Plate Carrée identity (``projection.py``). This module is the
pure helper; it carries no Workbench/Workstation model coupling (T10: the
``project/models.py`` CRS types are NOT promoted).

CNPC-relevant CRS codes are registered by default (Beijing 1954 / Xian 1980
/ CGCS2000) so domestic workflows are not forced through a WGS84 detour.
"""
from __future__ import annotations

from pyproj import CRS, Transformer
from pyproj.exceptions import CRSError

import contextvars

_project_crs_var: contextvars.ContextVar[str] = contextvars.ContextVar("project_crs", default="EPSG:4326")


def set_project_crs(crs: str) -> None:
    """Set the active project CRS (e.g. ``"EPSG:4547"`` for CGCS2000 / 3-degree Gauss-Kruger zone 39)."""
    # Validate eagerly so a bad code fails at setup, not at first paint.
    CRS.from_user_input(crs)
    _project_crs_var.set(crs)


def get_project_crs() -> str:
    """Return the currently active project CRS string."""
    return _project_crs_var.get()


# Known CRS catalog. EPSG codes for the CNPC-standard geodetic datums the
# resolution named, plus WGS84 / Web Mercator as universal defaults. The
# Gauss-Kruger zones are parametric (EPSG 4513-4534 for CGCS2000, 4491-4492
# for Beijing54); callers pass the exact EPSG code, this list is only the
# discovery/UX surface.
_KNOWN_CRS: list[tuple[str, str]] = [
    ("EPSG:4326", "WGS 84 (lng/lat)"),
    ("EPSG:4490", "CGCS2000 (lng/lat)"),
    ("EPSG:4610", "Beijing 1954 (lng/lat)"),
    ("EPSG:4612", "Xian 1980 (lng/lat)"),
    ("EPSG:3857", "Web Mercator (m)"),
    # CGCS2000 / Beijing 1954 / Xian 1980 are the primary CNPC datums; the
    # projected Gauss-Kruger zones are discovered by EPSG code, not enumerated.
]


def list_known_crs() -> list[str]:
    """Return the EPSG codes of CRS known to the facade (UX surface).

    Callers may pass any EPSG code the host's pyproj recognizes; this list
    is only for the Workstation's CRS picker and validation hints.
    """
    return [code for code, _label in _KNOWN_CRS]


def _crs_equivalent(a: str, b: str) -> bool:
    """True when two CRS strings denote the same coordinate system.

    Uses pyproj's ``CRS.equals`` semantics, which treats aliases
    (e.g. ``"WGS 84"`` vs ``"EPSG:4326"``) and case differences
    (``"epsg:4326"`` vs ``"EPSG:4326"``) as equivalent. Falls back to a
    case-insensitive string comparison when either side cannot be parsed.
    """
    if a == b:
        return True
    try:
        return CRS.from_user_input(a).equals(CRS.from_user_input(b))
    except CRSError:
        return a.lower() == b.lower()


def coerce_to_project_crs(coords, source_crs: str):
    """Reproject an (N, 2) array of (x, y) from ``source_crs`` to the project CRS.

    ``coords`` may be any array-like of shape (N, 2) or (2,) for a single
    point; returns a numpy ``ndarray`` of the same trailing shape in the
    project CRS. When ``source_crs`` equals the project CRS the input is
    returned as a float64 array unchanged (no transform). Equality is decided
    by pyproj ``CRS.equals`` (aliases / case-insensitive) rather than raw
    string comparison. Raises ``pyproj.exceptions.CRSError`` for unrecognized
    CRS strings.
    """
    import numpy as np

    coords = np.asarray(coords, dtype=np.float64)
    single = coords.ndim == 1
    if single:
        coords = coords.reshape(1, 2)

    target = get_project_crs()
    if _crs_equivalent(source_crs, target):
        out = coords
    else:
        transformer = Transformer.from_crs(source_crs, target, always_xy=True)
        xs, ys = transformer.transform(coords[:, 0], coords[:, 1])
        out = np.column_stack([xs, ys])

    return out[0] if single else out
