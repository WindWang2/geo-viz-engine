# Well Log Page

This module provides the UI orchestration for the single-well log visualization.

## Architecture

The core rendering logic is delegated to the `geoviz-well-log` package:
- `geoviz_well_log.ChartEngine`: The ECharts-based rendering engine.
- `geoviz_well_log.TrackManager`: Manages the layout of curves and lithology tracks.

## Features

- **Data Loading**: Integration with `src.data.loaders` to fetch Excel/XML data.
- **AI Inference**: Calls the DeepTime API for automated lithology and facies prediction.
- **Export**: Supports SVG and PNG export of the rendered tracks.
