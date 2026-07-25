"""Survey / bin-grid construction for Local Rectangular well–seismic alignment."""

from __future__ import annotations

from dataclasses import dataclass

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

    def xy_to_il_xl(self, x: float, y: float) -> tuple[float, float]:
        il_frac, xl_frac = self.bin_grid.xy_to_il_xl(x, y)
        return (
            self.iline_start + il_frac * self.iline_step,
            self.xline_start + xl_frac * self.xline_step,
        )

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
) -> SurveySpec:
    """Build a survey from three grid corners (horizon/SEGY text-header style).

    * **p1**: origin corner (il0, xl0, x0, y0)
    * **p2**: same inline as p1, opposite crossline (il0, xl1, x1, y1)
    * **p3**: same crossline as p2, opposite inline (il1, xl1, x2, y2)
    """
    il0, xl0, x0, y0 = (float(v) for v in p1)
    il0b, xl1, x1, y1 = (float(v) for v in p2)
    il1, xl1b, x2, y2 = (float(v) for v in p3)

    if abs(il0 - il0b) > 1e-6:
        raise ValueError("p1 and p2 must share the same inline number")
    if abs(xl1 - xl1b) > 1e-6:
        raise ValueError("p2 and p3 must share the same crossline number")

    n_il_steps = max(1, int(round(abs(il1 - il0))))
    n_xl_steps = max(1, int(round(abs(xl1 - xl0))))
    iline_step = 1 if il1 >= il0 else -1
    xline_step = 1 if xl1 >= xl0 else -1

    # Distance along XL edge (p1→p2) and IL edge (p2→p3)
    xl_len = float(np_hypot(x1 - x0, y1 - y0))
    il_len = float(np_hypot(x2 - x1, y2 - y1))
    xl_spacing = xl_len / n_xl_steps if n_xl_steps else 1.0
    il_spacing = il_len / n_il_steps if n_il_steps else 1.0

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
        n_inlines=n_il_steps + 1,
        n_crosslines=n_xl_steps + 1,
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
