# Well Log Page

This module provides the UI orchestration for the single-well log visualization.

## Architecture

The core rendering logic is delegated to the `geoviz-well-log` package:
- `geoviz_well_log.WellLogCanvas` / `build_qpainter_tracks`: QPainter well-log renderer.
- `src.pages.well_log.qpainter_widget.QPainterWidget`: page-level canvas host.

## Features

- **Data Loading**: Integration with `src.data.loaders` to fetch Excel/XML data.
- **AI Inference**: Calls the DeepTime API for automated lithology and facies prediction.
- **Export**: Supports SVG and PNG export of the rendered tracks.
