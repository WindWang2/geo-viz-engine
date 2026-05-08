# Geoviz Well Log Visualization Engine

Modular, ECharts-powered well log rendering engine for Python/PySide6 desktop applications.

## Features

- **High Performance**: Renders tens of thousands of data points smoothly using ECharts (SVG/Canvas).
- **Geological Standards**: Built-in support for lithology patterns, facies intervals, and systems tract triangles.
- **Modular Design**: Fully decoupled from the main application; can be used in any PySide6 project.
- **Cross-Well Support**: Includes `SyncManager` for multi-well viewport synchronization and `ConnectionOverlay` for correlation polygons.
- **Vector Export**: Export high-quality SVG versions of your charts.

## Installation

```bash
pip install geoviz-well-log
```

*(Note: Currently available as a local package in this workspace)*

## Quick Start

### 1. Basic Single Well Rendering

```python
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget
from geoviz_well_log import ChartEngine, WellLogData, CurveData

app = QApplication([])

# 1. Prepare Data
well_data = WellLogData(
    well_name="Well-01",
    top_depth=1000,
    bottom_depth=1100,
    curves=[
        CurveData(name="GR", depth=[1000, 1001, 1002], values=[60, 80, 70], color="#2d3748")
    ]
)

# 2. Setup UI
window = QWidget()
layout = QVBoxLayout(window)
engine = ChartEngine()
layout.addWidget(engine)

# 3. Render
# Data must be converted to the engine's internal JSON format
# Use the built-in helper logic or pass raw track configurations
payload = {
    "metadata": { "wellName": "Well-01", "topDepth": 1000, "bottomDepth": 1100 },
    "tracks": [
        { "type": "DepthTrack", "name": "Depth", "width": 6 },
        { 
            "type": "CurveTrack", "name": "GR", "width": 15,
            "series": [{"name": "GR", "color": "#1f2937", "data": [[1000, 60], [1001, 80], [1002, 70]]}]
        }
    ]
}
engine.render_data(json.dumps(payload))

window.show()
app.exec()
```

## Advanced: Cross-Well Correlation

For correlating multiple wells, use the `SyncManager` and `ConnectionOverlay`:

```python
from geoviz_well_log import ChartEngine, SyncManager, ConnectionOverlay

# ... setup multiple engines ...
engines = [engine1, engine2]
sync_manager = SyncManager()

for e in engines:
    sync_manager.register_engine(e)
    # When one scrolls, others follow automatically

# Draw polygons between wells
overlay = ConnectionOverlay(parent_container, engines)
overlay.set_links(correlation_links)
```

## Package Structure

- `geoviz_well_log.ChartEngine`: The core PySide6 widget (wraps QWebEngineView).
- `geoviz_well_log.models`: Pydantic data models for logs, curves, and intervals.
- `geoviz_well_log.config`: Configuration classes for track styling and layout.
- `geoviz_well_log.sync_manager`: Logic for horizontal viewport lock-step.
- `geoviz_well_log.connection_overlay`: QPainter-based layer for inter-well lines.
