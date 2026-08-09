# Stratal / proportional slices

> **Package:** `geoviz_seismic.stratal` · **Facade:** `from geoviz import ...`

A *stratal slice* (proportional / horizon-relative slice) is a 2-D attribute map
sampled along a geological-time surface interpolated **proportionally** between
an upper and a lower horizon. Where the two horizons pinch together or apart the
surface tracks local stratigraphic proportion rather than absolute time — the
standard tool for inspecting depositional facies parallel to bedding, which flat
time slices cannot reveal when strata are dipping or faulted.

## Public API

```python
from geoviz import (
    build_proportional_surfaces,   # interpolate surfaces between 2 horizons
    extract_stratal_slice,         # sample one surface through a volume
    stratal_slice_volume,          # end-to-end: build + sample every fraction
    validate_horizon_pair,         # mask inverted / NaN / out-of-range cells
)
```

All four are **pure numpy** (headless); they are safe on worker threads and in
tests without a Qt/OpenGL context.

### Coordinate convention

- Volume shape: `(nI, nX, nS)` — inline, crossline, sample.
- Horizon grids: `(nI, nX)`, values in **sample-index space** (convert from ms
  via `(twt_ms - t0_ms) / dt_ms`). NaN marks an absent pick and is propagated.

### Linear interpolation in T

`extract_stratal_slice` samples with `scipy.ndimage.map_coordinates(order=1)`,
so the fractional sample position of a proportional surface is honoured. This
supersedes `extract_along_horizon`, which truncates to an integer sample — fine
for a single horizon but visibly stair-steps a *proportional* surface, because
the fractional part carries real stratigraphic information.

## Example

```python
import numpy as np
from geoviz import stratal_slice_volume

vol = np.random.randn(40, 50, 200).astype(np.float32)
top = np.full((40, 50), 40.0)    # sample index
bot = np.full((40, 50), 160.0)

# Quarter / half / three-quarter stratal slices + RMS over ±3 samples.
maps, surfaces = stratal_slice_volume(
    vol, top, bot,
    fractions=[0.25, 0.50, 0.75],
    window=3, mode="rms",
    return_surfaces=True,
)
# maps.shape == (3, 40, 50); surfaces.shape == (3, 40, 50)
```

Inverted pairs (`top > bottom`) and absent picks (NaN) are masked out once in
`stratal_slice_volume` and propagated through every surface.

## 3D rendering

`Renderer3D` renders the surfaces as flat XY planes (laid at each surface's mean
depth so the map reads as a geological-time attribute) through the same LUT
shader pipeline as the orthogonal slices:

```python
from geoviz import Renderer3D, build_proportional_surfaces

renderer = Renderer3D()
renderer.load_volume(vol, spacing=(25.0, 25.0, 4.0))
surfaces = build_proportional_surfaces(top, bot, [0.25, 0.5, 0.75])
renderer.set_stratal_slices(
    surfaces, labels=["Q1", "Q2", "Q3"], active=1, opacity=0.8,
)
renderer.set_stratal_visible(False)   # toggle without clearing
renderer.get_stratal_slices()         # -> ((label, visible, mean_depth), ...)
renderer.clear_stratal_slices()       # remove all planes
```

## Tests

- Algorithm: `tests/test_stratal_slice.py` (pure-numpy math, 63 cases)
- GL integration: `tests/test_renderer_3d_stratal.py` (52 cases, marked slow)

## Design notes

- **Why a separate module?** The stratal math is pure numpy and reusable
  outside the renderer (attribute maps, QC plots, export). Keeping it out of
  `renderer_3d.py` preserves the engine's headless-testable core.
- **Why mean depth for the plane Z?** A proportional surface is non-planar; a
  flat XY plane at the mean depth is the cheapest legible representation and
  reuses the existing `GLImageLutItem` path. A warped-quad variant is a future
  enhancement tracked in the workbench TODO list.
