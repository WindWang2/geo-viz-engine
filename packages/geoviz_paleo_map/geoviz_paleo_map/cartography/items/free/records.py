"""Free-graphics record schema — the frozen cross-repo contract (spec §3.5).

Pure Python, **no Qt imports**: the host repo (paleo-workbench) and plain
``/usr/bin/python3`` must be able to verify the contract without PySide6.
geoviz item classes consume :func:`parse_record` output in their
``from_normalized`` constructors; the host reuses the same validation in its
persistence boundary.

Record shape (all geometry in paper-absolute mm)::

    {
      "id": "uuid4-string",
      "kind": "text|arrow|rect|ellipse|polygon|freehand|image|north_arrow|scale_bar",
      "style": {"stroke": "#000000", "fill": None, "width_mm": 0.3, "font_mm": 3.5},
      "geometry": {"x": 20.0, "y": 15.0, "w": 60.0, "h": 12.0}   # box kinds
                | {"points": [[x, y], ...]}                      # arrow/polygon/freehand
                | {"x": 20.0, "y": 15.0, "w": 60.0(optional)},   # text
      "props": {"text": "...", "align": "left"}                  # text
             | {"head_mm": 3.0}                                  # arrow
             | {"path": "plots/assets/<plot_id>/<uuid>.png"}     # image
             | {"denominator": 5000}                             # scale_bar
             | {},                                               # others,
    }
"""

from __future__ import annotations

import math
import re
import uuid

KINDS = (
    "text", "arrow", "rect", "ellipse", "polygon",
    "freehand", "image", "north_arrow", "scale_bar",
)

POINT_KINDS = ("arrow", "polygon", "freehand")
BOX_KINDS = ("rect", "ellipse", "image", "north_arrow", "scale_bar")

DEFAULT_STYLE = {"stroke": "#000000", "fill": None, "width_mm": 0.3, "font_mm": 3.5}

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def is_hex_colour(value) -> bool:
    """True for ``#rrggbb`` strings (case-insensitive)."""
    return isinstance(value, str) and bool(_HEX_RE.match(value))


def _finite(value):
    """float(value) if finite, else None."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def normalize_style(raw) -> dict | None:
    """Normalise a style dict; defaults fill gaps; None when invalid."""
    style = dict(DEFAULT_STYLE)
    if raw is None:
        return style
    if not isinstance(raw, dict):
        return None
    stroke = raw.get("stroke", style["stroke"])
    if stroke is not None and not is_hex_colour(stroke):
        return None
    fill = raw.get("fill")
    if fill is not None and not is_hex_colour(fill):
        return None
    width = _finite(raw.get("width_mm", style["width_mm"]))
    if width is None or width <= 0:
        return None
    font = _finite(raw.get("font_mm", style["font_mm"]))
    if font is None or font <= 0:
        return None
    style["stroke"] = stroke.lower() if isinstance(stroke, str) else stroke
    style["fill"] = fill.lower() if isinstance(fill, str) else None
    style["width_mm"] = width
    style["font_mm"] = font
    return style


def normalize_geometry(kind: str, raw) -> dict | None:
    """Normalise the geometry subset for ``kind``; None when invalid."""
    if not isinstance(raw, dict):
        return None
    if kind in POINT_KINDS:
        pts = raw.get("points")
        if not isinstance(pts, (list, tuple)):
            return None
        out = []
        for p in pts:
            if not isinstance(p, (list, tuple)) or len(p) != 2:
                return None
            x = _finite(p[0])
            y = _finite(p[1])
            if x is None or y is None:
                return None
            out.append([x, y])
        min_pts = 3 if kind == "polygon" else 2
        if len(out) < min_pts:
            return None
        return {"points": out}
    if kind == "text":
        x = _finite(raw.get("x"))
        y = _finite(raw.get("y"))
        if x is None or y is None:
            return None
        geom: dict = {"x": x, "y": y}
        if "w" in raw and raw["w"] is not None:
            w = _finite(raw["w"])
            if w is None or w <= 0:
                return None
            geom["w"] = w
        return geom
    if kind in BOX_KINDS:
        vals = [_finite(raw.get(k)) for k in ("x", "y", "w", "h")]
        if any(v is None for v in vals):
            return None
        x, y, w, h = vals
        if w <= 0 or h <= 0:
            return None
        return {"x": x, "y": y, "w": w, "h": h}
    return None


def normalize_props(kind: str, raw) -> dict | None:
    """Normalise kind-specific props; defaults fill gaps; None when invalid."""
    props: dict = {}
    raw = raw if isinstance(raw, dict) else {}
    if kind == "text":
        text = raw.get("text", "")
        if not isinstance(text, str):
            return None
        align = raw.get("align", "left")
        if align not in ("left", "center", "right"):
            return None
        props["text"] = text
        props["align"] = align
    elif kind == "arrow":
        head = _finite(raw.get("head_mm", 3.0))
        if head is None or head <= 0:
            return None
        props["head_mm"] = head
    elif kind == "image":
        path = raw.get("path")
        if not isinstance(path, str) or not path:
            return None
        props["path"] = path
    elif kind == "scale_bar":
        try:
            den = int(raw.get("denominator", 5000))
        except (TypeError, ValueError):
            return None
        if den <= 0:
            return None
        props["denominator"] = den
    return props


def parse_record(record) -> dict | None:
    """Validate + normalise a free-graphics record; None when malformed.

    Output always carries all five keys (``id``/``kind``/``style``/
    ``geometry``/``props``); a missing/blank ``id`` gets a fresh uuid4.
    """
    if not isinstance(record, dict):
        return None
    kind = record.get("kind")
    if kind not in KINDS:
        return None
    style = normalize_style(record.get("style"))
    geometry = normalize_geometry(kind, record.get("geometry"))
    props = normalize_props(kind, record.get("props"))
    if style is None or geometry is None or props is None:
        return None
    item_id = record.get("id")
    if not isinstance(item_id, str) or not item_id:
        item_id = str(uuid.uuid4())
    return {
        "id": item_id,
        "kind": kind,
        "style": style,
        "geometry": geometry,
        "props": props,
    }
