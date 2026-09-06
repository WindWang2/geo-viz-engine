"""Survey / bin-grid construction for Local Rectangular well–seismic alignment."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from geoviz_seismic.models import BinGridGeometry

# Corner tuple: (inline, crossline, x, y)
Corner = tuple[float, float, float, float]


@dataclass
class SurveySpec:
    """Survey geometry mapping absolute IL/XL ↔ Local Rectangular XY."""

    bin_grid: BinGridGeometry
    iline_start: int
    iline_step: int
    xline_start: int
    xline_step: int
    n_inlines: int
    n_crosslines: int
    n_samples: int
    dt_ms: float
    t0_ms: float = 0.0

    def xy_to_il_xl(
        self, x: float | np.ndarray, y: float | np.ndarray
    ) -> tuple[float, float] | tuple[np.ndarray, np.ndarray]:
        bg = self.bin_grid
        x_arr = np.asarray(x, dtype=np.float64)
        y_arr = np.asarray(y, dtype=np.float64)
        dx = x_arr - bg.x_origin
        dy = y_arr - bg.y_origin
        az = math.radians(bg.il_azimuth_deg)
        cos_a, sin_a = math.cos(az), math.sin(az)
        il_frac = (-dx * sin_a + dy * cos_a) / bg.il_spacing_m
        xl_frac = (dx * cos_a + dy * sin_a) / bg.xl_spacing_m
        il = self.iline_start + il_frac * self.iline_step
        xl = self.xline_start + xl_frac * self.xline_step
        if x_arr.ndim == 0:
            return float(il), float(xl)
        return il, xl

    def il_xl_to_xy(self, iline: float, xline: float) -> tuple[float, float]:
        il_step = self.iline_step if self.iline_step != 0 else 1
        xl_step = self.xline_step if self.xline_step != 0 else 1
        il_frac = (iline - self.iline_start) / il_step
        xl_frac = (xline - self.xline_start) / xl_step
        return self.bin_grid.il_xl_to_xy(il_frac, xl_frac)


def survey_from_corners(
    p1: Corner,
    p2: Corner,
    p3: Corner,
    *,
    n_samples: int,
    dt_ms: float,
    t0_ms: float = 0.0,
    iline_step: int | None = None,
    xline_step: int | None = None,
    n_inlines: int | None = None,
    n_crosslines: int | None = None,
) -> SurveySpec:
    """Build a survey from three grid corners (horizon/SEGY text-header style).

    * **p1**: origin corner (il0, xl0, x0, y0)
    * **p2**: same inline as p1, opposite crossline (il0, xl1, x1, y1)
    * **p3**: same crossline as p2, opposite inline (il1, xl1, x2, y2)

    Line numbering defaults to step ±1 between the corner numbers. Real SEGY
    often numbers lines with a larger step (e.g. IL 1000, 1002, …): pass the
    loader's actual ``iline_step``/``xline_step`` and counts so the grid has
    the right number of bins — deriving them from the corner numbers alone
    would double-count the axis and misregister every IL/XL↔XY conversion.
    """
    il0, xl0, x0, y0 = (float(v) for v in p1)
    il0b, xl1, x1, y1 = (float(v) for v in p2)
    il1, xl1b, x2, y2 = (float(v) for v in p3)

    if abs(il0 - il0b) > 1e-6:
        raise ValueError("p1 and p2 must share the same inline number")
    if abs(xl1 - xl1b) > 1e-6:
        raise ValueError("p2 and p3 must share the same crossline number")

    def _resolve(
        corner_span: float,
        step: int | None,
        count: int | None,
        label: str,
    ) -> tuple[int, int]:
        if step is None:
            step = 1 if corner_span >= 0 else -1
        step = int(step) or 1
        if count is None:
            count = int(round(abs(corner_span))) + 1
        count = max(1, int(count))
        span = (count - 1) * abs(step)
        if abs(int(round(abs(corner_span))) - span) > 1e-6 and step != 0:
            raise ValueError(
                f"{label}: corner numbers span {corner_span:g} but "
                f"{count} lines x step {step} span {span}"
            )
        if (corner_span < 0) != (step < 0) and corner_span != 0:
            step = -step
        return step, count

    iline_step, n_il = _resolve(il1 - il0, iline_step, n_inlines, "inline")
    xline_step, n_xl = _resolve(xl1 - xl0, xline_step, n_crosslines, "crossline")

    # Distance along XL edge (p1→p2) and IL edge (p2→p3): the physical edge
    # length spans (count-1) bins regardless of the line-number step.
    xl_len = float(np_hypot(x1 - x0, y1 - y0))
    il_len = float(np_hypot(x2 - x1, y2 - y1))
    # V6 §9 (P0): all-zero/degenerate SourceX/Y must not become a
    # valid-looking survey. Fabricating 1 m bins at the origin made the
    # footprint look trustworthy when the source geometry was actually
    # absent — refuse instead.
    if xl_len <= 1e-6 or il_len <= 1e-6:
        raise ValueError(
            "survey corners carry no coordinate extent "
            f"(XL edge {xl_len:g} m, IL edge {il_len:g} m; SourceX/Y all zero "
            "or missing) — refusing to fabricate survey geometry"
        )
    xl_spacing = xl_len / (n_xl - 1) if n_xl > 1 else 1.0
    il_spacing = il_len / (n_il - 1) if n_il > 1 else 1.0

    # Azimuth of inline axis from north (+Y), clockwise (BinGridGeometry convention).
    # IL direction: p2→p3. For classic IL=+Y/XL=+X, az=0.
    # BinGrid with positive spacing: IL unit = (-sin az, cos az).
    # When IL is along +X, az=90 would map positive spacing to -X; flip spacing
    # signs so corner vectors and BinGrid stay consistent (wayfinder #84).
    il_dx = x2 - x1
    il_dy = y2 - y1
    az_deg = float(np_degrees(np_atan2(il_dx, il_dy))) if (il_dx or il_dy) else 0.0
    # BinGrid with positive spacing: IL unit = (-sin az, cos az), XL = (cos az, sin az).
    # Flip spacing signs when corners require the opposite direction (e.g. IL along +X).
    sin_a = np_sin(az_deg)
    cos_a = np_cos(az_deg)
    pred_il = (-sin_a, cos_a)
    pred_xl = (cos_a, sin_a)
    des_il = (il_dx, il_dy)
    des_xl = (x1 - x0, y1 - y0)
    if pred_il[0] * des_il[0] + pred_il[1] * des_il[1] < 0:
        il_spacing = -il_spacing
    if pred_xl[0] * des_xl[0] + pred_xl[1] * des_xl[1] < 0:
        xl_spacing = -xl_spacing

    bin_grid = BinGridGeometry(
        x_origin=x0,
        y_origin=y0,
        il_azimuth_deg=az_deg,
        il_spacing_m=il_spacing,
        xl_spacing_m=xl_spacing,
    )

    return SurveySpec(
        bin_grid=bin_grid,
        iline_start=int(round(il0)),
        iline_step=iline_step,
        xline_start=int(round(xl0)),
        xline_step=xline_step,
        n_inlines=n_il,
        n_crosslines=n_xl,
        n_samples=int(n_samples),
        dt_ms=float(dt_ms),
        t0_ms=float(t0_ms),
    )


def np_hypot(a: float, b: float) -> float:
    return (a * a + b * b) ** 0.5


def np_atan2(y: float, x: float) -> float:
    import math

    return math.atan2(y, x)


def np_degrees(rad: float) -> float:
    import math

    return math.degrees(rad)


def np_sin(deg: float) -> float:
    import math

    return math.sin(math.radians(deg))


def np_cos(deg: float) -> float:
    import math

    return math.cos(math.radians(deg))
