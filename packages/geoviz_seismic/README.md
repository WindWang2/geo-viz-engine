# geoviz-seismic

3D seismic volume visualization + 2D profile display (VD/Wiggle) for PySide6.

## Install

```bash
pip install geoviz-seismic
# Optional: GPU-accelerated Wiggle rendering
pip install geoviz-seismic[wiggle]
```

## Quick Start

```python
import sys
from PySide6.QtWidgets import QApplication
from geoviz_seismic import SeismicView

app = QApplication(sys.argv)

# Option A: Load a SEGY file
view = SeismicView(path="survey.sgy")

# Option B: Built-in demo with synthetic data
view = SeismicView()

view.show()
app.exec()
```

## Features

- **3D volume rendering** with interactive inline/crossline/time slice planes
- **2D profile display** in VD (variable density heatmap) or Wiggle (waveform) mode
- **On-demand SEGY loading** — reads slices from disk, not the entire volume
- **LRU slice cache** for fast slice switching
- **Horizon surface overlay** with nearest/RBF interpolation
- **Professional seismic colormaps** (seismic, gray, jet, huang)

## API

```python
from geoviz_seismic import SeismicView, SeismicLoader, SeismicCache
from geoviz_seismic import Renderer3D, ProfileWidget, ProfileVD, ProfileWiggle
from geoviz_seismic import HorizonParser, ColormapManager
from geoviz_seismic.models import SeismicVolumeMeta, SliceInfo, HorizonData
```

## Horizon File Format

Tab-separated: `inline  crossline  time_ms`

```
1000    2000    1500.0
1000    2001    1502.5
1001    2000    1498.0
```
