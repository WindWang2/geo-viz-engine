from __future__ import annotations

import time
from typing import List

import numpy as np

from app.models.well_log import CurveData, WellLogData

# Module-level in-memory cache: well_id -> WellLogData
_wells_cache: dict[str, WellLogData] = {}


def generate_well_log(
    well_id: str,
    well_name: str,
    depth_start: float = 0.0,
    depth_end: float = 3000.0,
    depth_step: float = 0.125,
    seed: int = 42,
) -> WellLogData:
    """
    Generate a synthetic well log with GR, RT, DEN, NPHI curves.

    Lithology model (0=shale, 1=sandstone, 2=coal, 3=oil-bearing sand):
      - Shale:   GR~80, RT~2,   DEN~2.55, NPHI~0.25
      - Sand:    GR~30, RT~10,  DEN~2.45, NPHI~0.15
      - Coal:    GR~25, RT~50,  DEN~1.80, NPHI~0.40
      - Oil:     GR~35, RT~200, DEN~2.35, NPHI~0.20
    """
    rng = np.random.default_rng(seed)

    depths = np.arange(depth_start, depth_end, depth_step)
    n = len(depths)

    # Build a layered lithology sequence with ~50-80 layers
    n_boundaries = max(2, min(80, n // 100))
    boundary_indices = np.sort(rng.choice(n, size=n_boundaries, replace=False))

    lithology = np.zeros(n, dtype=int)  # default: shale
    prev = 0
    for idx in boundary_indices:
        if idx > prev:
            lithology[prev:idx] = int(rng.integers(0, 4))
        prev = idx
    lithology[prev:] = int(rng.integers(0, 4))

    # --- GR (Natural Gamma Ray, API) ---
    gr_base = np.where(
        lithology == 0, 80.0,
        np.where(lithology == 1, 30.0,
        np.where(lithology == 2, 25.0, 35.0))
    ).astype(float)
    gr = gr_base + rng.normal(0, 6, n)
    gr = np.clip(gr, 5.0, 200.0)

    # --- RT (Resistivity, ohm.m) — log-normal noise ---
    rt_base = np.where(
        lithology == 0, 2.0,
        np.where(lithology == 1, 10.0,
        np.where(lithology == 2, 50.0, 200.0))
    ).astype(float)
    rt = rt_base * np.exp(rng.normal(0, 0.25, n))
    rt = np.clip(rt, 0.1, 1000.0)

    # --- DEN (Bulk Density, g/cc) ---
    den_base = np.where(
        lithology == 0, 2.55,
        np.where(lithology == 1, 2.45,
        np.where(lithology == 2, 1.80, 2.35))
    ).astype(float)
    den = den_base + rng.normal(0, 0.04, n)
    den = np.clip(den, 1.0, 3.0)

    # --- NPHI (Neutron Porosity, v/v) ---
    nphi_base = np.where(
        lithology == 0, 0.25,
        np.where(lithology == 1, 0.15,
        np.where(lithology == 2, 0.40, 0.20))
    ).astype(float)
    nphi = nphi_base + rng.normal(0, 0.015, n)
    nphi = np.clip(nphi, 0.0, 0.6)

    depths_list = depths.tolist()

    curves = [
        CurveData(
            name="GR", unit="API",
            data=gr.tolist(), depth=depths_list,
            min_value=float(gr.min()), max_value=float(gr.max()),
            display_range=(0.0, 150.0), color="#00AA00", line_style="solid",
        ),
        CurveData(
            name="RT", unit="ohm.m",
            data=rt.tolist(), depth=depths_list,
            min_value=float(rt.min()), max_value=float(rt.max()),
            display_range=(0.1, 1000.0), color="#AA0000", line_style="solid",
        ),
        CurveData(
            name="DEN", unit="g/cc",
            data=den.tolist(), depth=depths_list,
            min_value=float(den.min()), max_value=float(den.max()),
            display_range=(1.5, 3.0), color="#0000CC", line_style="solid",
        ),
        CurveData(
            name="NPHI", unit="v/v",
            data=nphi.tolist(), depth=depths_list,
            min_value=float(nphi.min()), max_value=float(nphi.max()),
            display_range=(0.0, 0.6), color="#CC6600", line_style="dashed",
        ),
    ]

    actual_depth_end = float(depths[-1]) + depth_step if n > 0 else depth_end

    return WellLogData(
        well_id=well_id,
        well_name=well_name,
        depth_start=depth_start,
        depth_end=actual_depth_end,
        depth_step=depth_step,
        location=None,
        curves=curves,
    )


def generate_wells(
    count: int = 10,
    depth_start: float = 0.0,
    depth_end: float = 3000.0,
    depth_step: float = 0.125,
    base_seed: int | None = None,
) -> List[WellLogData]:
    """Generate `count` synthetic wells and cache them in memory.

    Args:
        base_seed: Optional base seed for reproducibility. If None, uses current time.
    """
    global _wells_cache
    wells: List[WellLogData] = []
    base = base_seed if base_seed is not None else int(time.time())
    for i in range(count):
        well_id = f"WELL-{i + 1:03d}"
        well_name = f"Well {i + 1}"
        well = generate_well_log(
            well_id, well_name,
            depth_start=depth_start,
            depth_end=depth_end,
            depth_step=depth_step,
            seed=base + i * 42 + 7,
        )
        wells.append(well)
    _wells_cache = {w.well_id: w for w in wells}
    return wells


def get_cached_wells() -> List[WellLogData]:
    """Return all previously generated wells from the in-memory cache."""
    return list(_wells_cache.values())
